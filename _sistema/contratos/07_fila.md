# 07 · Fila

**Entradas:** tudo acima (vídeo aprovado no QA, roteiro, legenda do perfil)

**Saída:** `<perfil>/posts/04-aprovado/<AAAA-MM-DD_HHMM>.json`:
```json
{"id": "<prefixo>-001", "horario": "2026-01-15 17:30", "video": "<pasta>/out/<prefixo>-001/video.mp4",
 "legenda": "<título> ... #fixa1 ...", "capa_offset_ms": 1000}
```
`horario` no fuso de `perfis.yaml → padrao.fuso`.

**Gate (passa se):**
- **Gates universais** (`_sistema/orquestrador/gates_universais.py`, ajustes em `perfil.yaml → ritmo / qualidade`): `gancho` (texto e voz até 1 s, movimento na janela do gancho; exceção `ritmo.abertura_calma` ou `out/<id>/abertura_excecao.json`), `liga_ao_fato` (explicador e inserts sorteados com 1 frase ≥ 20 caracteres citando o assunto), `seguir`, `card_final`, `area_segura`, `piscadas`, `audio`, `hud`, `variacao`.
- **Gates do perfil** (`<perfil>/gates.py`, se existir; `CHAVES-PERFIL.md §13`). Exceção no plugin, arquivo sem a função `gates` ou achado fora do formato viram erro.
- **Legenda** pela regra de `_sistema/legenda.md` (lição rápida: título + 3 linhas numeradas, 120–450 caracteres; 6 hashtags = 3 fixas do perfil + 3 variáveis sem repetir nos 3 posts vizinhos, com uma linha em branco antes, `hashtags.py`; nenhuma palavra proibida; COM CTA a chamada vai no corpo, com frase e emoji variados; SEM CTA nenhuma chamada). O `fila.py` monta, confere e registra em `<perfil>/reviews/legendas.jsonl`.
- Horário é o próximo livre de `<perfil>/perfil.yaml → horarios`; `python _sistema/orquestrador/post.py publicar <item> --dry-run` sem erros de vídeo.

Achado `erro` barra a entrada; `aviso` só é impresso. Com `qa.json → aprovado_dono: true`, os erros de `area_segura` viram aviso. Os gates valem na ENTRADA da fila: o que já está em `04-aprovado` não é tirado.

**Proibido:** dois itens no mesmo horário do mesmo perfil.

**Se reprovar:** corrigir e tentar de novo até o limite de `_sistema/automacao.md §3`; depois gravar `fail.json` com etapa, motivo e últimas saídas, e parar.
