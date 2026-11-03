<!-- Etapas da producao automatica de {{HANDLE}}. O orquestrador encaixa este texto no produzir.md (chaves: {id} {handle} {pasta} {perfil} {idioma} {cta_modo}). -->
Referencia: veja `{perfil}/estilo-extraido.md` (o estilo aprovado) e, quando existir, a primeira edicao aprovada em `{perfil}/out/`.

## Etapas (cada uma grava na pasta da edicao)
1. **Pauta.** Confirme o fato com 2 fontes confiaveis que digam a mesma coisa; complete o `brief.json` (fontes, numero final, frase de fecho). Fato duvidoso: troque o angulo ou grave `fail.json` e pare.
2. **Roteiro.** Siga o formato do `formatos.md`. Primeira frase com no maximo 10 palavras, prende em 2 s, sem "ola" nem vinheta. Cada frase traz decisao, porque, numero ou virada. Marque o momento da **pausa de seguir** conforme `perfil.yaml → ritmo.seguir`. Grave `narracao.txt` com tags de emocao em toda frase (se o perfil tem voz).
3. **Voz.** Conector do ElevenLabs (`voz` do `perfil.yaml`), 1 geracao; depois `python _sistema/orquestrador/voz_words.py {pasta}/voice.mp3 {pasta}/narracao.txt {pasta}` (gate em `voz_check.json`). Perfil sem `voz`: pule.
4. **Cena.** Escreva o `script.json` (schema em `_sistema/schemas/script.schema.json`): `gancho`, `seguir {t, dur, texto}`, `hud` (se ligada), `dados`/`inserts`, `capa`, `caption`. Use as cenas de `{perfil}/remotion/src/` e os tokens de `estilo.ts`. Confira um still de CADA plano antes de renderizar e corrija tudo de uma vez.
5. **Mix e render.** `python _sistema/orquestrador/mix.py {pasta}` e `python _sistema/orquestrador/render.py {pasta}` (precisam de `"passou": true`).
6. **QA.** `python _sistema/orquestrador/qa.py preparar {pasta}`, avaliadores independentes, `qa.py julgar {pasta}`. Corte 6,8, maximo 5 rodadas. Depois, folhas de quadros densas do `video.mp4` (`movimento.py`).
7. **Fila.** `python _sistema/orquestrador/fila.py {pasta}`.
