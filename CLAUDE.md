# INSTAGRANS-KIT — estúdio automático de perfis de Reels

> Lido pelo Claude Code em toda sessão aberta nesta pasta. Fale e documente em PT-BR; o idioma do conteúdo publicado é definido em cada perfil (`perfil.yaml → idioma_conteudo`).

## O que é
Um motor que cria **perfis de qualquer assunto**: você dá vídeos de referência + links, o Claude extrai o estilo, monta o modelo de vídeo em código (Remotion), e o perfil passa a produzir, passar no QA e postar sozinho.

## Primeiro, sempre
1. `REGRAS-UNIVERSAIS.md` — valem para todo perfil, sem exceção (gancho, pausa de seguir, área segura, áudio, QA…).
2. `perfis.yaml` — valores comuns (`padrao`) e a ordem dos perfis. Cada perfil tem a própria config em `<pasta>/perfil.yaml`. Edite o do perfil, não o da raiz.
3. `_sistema/orquestrador/CHAVES-PERFIL.md` — todas as chaves que o motor lê.
4. Na pasta do perfil: `RETOMAR.md` (onde paramos), `estilo-extraido.md` (fonte de verdade do estilo), `producao.md`.

## Como trabalhar com a pessoa
- Português simples, frases curtas, sem sigla nem nome de arquivo no meio da explicação; diga primeiro o que mudou na tela/no vídeo.
- Decisão que é da pessoa vai em **pergunta com opções** (`AskUserQuestion`), uma por vez, com a sua recomendação primeiro. O que o guia e o que já foi aprovado resolvem, você decide e avisa.
- Tipo novo de vídeo/formato/pilar: processo completo antes de produzir (capa por tipo, HUD/tarja/card variados e sorteados, cada regra vira checagem no `fila.py`, documentação, folha para aprovação) — só então produz.
- Fim de toda resposta: o que está pronto, o que NÃO foi visto/testado, perguntas pendentes.

## Como criar um perfil novo (skill `criar-perfil`)
Pasta nova a partir de `_modelo-perfil/` → pessoa põe vídeos em `refs/` e links em `refs/links.txt` → `refs.py analisar` → Claude olha as folhas e escreve `estilo-extraido.md` + `remotion/src/estilo.ts` → folha de aprovação → 1 edição de teste com a pessoa olhando → QA → liga `producao_auto`.

## Regras de execução
- Toda arte em código (Remotion/React/SVG/Three.js). Sem gerador de imagem ou vídeo, a menos que a pessoa autorize por escrito no `perfil.yaml`.
- Nada recriado por frame (sem `Math.random` no render), senão pisca.
- Nunca postar, mandar DM ou publicar sem `producao_auto`/`aprovacao` ligados no perfil. Testes nunca postam.
- Segredos só no `.env` (nunca no código, nunca no chat). Cada pessoa usa as próprias contas.
- Não renomear pastas de perfil depois de criadas (código e agendador usam o nome).
- **Trava por edição:** antes de mexer numa edição, `python _sistema/orquestrador/travas.py pegar <id>`; saída 3 = outra conversa está nela.
- Conversa longa: atualize o `RETOMAR.md` do perfil e peça à pessoa /compact ou /clear.
- Repita de vídeo para vídeo o que funcionou, melhore o que não: cada edição lê e escreve `reviews/aprendizados.md`.

## Pastas
```
INSTAGRANS-KIT/
  CLAUDE.md  REGRAS-UNIVERSAIS.md  perfis.yaml  .env  instalar.ps1  GUIA/index.html
  _sistema/  orquestrador/ (motor)  contratos/  painel/  schemas/  templates/
  _modelo-perfil/   modelo vazio (remotion/ neutro + perfil.yaml)
  <pasta-do-perfil>/  perfil.yaml  refs/  estilo-extraido.md  producao.md  pautas.csv  remotion/  out/  posts/
```
