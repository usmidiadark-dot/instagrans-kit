# fluxo.md — o caminho de um post (automático)

> Um post = um arquivo `.json` (`AAAA-MM-DD_HHMM.json`: id, horário, vídeo, capa, legenda, nota do QA) que anda pelas pastas de `posts/`. A pasta onde ele está É o status.
> Arquivos pesados ficam em `out/<id>/`; o `.json` só aponta para eles.

| # | Pasta | Quem move | O que acontece |
|---|---|---|---|
| 1 | `posts/01-pautas/` | sistema | tema do `pautas.csv` (ou 5 novos propostos pelo Claude quando o banco tiver < 10) |
| 2 | `posts/02-em-producao/` | sistema | roteiro (`shots/<id>.md` + `out/<id>/script.json`), voz, cena, render + mix |
| 3 | `posts/03-para-aprovar/` | sistema | QA técnico + QA visual (`_sistema/contratos/06_qa.md`) |
| — | `posts/03-reserva/` | sistema | só em perfil com `serie`: edição pronta que espera a vez do personagem |
| 4 | `posts/04-aprovado/` | sistema (se o QA e os gates passaram) | fila: legenda, hashtags e horário prontos |
| 5 | `posts/05-publicado/` | sistema | publicado pela Graph API; link e horário real gravados |
| 6 | (no mesmo arquivo) | sistema | métricas 48 h e 7 dias pelos Insights da Graph API; lição em `reviews/` e em `formatos.md` (ver `automacao.md §9`) |

Reprovado no 3: volta para 2 com o motivo em `revisoes:` (até a 5ª rodada de QA no total). Na 5ª reprovação: `reviews/falhas/` + alerta. Reprovado nos gates da fila (universais ou `<perfil>/gates.py`): não entra em 4 até corrigir.

## Agenda (fuso de `perfis.yaml → padrao.fuso`)
- Produção a cada 30 min: sempre que a fila de `04-aprovado/` de um perfil com `producao_auto: true` fica abaixo de `fila_alvo` (reserva mínima), completa a fila.
- Posts: nos horários de `<perfil>/perfil.yaml → horarios`.
- Semanal: relatório da semana + decisão dos formatos (`formatos.md`: ativo / em teste / cortado) + atualização do `RETOMAR.md` de cada perfil.

## Cuidados técnicos
- Listar filas sempre ignorando `._*`: `find posts/04-aprovado -name '*.json' -not -name '._*'`.
- Um perfil por sessão de produção; o `CLAUDE.md` do perfil é o contexto daquela sessão.
