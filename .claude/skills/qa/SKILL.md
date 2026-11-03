---
name: qa
description: Faz o QA de uma edição pronta (nota por item, folhas de quadros densas, gates da fila). Use quando a pessoa pedir "confira", "QA", "pode postar?".
---

# QA de uma edição

1. Rode `python _sistema/orquestrador/fila.py` para o perfil (gates automáticos) e leia o que reprovou.
2. Gere/abra as folhas de movimento: `python _sistema/orquestrador/movimento.py <pasta-da-edicao> --densas --passo 0.25` (0,25 s em peça nova; padrão 0,5 s). Olhe as imagens: texto que reflui, pisca ou pula só aparece assim.
3. Dê nota 0–10 em: assunto reconhecível em 1 s, fundo, capa, HUD, ação, variação, e a média. **Corte 6,8 em todos.** Defeito grave reprova; defeito leve vira recomendação.
4. Confira o gancho (0–3 s), a pausa de seguir, a área segura (y 285–1635), áudio (voz na frente, ducking) e a capa na grade real (`feed_check.py`).
5. Reprovou: liste TUDO de uma vez, corrija e refaça (máx. 5 rodadas). Aprovou: diga o que foi visto e o que não foi.
