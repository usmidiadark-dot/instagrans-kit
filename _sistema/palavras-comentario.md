# Palavra de comentário por vídeo — regra de todo perfil com oferta

> Só vale para perfil com oferta ligada (COM CTA). Perfil sem oferta usa `perfil.yaml → sem_cta_sempre: true` e o final de SEGUIR; aí nada deste arquivo se aplica. Código: `cta_video.py` (card, fala e linha da legenda por vídeo), `dm.py` (casa a palavra só no post dono dela; `--dry-run` testa sem enviar), `fila.py` (`confere_cta_video`), `legenda_cta.py` (linha da legenda). Chaves: `CHAVES-PERFIL.md §7`.

## 1. A regra
1. Todo vídeo tem a **sua palavra de comentário**, nascida do assunto dele, **diferente da do vídeo anterior e sem repetir nas últimas 10 edições do perfil**.
2. 3 a 7 letras, uma palavra só, fácil de digitar no celular, que **nomeia o que a pessoa vai receber**. Evite palavras que as pessoas comentam sem querer (WOW, YES, nomes de banda/marca/pessoa) e **não repita a de outro perfil** (as palavras fixas de `oferta.palavra` e de `padrao.curso` ficam reservadas entre os perfis).
3. A **promessa** (o que vem depois de "I'll send you") aponta para a **parte do produto** ligada ao tema do vídeo (`oferta.secoes`, se o produto tem seções). Nunca preço, "free", "course" nem "link in bio".
4. A mesma palavra e a mesma promessa aparecem em 4 lugares do MESMO vídeo: (a) a **última frase falada** ("Comment PALAVRA and I'll send you …"), (b) o **card final animado**, (c) a **linha de chamada no corpo da legenda** (regra e emoji do tema em `_sistema/legenda.md §5`), (d) a **DM** que a pessoa recebe.
5. A **DM é por palavra** (fala do vídeo e leva à seção do produto, `oferta.dm_por_video` + `oferta.link_dm_base`/`oferta.ancoras`) e a **resposta pública** varia (3 a 5 frases, `oferta.respostas_publicas`) para não parecer robô.
6. `dm.py` casa cada palavra **só nos comentários do post que é dono dela** (pelo `media_id` gravado em `out/<id>/post.json` + `script.json → cta`) e responde uma vez por comentário. A palavra fixa do perfil (`oferta.palavra`) e a do curso continuam valendo nos posts antigos.
7. `fila.py`/`post.py` reprovam: sem palavra; palavra repetida das últimas 10; fora de 3–7 letras; igual à de outro perfil; promessa com preço/"free"; a palavra da legenda diferente da do card ou da narração; e as regras da linha de chamada de `_sistema/legenda.md §9`.

## 2. O final do vídeo (gancho para comentar)
- **Áudio da narração + animação + texto do card**, os três juntos: a última frase falada diz a palavra, e o card final **escreve a palavra no instante em que a voz a diz** (sincronizado com `words.json`), com a promessa ao lado.
- Cada perfil faz a versão na **sua linguagem visual** (no estilo da HUD e do guia). Gates: `card_final` (≥ `ritmo.card_final_min_s` depois da última palavra), área segura do feed, texto ≥ tamanho mínimo do perfil.

## 3. Teste A/B com e sem CTA (opcional)
`format.json → ab_cta {desde, comeca}` alterna edições COM e SEM CTA (`brief.json → cta`); a edição SEM CTA não tem palavra, card nem chamada falada. `perfil.yaml → ab_sem_cta_padrao: true` faz a edição sem `script.cta` sair SEM CTA.

## 4. Votação no lugar da oferta (opcional)
Perfil sem oferta pode usar `dm_so_votacao: true`: o comentário com uma das 2 palavras de `script.votacao.opcoes` vota, a resposta pública confirma o voto, a votação fecha sozinha (`votacao_fecha_h`, padrão 24 h) e a vencedora vira pauta prioritária.

## 5. Ligar num perfil novo
1. Preencher `oferta` no `perfil.yaml` (palavra fixa de reserva, card, textos da DM, links) e `legenda_cta` (banco de frases e emojis).
2. Testar a DM com `dm.py --perfil <prefixo> --dry-run` e depois `dm.py --perfil <prefixo> --teste-link <url>` com um comentário de uma conta pessoal.
3. Só então `oferta.dm_ativa: true`. As edições já na fila ou postadas seguem com a palavra que tinham.
