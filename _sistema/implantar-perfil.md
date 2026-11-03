# Implantar um perfil novo na automação

> Para usar num **chat novo**: abra o Claude Code na raiz do projeto e diga *"implante o perfil `<pasta>` seguindo `_sistema/implantar-perfil.md`"*. Este arquivo tem tudo que o chat precisa.
> **Perfil que ainda não existe:** `python _sistema/orquestrador/criar_perfil.py <pasta> --handle @meu.perfil [--prefixo mpf] [--idioma en] [--nicho "..."]` copia o `_modelo-perfil/` e registra a pasta em `perfis.yaml → ordem`. Depois: referências em `<pasta>/refs/` + `refs.py` para analisar o estilo, e o guia de identidade aprovado (`guia.html`) antes de produzir. Passo a passo completo para a pessoa: `GUIA/index.html`.

## O que já está pronto e serve para qualquer perfil (não refazer)
| Peça | Arquivo |
|---|---|
| Orquestrador (pauta, sessão `claude -p`, reserva da fila) | `_sistema/orquestrador/orquestrador.py` + `produzir.md` |
| Voz (ElevenLabs via MCP) + tempos por palavra | contrato 03 + `voz_words.py` |
| Mix com ducking e gate de áudio | `mix.py` (valores por perfil em `<perfil>/perfil.yaml → audio`) |
| Render + capa + folha de contato + anti-piscada | `render.py`, `piscadas.py` |
| QA visual (3 subagentes, mediana, máx. 5 rodadas) | `qa.py` |
| Gates universais da fila (gancho, liga_ao_fato, seguir, card_final, area_segura, piscadas, audio, hud, variacao) | `gates_universais.py` (ajustes em `perfil.yaml → ritmo / qualidade`) |
| Legenda lição rápida + hashtags 3+3 | `_sistema/legenda.md`, `hashtags.py` (conferidos pelo `fila.py`) |
| Fila e post pela Graph API | `fila.py`, `post.py` |
| Token da Meta | `meta_token.py` |
| Agendador do Windows | `_sistema/agendador.ps1` |
| Painel | `_sistema/painel/painel.py` |
| DM automática (opcional, só com oferta) | `dm.py` (oferta e textos no `perfil.yaml` do perfil) |

## O que cada perfil precisa de próprio (é aqui que o trabalho está)
1. **`perfil.yaml`** — preencher as chaves de `_sistema/orquestrador/CHAVES-PERFIL.md` (o modelo já vem com o essencial: handle, prefixo, horários, composição, ritmo, qualidade, legenda, QA, grade, hashtags, voz).
2. **Voz** — 3 candidatas pelo MCP do ElevenLabs que batam com o guia; o dono escolhe ouvindo a mesma frase; gravar `voz: {voice_id, modelo}` no `perfil.yaml` do perfil. Perfil sem narração: apagar o bloco `voz` (a etapa 3 é pulada).
3. **Sons em código** — trilha e SFX do guia gerados por script na pasta do perfil (`<perfil>/assets/audio/`), com banco de ≥ 6 variações de transição (`_sistema/audio-mix.md §7`).
4. **Cena** — composição Remotion do perfil em `<perfil>/remotion/` (o modelo traz `Edicao.tsx`, `Capa.tsx`, `base/`, `cenas/`, `estilo.ts`). Trocar o estilo pelo do guia do perfil. O `render.py` lê a composição por `perfil.yaml → composicao: {edicao, capa}`. Toda composição aceita as props `{script, words}`, `capa: true` e `soOverlay` (o `piscadas.py` usa para medir só textos/HUD/inserts).
   - Obrigatório em todo vídeo (viram gate): **gancho** nos primeiros segundos, **HUD interativa** no estilo do perfil (se `qualidade.hud`), inserts de dado, legenda em blocos que acendem com a voz, **card de seguir** e **card final** (`ritmo.seguir`, `ritmo.card_final`), **área segura do feed 4:5** (y ≈ 285–1635), **nenhuma piscada**, som por plano + ambiente contínuo + ducking suave (`<perfil>/perfil.yaml → audio`).
   - **Capa pôster** com o texto na arte, inteira no corte 3:4, com o ciclo de cores em `<perfil>/perfil.yaml → grade.ciclo`; simular a grade 3 × 2 antes de aprovar o modelo (`capa_grade.py`).
   - **Variar a execução**: banco de cenários/variações no `<perfil>/formatos.md` e checagens em `<perfil>/perfil.yaml → qualidade`.
   - Criar `reviews/aprendizados.md` (toda produção lê e escreve) e `versoes/` (o `render.py` guarda cada render).
5. **Etapas de produção do perfil** — `<perfil>/producao.md` (entra no prompt da sessão; pode citar `{id}`, `{handle}`, `{pasta}`, `{perfil}`, `{idioma}` e `{cta_modo}`).
6. **Gates próprios (opcional)** — regra que só vale para este perfil vai em `<perfil>/gates.py` (`gates(ctx) -> list`, `CHAVES-PERFIL.md §13`); defeito crônico do QA vai em `<perfil>/gate_comum.py`; textos próprios dos itens do QA em `<perfil>/qa_itens.json`.
7. **Edição de teste** — fazer a 1ª edição com o dono olhando, passar no QA e nos gates, e só então rodar a 2ª sozinha pelo orquestrador.
8. **Meta** — siga `_sistema/briefs/configurar-meta.md`: Instagram profissional ligado a uma Página do Facebook, app da Meta com as permissões de `regras-gerais.md §7`, token curto → `python _sistema/orquestrador/meta_token.py --perfil <prefixo>` → `post.py checar --perfil <prefixo>`.
9. **DM (só se houver oferta)** — no Instagram do perfil: Configurações → Mensagens → Ferramentas conectadas → permitir acesso às mensagens. Preencher `oferta` e `legenda_cta`, tirar `sem_cta_sempre`, testar (`dm.py --perfil <prefixo> --teste-link <url>`) e ligar `oferta.dm_ativa: true` (`_sistema/palavras-comentario.md`).
10. **Teste no ar** — assim que o perfil estiver pronto, publicar a 1ª edição (`post.py publicar <item>`) e conferir a capa no Instagram e o feed (`feed_check.py <pasta>`).
11. **Ligar** — `producao_auto: true` no `perfil.yaml` do perfil (o agendador produz a cada 30 min nos perfis com essa chave e fila abaixo de `fila_alvo`; não mexer no `agendador.ps1`). Atenção ao tempo por edição e ao crédito de voz.

## Regras aprendidas (não repetir os erros)
- Conferir um still de **cada** plano antes de renderizar; corrigir tudo de uma vez. Máximo 5 rodadas de QA.
- Fundo vivo e assunto reconhecível em 1 s são o que mais reprova no QA.
- Nada recriado por frame (geometria/material fixos), senão pisca.
- Áudio e vídeo para o dono: abrir no Explorer **e** enviar; arquivo > 30 MB vai com prévia comprimida.
- Sessão `claude -p` no Windows: chamar o `claude.exe` direto, prompt pela entrada padrão, ferramentas por `--allowedTools` (já está no orquestrador; MCPs em `perfis.yaml → padrao.ferramentas_mcp`).

## Área segura do feed (automática)
Todo perfil novo: `qualidade.area_segura` no `perfil.yaml` (e `qualidade.area_feed: true` para a medida por pixel). A geometria do ASSUNTO (não só texto/HUD) também conta: base/pés/sombra até y 1620 e topo a partir de y 300 no 1080×1920; se o gate universal não cobre o estilo do perfil, a checagem vai no `<perfil>/gates.py`. Sem esperar o dono avisar.

## Flags do perfil.yaml ligadas à chamada
`sem_cta_sempre: true` (perfil sem oferta: nenhuma chamada para comentar; padrão do modelo), `ab_sem_cta_padrao: true` (edição sem `script.cta` sai SEM CTA). Também: `composicao:` (o `render.py` para se faltar `composicao.edicao`) e `qa_itens.json` opcional na pasta do perfil.
