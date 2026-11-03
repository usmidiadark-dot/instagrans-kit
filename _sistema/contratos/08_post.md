# 08 · Post

**Quem faz:** script, sem sessão do Claude: `python _sistema/orquestrador/post.py proximo` (agendador, nos horários do perfil).

**Entradas:** item da fila (`posts/04-aprovado/*.json`), `IG_USER_ID_<X>` e `IG_TOKEN_<X>` do `.env`.

**Saída:** `<perfil>/out/<id>/post.json` com container_id, media_id, permalink e horário; o item vai para `posts/05-publicado/`.

**Antes de postar (o script confere):** vídeo MP4 H.264 + AAC, 9:16, 3 s–15 min, 23–60 fps, ≤ 300 MB; legenda não vazia e ≤ 2.200 caracteres, pela regra de `_sistema/legenda.md` (COM CTA: o `post.py` confere e nunca põe a linha de chamada no topo; emoji diferente do `cta.emoji_tema` é trocado no lugar, item sem o campo vale como está; tema de 1 a 3 emojis fora da regra "bonito sem brega" bloqueia o post); perfil não pausado; o token é da conta certa (`username` = handle); cota de publicação. `post.py checar` faz só essa parte (leitura) e avisa se o token vence em menos de 7 dias.

**Gate (passa se):** contêiner `FINISHED`, `media_publish` devolve o ID e o permalink responde.

**Proibido:** postar com `pausado: true`; postar dois vídeos do mesmo perfil na mesma execução; token fora do `.env`.

**Se reprovar:** 3 tentativas com 10 min entre elas; depois `fail.json` em `out/<id>/`, o item fica na fila e sai alerta.
