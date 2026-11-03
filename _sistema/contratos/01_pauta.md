# 01 · Pauta

**Entradas:** `<perfil>/pautas.csv`, `<perfil>/formatos.md`, `<perfil>/out/*/brief.json` dos últimos 90 dias

**Saída:** `brief.json` (schema `schemas/brief.schema.json`): tema, ângulo, formato escolhido e as fontes (perfil de fatos)

**Gate (passa se):** Tema não usado em 90 dias; formato existe no `formatos.md` e não está `cortado` (prioridade para os `ativo`, ver `automacao.md §9`); formato respeita a alternância do perfil (`qualidade.formato_varia`, `qualidade.montagem_varia`); perfil de fatos com 2 fontes confiáveis que dizem a mesma coisa.

**Proibido:** Inventar fato; repetir tema; usar tema fora do nicho do guia.

**Se reprovar:** corrigir e tentar de novo até o limite de `_sistema/automacao.md §3` (QA: máx. 5 rodadas no total); depois gravar `fail.json` com etapa, motivo e últimas saídas, e parar.
