---
name: analisar-refs
description: Extrai o estilo de vídeos de referência (pasta refs/ + links) de um perfil e o transforma em estilo-extraido.md e tokens do Remotion. Use depois de refs.py analisar, ou quando a pessoa pedir "copie o estilo destes vídeos".
---

# Analisar referências e replicar o estilo (100% em código)

Entrada: `<pasta>/refs/_analise/RESUMO.json` + as folhas PNG de cada vídeo (`folha-gancho.png`, `folha-geral.png`). Se não existir, rode `python _sistema/orquestrador/refs.py analisar <pasta>`.

1. **Olhe as imagens** (Read nas folhas), não só os números. Refs são forma de pensar: entenda o **porquê** de cada recurso, não copie quadro a quadro.
2. **Descreva em `<pasta>/estilo-extraido.md`** (curto, com exemplos por quadro):
   - paleta (use `paleta` do RESUMO como ponto de partida; dê papéis: fundo, destaque, texto)
   - tipografia (peso, caixa, tamanho relativo, posição), legenda (blocos? palavra a palavra?)
   - câmera (cortes por 10 s, zoom/paralaxe/tilt), ritmo e duração típica
   - gancho dos 3 s: o que aparece, em que quadro, como entra
   - como o vídeo pede para seguir (e onde); card final
   - tipo de cena/personagem/mundo, HUD ou elementos fixos, efeitos de textura/grão
   - som: voz? trilha? SFX? (o `lufs` mede o volume)
   - o que NÃO copiar (marca, rosto, logotipo de terceiros) e o que torna este perfil original
3. **Traduza em código**: preencha `<pasta>/remotion/src/estilo.ts` (tokens) e crie as cenas do estilo em `src/cenas/` reaproveitando `src/base/` (legenda, HUD, CardSeguir, GanchoAbertura, Fundo vivo, Camera3D). Sem gerador de imagem. Sem aleatório no render.
4. **Mapa de variação**: liste em `<pasta>/formatos.md` os formatos/pilares do perfil e o que varia entre edições (desenho do card, HUD, tarja, cena). Regra: o que repete mantém a animação, muda o desenho.
5. **Prove com a folha**: renderize 3 capas + 1 cena de 3 s + grade 3×3; compare lado a lado com as refs e corrija até bater (máx. 5 rodadas, tudo de uma vez). Mostre à pessoa; só avance com o OK.
6. **Registre**: `RETOMAR.md` do perfil (o que foi aprovado, o que falta).

Se a análise der pouco material (poucos vídeos, baixa qualidade), peça mais refs em vez de inventar estilo.
