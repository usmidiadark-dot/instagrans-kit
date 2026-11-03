# regras-gerais.md — valem para todos os perfis automatizados

> Regra de perfil pode ser mais rígida que esta, nunca mais frouxa. Resumo curto: `REGRAS-UNIVERSAIS.md` na raiz. Chaves de cada perfil: `_sistema/orquestrador/CHAVES-PERFIL.md`.

## 1. Qualidade (o QA reprova se faltar)
- **Assunto reconhecível de cara**, sem som e sem legenda.
- **Fundo bonito e vivo**: colorido, com luz e movimento, no tom da ID. Nunca escuro e parado (salvo estilo de referência aprovado que seja assim).
- **Câmera com profundidade 3D** e planos variados (mínimo do `format.json → min_camera_planes`).
- **Áudio mixado** pelo `audio-mix.md`: voz na frente, −14 LUFS final.
- Estilo, cores e tipografia do `guia.html` do perfil. Nada inventado fora dele.
- **Gancho forte**: nos primeiros segundos (`ritmo.gancho_ate_s`, padrão 3) o assunto aparece grande e legível; a primeira frase é pergunta, número ou promessa concreta (nada de "olá", logo ou vinheta); movimento já no primeiro quadro. Gate `gancho` em `gates_universais.py` (texto do gancho até 1 s, voz até 1 s, movimento mínimo `ritmo.gancho_movimento_min`). Abertura calma de propósito: `ritmo.abertura_calma: true` no perfil ou `out/<id>/abertura_excecao.json` com o motivo.
- **HUD interativa** (quando o perfil liga `qualidade.hud`): um painel fixo com a cara do perfil, que entra depois do gancho e fica até o fim, com 1–3 dados que mudam no momento em que a voz fala (contador, cronômetro, medidor, status). Layout fixo no código do perfil; o roteiro só traz os valores e os tempos (`script.hud.passos`, 2 ou mais valores). Sempre no estilo do vídeo, nunca um painel genérico colado por cima, e sem cobrir rosto, assunto ou legenda. Junto dela: inserts de dado e legenda dinâmica e limpa (blocos curtos que acendem com a voz). Gate `hud`.
- **Área segura do feed, sem amontoar**: o reel também aparece no feed sem ser aberto, cortado no centro em 4:5 (no quadro 1080×1920, de y ≈ 285 a 1635). Tudo que importa (gancho, HUD, cards, frases, número, card final) fica dentro desse corte, fora da coluna de botões da direita (x > 950 abaixo de y 1000) e acima da faixa da legenda do Instagram. Vale também para o **assunto** (personagem, objeto): base e sombra acima de y 1620, topo da cabeça abaixo de y 300 (só o fundo e o corte intencional de close sangram). **Sem amontoar:** além da HUD e da legenda, no máximo 2 inserts juntos (`qualidade.max_inserts_juntos`). A fonte não diminui para caber. Checagens: por roteiro no gate `area_segura` (`qualidade.area_segura`) e por pixel no `piscadas.py` (`fora_da_area`, gate `area_segura_ok` do `render.py`, ligado por `qualidade.area_feed`). Se o perfil precisa conferir a geometria do assunto de outro jeito, a checagem vai no `<perfil>/gates.py`.
- **Variar a execução, nunca Ctrl+C Ctrl+V**: recurso que se repete entre vídeos (marca, card, entrada, transição, insert) mantém a função e a animação, mas muda o desenho por edição (estilo, ponto de partida, lado, forma). Gate `variacao` (`qualidade.cena_varia`, `qualidade.variacoes`, `qualidade.inserts_novos_min`, `qualidade.gancho_banco`).
- **Nenhuma piscada**: texto, HUD ou insert nunca aparece por menos de 0,4 s nem some e volta; trocas são cruzamentos, painéis recolhem sem sumir-e-voltar. O `render.py` reprova sozinho (`piscadas.py`, gate `sem_piscada_ok`; gate `piscadas` na fila) e o QA confere no vídeo.
- **Pausa para pedir para seguir**: um card curto e visível pedindo para seguir o perfil (`script.seguir {t, dur, texto}`), no momento de `ritmo.seguir.momento` (`meio` ou `final`) e com a duração de `ritmo.seguir.duracao_s` (padrão 1,5–2,5 s). A fala acompanha o card; o desenho varia por edição. Gate `seguir`.
- **Card final**: `ritmo.card_final` (`oferta`, `seguir` ou `nenhum`), com pelo menos `ritmo.card_final_min_s` (padrão 1,6 s) depois da última palavra. Gate `card_final`.
- **Capa pensada para a grade do perfil**: a grade tem que ficar bonita, então cada capa é desenhada pensando na disposição dela entre as outras.
  - **Diz o que é o vídeo**, em destaque: o assunto em tipo grande e chamativo, com cores vibrantes da paleta do perfil, e o texto **inserido na arte** (atravessando bordas, sobre a cena, seguindo formas), nunca um cabeçalho solto.
  - **Corte 3:4:** na grade o Instagram mostra a capa cortada no centro em 3:4 (faixa y 240–1680 de 1920). Título, assunto e selo ficam inteiros dentro dessa faixa.
  - **Zonas da grade real:** o ícone de reel fica no canto superior direito e a contagem de views no inferior esquerdo; nenhum texto da capa fica debaixo deles (`capa_grade.py` simula, o QA confere).
  - **Família visual fixa:** o mesmo layout, tipografia e contorno em todas as capas do perfil (definido no `style-guide.md` do perfil); a variação é planejada.
  - **Disposição:** cada perfil define em `<perfil>/perfil.yaml → grade.ciclo` a sequência de cores de fundo da capa; o `render.py` dá a cada edição a cor da posição dela na grade. Com `qualidade.grade_por_ordem` a cor segue a ordem real de publicação (`grade.py`). Elementos que encostam na borda devem emendar com a capa vizinha.
  - Antes de aprovar um modelo de capa novo, simular a grade (3 × 2, capas cortadas em 3:4) e mostrar ao dono.
  - **Antes de dar por concluída qualquer mudança de vídeo, capa ou fila:** rodar `feed_check.py <pasta_do_perfil>` (lê o feed real pela Graph API, mede a cor de cada capa e confere o ciclo, a fila e a contagem); só conclui com `ok: true`.
- **Capa no momento da ação:** o quadro da capa é o momento em que a ação do título está mais legível (o gesto, a postura), com rosto e mãos inteiros, nunca um quadro neutro.
- **Sair bom sozinho**: toda regra de qualidade vira **checagem automática** num script (`mix.py`, `render.py`, `fila.py`, `gates_universais.py`, `<perfil>/gates.py`) ou item com nota no QA; regra só em texto é esquecida. Valem para todos os perfis:
  - **Som em cada ação:** todo plano tem o seu SFX (`script.json → shots[].sfx`), e um **ambiente contínuo** baixinho o vídeo todo, conforme o perfil. SFX pode cair por baixo da voz (volume próprio por evento), nunca acima dela. Gates do `mix.py`: `som_por_plano_ok`, `ambiente_ok`, `sfx_ok` (ligados em `<perfil>/perfil.yaml → audio`).
  - **Música sem tranco:** a trilha abaixa e volta devagar com a voz; gate `ducking_suave_ok` (`audio.duck_max_db_s`).
  - **Toda ação vira gancho de insert:** quando algo acontece na tela (gesto, objeto, número), entra no mesmo trecho um insert ou card que reforça a ação.
  - **Inserts novos a cada edição:** objetos tirados do roteiro daquela edição, desenhados em código; com `qualidade.inserts_novos_min` o gate reprova a edição que só repete inserts anteriores.
  - **Peça sorteada só com ligação ao fato:** cena de explicador ou insert sorteado precisa de `liga_ao_fato` (1 frase de 20+ caracteres que cita o assunto e diz por que a peça pertence a ESTE fato). Sem ela, a peça sai. Gate `liga_ao_fato` (`qualidade.liga_ao_fato`, padrão ligado).
  - **Fundo vivo de verdade:** além da cena, camadas que se mexem o tempo todo e enriquecem o ambiente sem tirar o foco, no estilo do perfil: partículas de luz ou poeira, reflexos, raios de luz respirando, fumaça, folhas, elementos de identidade do perfil. Nunca uma parede parada (`qualidade.fundo_vivo`).
  - **Variação constante:** cenário e objetos de cena mudam a cada edição; nenhum cenário repetido das 2 últimas edições (banco de cenários no `formatos.md` do perfil; `qualidade.cena_varia`).
- Toda arte feita em código (Remotion, React, Three.js, SVG). Sem gerador de imagem ou vídeo.

## 2. Aprovação
- **Automática.** Passou no QA técnico e visual → `posts/04-aprovado/` e entra na fila. Reprovou → volta com o motivo escrito no arquivo do post; depois de 5 rodadas de QA no total vai para `reviews/falhas/` e dispara alerta. O dono pode aprovar à mão uma edição abaixo do gate (`qa.json → aprovado_dono: true`; o `fila.py` aceita, e o veredito do QA continua registrado).
- Nota de corte: `perfil.yaml → qa.corte` (padrão 6,8).
- Botão de parada: `perfis.yaml → padrao.pausado: true` suspende tudo.

## 3. Custos
- Antes de abrir uma sessão, o orquestrador confere o crédito de voz (`padrao.voz_min_creditos`). Registre o gasto de cada geração no arquivo do post (`custo:`) e no `relatorio.md` da edição.

## 4. Revisão de imagem e vídeo
- A conferência é feita sobre os quadros do vídeo e a capa, por subagentes, que devolvem nota e motivo em texto (`_sistema/contratos/06_qa.md`).
- Defeito que se repetir duas vezes vira regra no `style-guide.md` do perfil.
- **Melhoria contínua:** cada perfil tem `<perfil>/reviews/aprendizados.md`. Toda produção lê antes de começar e acrescenta 1–3 lições no fim (o `produzir.md` manda); pedido do dono entra lá na hora. Lição repetida vira regra e, se der, checagem no código.
  - **Defeito reincidente vira checagem:** todo defeito apontado pelo QA ou pelo dono entra em `<perfil>/reviews/licoes_recorrentes.md` (uma linha numerada por defeito, somando as reincidências). Com **3 reincidências** a lição fica **CRÔNICA** e vira checagem no `<perfil>/gate_comum.py` (roda sobre qualquer edição renderizada) ou no `<perfil>/gates.py`, não em mais uma régua por cena. O `qa.py preparar` injeta as lições e o resultado do gate no prompt dos avaliadores.

## 5. Conteúdo
- Cada perfil tem identidade própria: não reaproveitar personagem, paleta ou frase de outro perfil.
- Sem conteúdo enganoso, sem imitar marca ou pessoa real, sem prometer resultado (saúde, dinheiro). Perfil de fatos: fato só com 2 fontes.
- **Roteiro profundo**: roteiro raso reprova; cada frase traz decisão, porquê, número ou virada.
- Música e SFX só com licença registrada (`reviews/<id>-assets.md`) ou gerados em código.
- **Hashtags**: 3 fixas + 3 variáveis que não repetem nos 3 posts vizinhos, numa linha, uma linha em branco depois do texto (`_sistema/orquestrador/hashtags.py`).
- Legenda e hashtags seguem o `brief.md`/`guia.html` do perfil e, acima deles, `_sistema/legenda.md`.
- **Chamada para comentar (só em perfil com oferta ligada)**: COM CTA, a legenda abre com o gancho do vídeo e a frase de comentário vai para o corpo (depois das linhas numeradas, antes das hashtags), sorteada do banco do perfil (`legenda_cta`), com o emoji do tema do vídeo e sem repetir as últimas edições; SEM CTA, nenhuma chamada. O `fila.py` monta e confere (`legenda_cta.py`), o `post.py` confere e nunca põe a linha no topo. Perfil sem oferta usa `sem_cta_sempre: true`.

## 6. Arquivos e scripts
- **Versões dos vídeos**: toda versão renderizada fica em `<perfil>/versoes/<id>/<id>_v<N>_<data_hora>.mp4` (+ a capa da mesma versão); o `render.py` guarda sozinho a cada render. O `out/<id>/video.mp4` é sempre a versão atual. Render feito por outro script também guarda a versão lá.
- Scripts longos ficam em arquivo e são editados por trechos, com `assert` e conferência depois.
- Logs e renders longos vão para arquivo; leia com `grep`/`tail`.
- Discos externos no Mac criam arquivos `._*`: **todo script que lê pastas ignora `._*`**.
- Tokens e senhas só no `.env`. Nunca em `.md`, `.yaml` ou no chat.

## 7. Contas (checklist do dono; o agente não cria contas)
Para cada perfil (passo a passo da Meta: `_sistema/briefs/configurar-meta.md`):
- [ ] Conta criada, com foto e bio do guia
- [ ] Profissional (Criador ou Empresa)
- [ ] Ligada a uma Página do Facebook
- [ ] App da Meta com as permissões: `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `instagram_manage_comments`, `instagram_manage_messages`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `business_management`
- [ ] "Permitir acesso às mensagens" ligado no Instagram (só se for usar DM automática)
- [ ] Token de longa duração e IG User ID no `.env` (nomes em `perfil.yaml → token_env` / `user_id_env`)
- [ ] 2FA ativado
- [ ] **Traduzir reel**: na tela de postar (Mais opções → Acessibilidade e tradução → "Traduzir reel"), se a opção estiver disponível, ligar sempre, com três idiomas diferentes do idioma do conteúdo (ex.: português do Brasil, espanhol e francês para conteúdo em inglês). Se mostrar "Indisponível", seguir sem ela e conferir de novo no post seguinte. A Graph API (`post.py`) não tem campo para isso: nos posts automáticos conferir/ligar pelo app.

## 8. Como falar e trabalhar com o dono (todas as sessões)
(1) explicar em português simples, sem sigla nem caminho de arquivo no meio; (2) tudo que depende dele vai em pergunta com opções, recomendação primeiro, uma decisão por pergunta; o que dá para decidir pelo guia e pelo que já foi aprovado, o agente decide e avisa; (3) tipo novo de vídeo, formato ou pilar segue o processo completo antes de produzir (capa por tipo + grade 3×3, peças variadas e sorteadas, checagens no `fila.py`/`gates.py`, documentação, folha para o dono aprovar); (4) fechar sempre com: o que está pronto, o que não foi visto, e as perguntas pendentes.

## 9. Conferência EM MOVIMENTO (todos os perfis, sem exceção)
Quadros parados não mostram texto que reflui, pisca ou pula com a câmera andando. Depois do QA e ANTES de entrar em `04-aprovado`, 2 etapas:
(a) **Detector** `python _sistema/orquestrador/movimento.py <pasta> --saida movimento.json`: o `fila.py` já roda e grava `out/<id>/movimento.json` (piscadas A→B→A) e as folhas densas em `out/<id>/movimento/`. **Limite conhecido:** é só AVISO: dispara também em vídeo bom e não pega o texto refluindo com câmera andando; não confie nele sozinho.
(b) **Folhas de quadros densos olhadas pelo revisor** (obrigatório): 1 quadro a cada 0,25 s nas peças novas e 0,5 s no resto (`movimento.py <pasta> --densas --passo 0.25`). Procurar: texto que muda de quebra de linha, pisca ou escala torto; peça sobreposta a HUD, legenda ou sujeito; corte brusco na entrada/saída; legenda sumindo sem motivo; peça fora do tema. Qualquer achado reprova e volta para refazer.

## 10. YouTube (cross-post): checagem antes de enviar
**Molde único da descrição do YouTube:** o molde é do sistema (`crosspost.py → textos`), igual para todo perfil, venha a legenda do Instagram como vier: título (sem #Shorts) + descrição com EXATAMENTE 3 linhas numeradas `1. 2. 3.` (a 1ª não repete o título; corpo de 120 a 450 caracteres) + linha em branco + 6 hashtags (3 fixas do perfil + 3 variáveis, `hashtags.py`) + `#Shorts`; as `tags` do vídeo são as 6 hashtags; idioma do perfil; playlist do formato. Grave `script.json → tema` (chave de `hashtags.por_tema`) para as variáveis combinarem com o assunto.

- `crosspost.py → confere_yt` **reprova o envio** (nada sobe) se: título > 100 caracteres ou com `#Shorts`; descrição repete o título na 1ª linha, tem 3 quebras seguidas, tem link ou não termina em hashtags; tradução com a última linha (hashtags) diferente da original; capa 16:9 ausente, fora de 1280×720, > 2 MB, com o título saindo pela borda direita ou ilegível em 320 px.
- Idioma do vídeo e do áudio = `perfil.yaml → crosspost.youtube.idioma`, ou, se não houver, `idioma_conteudo` do perfil.
- **Não coberto pela checagem:** letras cortadas na borda de cima/baixo da capa 16:9; conferir olhando a capa em tamanho grande ao criar um perfil novo.
- **Conferência depois do envio:** `crosspost.py → conferir_no_ar` lê o vídeo no ar e compara título, descrição, idioma, categoria, privacidade, traduções e playlist; se divergir, corrige e grava em `cross_youtube.json → conferencia`. Qualquer erro DEPOIS do vídeo criado vira `erro_pos_envio` (o `video_id` nunca se perde, senão o reenvio duplica o vídeo). Conferir à mão: `python _sistema/orquestrador/crosspost.py conferir-no-ar <id> --perfil <pasta> [--corrigir]`. **Dublagem automática não tem API**: só manual no Studio.
- **Envio que falha:** falha antes do vídeo existir não deixa nada no canal; o upload só cria o vídeo quando termina. Falha de rede NO MEIO do envio pode deixar vídeo à toa: conferir o canal no Studio se um envio der timeout.
- Cota: 10 mil unidades/dia por projeto do Google; envio ≈ 1.600, atualização 50, capa 50. Pacote de canal (país, idioma, palavras-chave) é feito à mão no Studio.

- **SFX de transição = só um bafinho, e variado**: 30 dB abaixo dos sons da história, banco de ≥ 6 variações, nunca a mesma duas vezes seguidas nem as 3 últimas da edição anterior; vídeo só com efeitos usa `audio.final_lufs` mais baixo. Texto completo: `_sistema/audio-mix.md`.
