# Estúdio automático · arquitetura

Sistema que cria e posta reels nos perfis do projeto sem intervenção humana: pauta → roteiro → voz → cena → render → QA → post. Roda num PC Windows, **como sessão do Claude Code** (`claude -p` disparado pelo agendador): o Claude faz as etapas criativas e a voz (pelo MCP do ElevenLabs, que só existe dentro da sessão), e chama scripts para as etapas mecânicas. Posta pela API oficial da Meta. Sem aprovação humana: quem decide se um vídeo sai é o QA automático; o que reprova vai para `<perfil>/reviews/falhas/` e gera alerta.

## 1. Visão geral

```
Agendador do Windows (a cada 30 min, quando a fila está abaixo da reserva)
  └─ sessão do Claude Code (claude -p, com os MCP de perfis.yaml → padrao.ferramentas_mcp)
       └─ orchestrator  ──>  para cada perfil ativo, mantém a reserva (`fila_alvo`, padrão 3) pronta na fila
        1 PAUTA      escolhe o tema do dia no banco do perfil          [script + Claude]
        2 ROTEIRO    Claude escreve o roteiro JSON nas batidas do guia [Claude]
        3 VOZ        ElevenLabs via MCP + words.json (faster-whisper se o MCP não der tempos) [Claude + script]
        4 CENA       Claude escreve a cena (Remotion/Three.js) a partir do roteiro e do style-guide.md [Claude]
        5 RENDER     Remotion → frames → MP4 1080×1920 30 fps + capa   [script]
        6 QA         técnico (script) + visual (Claude lê os quadros contra o guia)
        7 FILA       gates universais + <perfil>/gates.py; aprovado entra em <perfil>/posts/04-aprovado/ com legenda e horário
Agendador do Windows (nos horários de post de cada perfil)
  └─ publisher       pega o próximo da fila e posta via Graph API     [script]
```

Cada etapa lê só a saída da anterior e grava num arquivo dentro de `<perfil>/out/<id>/`. Se uma etapa falha, ela tenta de novo até o limite; se continuar falhando, a edição vai para `<perfil>/reviews/falhas/` com o motivo e o próximo tema entra no lugar. A reserva de vídeos por perfil absorve as falhas sem deixar dia sem post.

## 2. Fonte das regras

Os guias de identidade aprovados (`<perfil>/guia.html`) são a fonte de verdade. De cada guia sai um `<perfil>/style-guide.md` com as regras em texto (paleta, tipografia, câmera e profundidade, animação, formato, sempre/nunca). O Claude Code lê o `style-guide.md` em toda etapa criativa. Mudou o guia, muda o `style-guide.md`, e a próxima edição já sai com a regra nova. A config de cada perfil mora em `<pasta>/perfil.yaml` (chaves em `_sistema/orquestrador/CHAVES-PERFIL.md`); o `perfis.yaml` da raiz só tem `padrao` e `ordem`.

Regras que valem para todos os perfis (detalhe em `_sistema/regras-gerais.md`):
- assunto reconhecível de cara, sem som e sem legenda;
- gancho forte nos primeiros segundos;
- fundo bonito, colorido e vivo, no tom da ID (nunca escuro e sem graça);
- áudio sempre mixado: voz na frente, trilha com ducking, SFX ajustados;
- câmera com profundidade 3D (camadas e paralaxe, ponto de vista que muda por plano), sem trocar o estilo aprovado do perfil;
- toda arte é feita em código (sem gerador de imagem ou vídeo);
- personagens, cenários e inserts saem do roteiro de cada edição, dentro do traço, das cores e da tipografia do guia;
- idioma do conteúdo em `perfil.yaml → idioma_conteudo` (padrão inglês).

## 3. Etapas e gates

| # | Etapa | Entrada | Saída | Gate (passa se…) | Tentativas |
|---|---|---|---|---|---|
| 1 | Pauta | `<perfil>/pautas.csv`, `formatos.md`, histórico de posts | `brief.json` | tema não usado nos últimos 90 dias; formato não `cortado` (§9); perfil de fatos: fato com 2 fontes | 3 temas |
| 2 | Roteiro | `brief.json`, `style-guide.md`, `format.json` | `script.json` | valida no `_sistema/schemas/script.schema.json`; palavras e duração dentro do formato; todas as batidas presentes | 3 |
| 3 | Voz (pula em perfil sem `voz`) — Claude pelo MCP do ElevenLabs | `script.json`, voz do perfil | `voice.mp3`, `words.json` | duração ±10% do roteiro; Whisper bate com o texto (erro de palavra < 5%) | 2 |
| 4 | Cena | `script.json`, `words.json`, `style-guide.md`, biblioteca do perfil | composição Remotion do perfil | compila; todos os planos do roteiro existem; textos amarrados aos timestamps | 3 |
| 5 | Render + mix | cena, voz, trilha, SFX | `video.mp4`, `cover.jpg`, `sheet.jpg` | 1080×1920, 30 fps, duração certa, sem frame preto > 0,2 s; áudio pelo `_sistema/audio-mix.md` (−14 LUFS, voz ≥ 12 LU acima da trilha, Whisper na mix final) | 2 |
| 6 | QA visual | quadros, `cover.jpg`, `style-guide.md` | `qa.json` | nota ≥ `qa.corte` (padrão 6,8); **assunto reconhecível de cara** e **fundo bonito e vivo** ≥ corte; nenhum item "nunca" violado (`_sistema/contratos/06_qa.md`) | **5 rodadas no total** (1ª + 4 correções); na 5ª reprovação → `fail.json` |
| 7 | Fila | tudo acima | `<perfil>/posts/04-aprovado/<horário>.json` | gates universais (`gates_universais.py`: gancho, liga_ao_fato, seguir, card_final, area_segura, piscadas, audio, hud, variacao) + `<perfil>/gates.py`; legenda e hashtags no padrão | — |
| 8 | Post | item da fila | `post.json` com o ID da mídia | a API retorna status `FINISHED` e `PUBLISHED` | 3, com 10 min entre elas; se o contêiner vai para o processamento assíncrono (upload 400 `ProcessingFailedError` em vídeo longo), o `post.py` grava `out/<id>/container.json` e as rodadas seguintes retomam o **mesmo** contêiner (publica ao ficar `FINISHED`; recria só se der erro ou passar de 3 h), sem segurar os outros perfis. Com `padrao.cloudflare: true`, se o upload direto der 400, o `post.py` tenta **por link** (cópia num deploy de prévia do Cloudflare Pages do perfil, `video_host`) |

Os contratos detalhados de cada etapa (o que o Claude recebe, o que entrega, o que é proibido) estão em `_sistema/contratos/0X_*.md`.

## 4. Pastas
Ver a estrutura no `CLAUDE.md` da raiz. Cada etapa grava em `<perfil>/out/<id>/` e o arquivo do post anda por `<perfil>/posts/` (`_sistema/fluxo.md`).

## 5. Postagem (API da Meta)

Pré-requisitos, uma vez por conta: perfil Instagram profissional (Creator ou Business) ligado a uma página do Facebook; um app na Meta for Developers com as permissões de `_sistema/regras-gerais.md §7`; um token de longa duração por conta, guardado no `.env` (nunca no código). Passo a passo: `_sistema/briefs/configurar-meta.md`.

Fluxo de um reel: criar o contêiner (`media_type=REELS`, `upload_type=resumable`, legenda, capa); enviar o MP4 direto do PC pelo upload resumível; consultar o status até `FINISHED`; publicar (`media_publish`). O post não depende de hospedar o vídeo em URL pública.

Limites que o publisher respeita: até 50 posts por conta a cada 24 h; renovar o token antes dos 60 dias (`meta_token.py`; o `post.py checar` avisa com 7 dias de antecedência).

## 6. Agenda

- **Produção:** a cada 30 min, nos perfis com `producao_auto: true`; só produz quando a fila (`04-aprovado/`) está abaixo de `fila_alvo` (reserva mínima). Uma execução por vez (a tarefa ignora a próxima se a anterior ainda roda; limite de 12 h por execução). Uma edição por perfil de cada vez: se o perfil tem item em `02-em-producao/` com log mexido há menos de 15 min (inclusive uma edição feita à mão), o orquestrador não abre outra. O agendador faz no máximo 1 edição por perfil a cada rodada, em rodízio. Pausa curta: `pausa_programada`; pausa longa: `pausado`.
- **Post:** nos horários de `<perfil>/perfil.yaml → horarios`, no fuso de `perfis.yaml → padrao.fuso`.
- **Acompanhar uma produção:** cada edição é uma sessão `claude -p` nova. O passo a passo aparece ao vivo em `logs/<id>_<data>.log` (uma linha por ação); a 1ª linha traz o id da sessão, que também fica em `posts/02-em-producao/<id>.json`. Para abrir a conversa inteira depois que ela terminar: `claude --resume <id-da-sessão>` num terminal na raiz do projeto.
- **Painel de Produção** (`_sistema/painel/`): página local ao vivo em http://127.0.0.1:8765 que mostra a situação de cada perfil (rodando / produzindo / atenção / parado / montando / fora) com o motivo, as tarefas do agendador, a edição em produção (etapa por etapa + log ao vivo + comando de `--resume`), a fila com horário, o que está no ar (lido do Instagram, com views), falhas com motivo e as métricas por perfil (Graph API, cache de 10 min). Para abrir: `_sistema/painel/abrir-painel.cmd` ou `python _sistema/painel/painel.py`. Só lê os arquivos, não muda nada. Vigia opcional: `_sistema/vigia_painel.ps1` (se o Painel não responde, sobe de novo).
- **DM automática** (opcional, `_sistema/orquestrador/dm.py`, tarefa a cada 15 min): quem comenta a palavra-chave do perfil recebe por DM privada o link do produto (`<perfil>/perfil.yaml → oferta.dm`, `oferta.link_gratis`) e uma resposta pública curta; 1 vez por comentário, até 7 dias. Só envia com `oferta.dm_ativa: true`. Perfil sem oferta pode usar só a votação (`dm_so_votacao`). Regra da palavra: `_sistema/palavras-comentario.md`.
- Perfil recém-implantado: a **1ª edição sai assim que o perfil fica pronto, como teste**, com o dono olhando; só depois liga `producao_auto`.
- **Sem "aquecer" conta e sem rampa de posts:** nada de curtir/seguir/comentar por robô (fora da API, é o que o Instagram pune). O que separa os perfis é a retenção (tempo médio assistido), então é o gancho que precisa melhorar, não a conta. Se um perfil novo ficar parado em menos de 100 de alcance por post depois de 5 posts, rever antes o gancho e a capa. Aquecimento só humano: 5–10 min por dia no celular (curtir e comentar de verdade no nicho, stories).
- A produção roda pelo Agendador de Tarefas do Windows (`_sistema/agendador.ps1`) abrindo uma **sessão do Claude Code** na raiz do projeto (`claude -p "produzir" …`), com o conector do ElevenLabs habilitado e logado. Sem a sessão não há voz: o ElevenLabs gera pelo MCP; a `ELEVENLABS_API_KEY` do `.env`, se houver, só lê o saldo de créditos.
- O post (etapa 8) é mecânico e roda direto pelo script `_sistema/orquestrador/post.py`, sem sessão.
- Se o MCP do ElevenLabs estiver desconectado ou sem créditos, a etapa 3 falha com `fail.json` e alerta; a reserva da fila segura enquanto o dono reconecta.

## 7. Sem aprovação humana: o que segura a qualidade

- QA técnico e visual em todo vídeo (etapa 6); o visual compara os quadros com o `style-guide.md` e com a lista "nunca" do guia.
- Gates de entrada da fila (universais + plugin do perfil): erro barra a entrada, aviso só é impresso.
- Reserva na fila: uma falha não vira dia sem post.
- Avisos (`_sistema/avisos.py`, mostrados no Painel) quando: o MCP do ElevenLabs não responde ou fica sem créditos, uma edição vai para `<perfil>/reviews/falhas/`, a fila de um perfil cai, um post falha, o token está para vencer.
- Botão de parada: `perfis.yaml → padrao.pausado: true` (ou `pausado` por perfil) suspende a produção e o post sem apagar a fila.

## 8. Perfis

A lista de perfis é `perfis.yaml → ordem`; cada um tem `<pasta>/perfil.yaml` com `status` (`ativo` | `montando` | `fora-do-pc`). Só perfil `ativo` produz e posta. Perfil sem `voz` pula a etapa 3. Perfil novo: `python _sistema/orquestrador/criar_perfil.py <pasta> --handle @x` copia o `_modelo-perfil/` e segue `_sistema/implantar-perfil.md`.

## 9. Biblioteca de formatos (o que retém fica, o que não retém sai)

Cada perfil tem um `<perfil>/formatos.md`: a lista de formatos que ele pode usar, com a promessa, o gancho dos primeiros segundos, as batidas (que apontam para o `format.json`), um exemplo e o desempenho medido. O `id` do formato é o mesmo da coluna `formato` do `pautas.csv`. O QA garante que o vídeo está bem feito; a biblioteca diz se o formato funciona com o público.

**Ciclo:**
1. **Medir:** 48 h e 7 dias depois do post, ler os Insights da Graph API (alcance, retenção, compartilhamentos, salvamentos) e gravar em `metricas:` no arquivo do post (hoje o Painel só lê). Precisa da permissão `instagram_manage_insights` no app da Meta.
2. **Registrar:** a lição do post entra em `reviews/` e numa linha em `formatos.md → Lições`; a tabela do formato é recalculada com a média dos posts medidos.
3. **Decidir** (no relatório semanal, mínimo de 3 posts medidos por formato):
   - formato abaixo da média do perfil em retenção 3 s **e** em compartilhamentos/1k → estado `cortado`, e as pautas dele no `pautas.csv` voltam para revisão;
   - formato acima da média nos dois → estado `ativo` e peso maior na escolha da pauta;
   - formato novo entra como `em teste`, no máximo 1 em teste por perfil, e só se couber no guia (formato não troca estilo, traço, paleta ou voz).
4. **Usar:** a etapa 1 (Pauta) escolhe primeiro entre formatos `ativo`, nunca usa `cortado`, e a etapa 2 (Roteiro) segue a promessa e o gancho do formato escolhido.

Proibido na biblioteca: formato que dependa de conteúdo de terceiros (repost, gancho tirado do vídeo de outro criador), de gerador de imagem ou vídeo, ou de várias contas repostando o mesmo vídeo.

## 10. Cross-post (mesmo vídeo, outras plataformas)

O render 9:16 que sai do QA também pode ir para o YouTube Shorts e o TikTok. É só distribuição: o vídeo é o mesmo (cortado antes da chamada final, sem re-render), sem produção extra. Código: `_sistema/orquestrador/crosspost.py` (chamado pelo `orquestrador.publicar`); config em `<perfil>/perfil.yaml → crosspost` (chaves em `CHAVES-PERFIL.md §10`). Regras de conteúdo e checagem antes do envio: `_sistema/regras-gerais.md §10`.

- **Legenda:** a do Instagram sem a linha de chamada, no molde único do YouTube; título do Shorts = a primeira linha. Thumb 16:9 por composição do Remotion do perfil (`crosspost.youtube.thumb`), playlists por formato.
- **Quem dispara:** a tarefa de post do agendador → `orquestrador.py publicar` → para cada perfil com bloco `crosspost`: `crosspost.py proximo --perfil <pasta>`.
- **Cada rodada, por perfil:** 1 envio no máximo. Só entra o que já saiu no Instagram há mais de `ATRASO_MIN`. Post novo (depois de `crosspost.desde`) vem antes do acervo; acervo só se sobrar cota e só com `crosspost.acervo: true`. Limites em constantes do `crosspost.py`: `MAX_DIA` (todos os canais do projeto), `MAX_ACERVO_DIA`, `MAX_DIA_CANAL`, `INTERVALO_H` entre envios do mesmo canal. Fila sem pular vídeo: o `proximo` envia sempre o mais antigo ainda pendente. Vídeo que falha `MAX_FALHAS` vezes seguidas sai da vez e avisa.
- **Cada envio:** `preparar` (corte antes da chamada final, textos, capa 16:9) → `confere_yt` (reprova antes de enviar) → traduções → upload resumível (se a rede cair, continua de onde parou) → capa → playlist → `conferir_no_ar` → grava `out/<id>/cross_youtube.json`. Falha vira `cross_youtube_erro.json` e a rodada seguinte tenta de novo.
- **Idiomas:** `crosspost.youtube.idioma` (senão `idioma_conteudo`) = idioma original; `crosspost.youtube.traduzir` = `false` | `true` | lista de idiomas. `crosspost.youtube.projeto_google` separa a cota por projeto do Google Cloud.
- **Métricas:** cada plataforma entra no Painel; a decisão de cortar um formato continua pelo Instagram.
- **Para um perfil novo ligar o YouTube:** bloco `crosspost.youtube` no `perfil.yaml`, as variáveis OAuth no `.env` (nomes em `client_id_env`, `client_secret_env`, `refresh_token_env`; gerar com `crosspost.py auth-youtube --perfil <pasta>`, login no Google do canal), composição da thumb no Remotion do perfil e a zona do título.

| Quero… | Onde |
|---|---|
| ligar/desligar o YouTube de um perfil | `<perfil>/perfil.yaml → crosspost.youtube.ativo` |
| subir (ou não) o acervo antigo; data de corte | `crosspost.acervo`, `crosspost.desde`, `crosspost.acervo_pausado_ate` |
| teto por dia, intervalo entre envios, atraso depois do Instagram | constantes `MAX_DIA`, `MAX_ACERVO_DIA`, `MAX_DIA_CANAL`, `INTERVALO_H`, `ATRASO_MIN` em `_sistema/orquestrador/crosspost.py` |
| idioma do canal | `crosspost.youtube.idioma`; sem ele vale `idioma_conteudo` do perfil |
| zona do título na capa 16:9 | `crosspost.youtube.thumb.zona_titulo` ([x0,y0,x1,y1] em 1280×720) |

## 11. Cópia para o Google Drive (opcional)
Ao entrar em `04-aprovado` (`fila.py`), `orquestrador/drive.py` copia `out/<id>/video.mp4` para `<DRIVE_PASTA>/<perfil>/<id>.mp4` (pasta sincronizada do Drive para computador). Edição refeita: o novo substitui e o antigo vai para `<perfil>/anteriores/`. Falha ou Drive fechado: só gera aviso, o post não é bloqueado. `.env → DRIVE_PASTA` vazio = desligado.

## 12. Em aberto no motor
1. Leitura automática de métricas 48 h / 7 d e atualização do `formatos.md` (§9); hoje só o Painel lê as métricas.
2. Alertas por e-mail/webhook (hoje só os avisos do Painel).
