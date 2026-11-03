---
name: produzir
description: Produz uma edição (reel) de um perfil já aprovado, do roteiro ao arquivo pronto, e passa no QA. Use quando a pessoa pedir "produza", "faça o próximo vídeo", ou ao retomar a fila.
---

# Produzir uma edição

1. `python _sistema/orquestrador/travas.py pegar <id>` (saída 3 = outra conversa está nela: pare).
2. Leia `<pasta>/RETOMAR.md`, `estilo-extraido.md`, `reviews/aprendizados.md`, `producao.md` e `REGRAS-UNIVERSAIS.md`.
3. Pauta (`pautas.csv`) → roteiro com gancho em 0–3 s, decisão/porquê/número/virada por frase, pausa de seguir no momento do perfil (contrato `_sistema/contratos/02_roteiro.md`).
4. Voz (conector ElevenLabs, com tags de emoção por frase) → tempos por palavra (`voz_words.py`) → cena Remotion do perfil → render → SFX medidos no render → mix.
5. Antes do render final: um still de cada plano; corrija tudo de uma vez.
6. QA: `python _sistema/orquestrador/qa.py` (corte 6,8; máx. 5 rodadas) e folhas de quadros densas do `video.mp4`.
7. Fila: `python _sistema/orquestrador/fila.py` confere os gates. Só aprovado vai para `posts/04-aprovado`.
8. Escreva em `reviews/aprendizados.md` o que funcionou/falhou; solte a trava (`travas.py soltar <id>`).

Sem `producao_auto`/aprovação ligados no perfil, **nunca poste**.
