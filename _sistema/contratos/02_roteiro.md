# 02 · Roteiro

**Entradas:** `brief.json`, `<perfil>/style-guide.md`, `<perfil>/format.json`, `<perfil>/formatos.md` (promessa e gancho do formato escolhido)

**Saída:** `script.json` (schema `schemas/script.schema.json`): planos com tempo, fala, texto de tela, câmera, personagem, cenário, inserts

**Gate (passa se):** Valida no schema; o gancho e o payoff seguem o formato do `formatos.md`; todas as batidas do formato presentes na ordem; contagem de palavras e duração dentro de `format.json`; cada plano tem um plano de câmera diferente do anterior.

**Proibido:** Pedir salvar/comentar fora do card de seguir e da chamada do perfil (`script.seguir`, `script.cta`); roteiro raso (cada frase traz decisão, porquê, número ou virada); jargões listados em "nunca" do guia; mais de uma ideia por vídeo.

**Se reprovar:** corrigir e tentar de novo até o limite de `_sistema/automacao.md §3` (QA: máx. 5 rodadas no total); depois gravar `fail.json` com etapa, motivo e últimas saídas, e parar.
