# Projeto Remotion neutro (modelo de perfil)

Esqueleto sem estilo travado. Ao criar um perfil, o Claude copia esta pasta para `<perfil>/remotion/` e a **reveste** com o estilo extraído dos vídeos de referência.

**Regra:** toda arte é feita em código (React, SVG, CSS, Three.js se precisar). Nada de gerador de imagem ou de vídeo.

## Composições (o `render.py` chama por estes nomes)
- `Edicao`: 1080×1920, 30 fps. A duração vem de `script.duration_s`. Props: `{script, words, capa?, soOverlay?}`.
- `Capa`: pôster 1080×1920 de 1 quadro. Lê `script.capa`.

No `perfil.yaml` do perfil, declare (sem isto o `render.py` cai nos nomes de outro perfil):
```yaml
composicao: {edicao: Edicao, capa: Capa, cena: codigo}
```

## Onde mexer para revestir o estilo
1. **`src/estilo.ts`**: paleta, fontes, tamanhos, durações, easing, raios, posições, câmera. É o primeiro e o principal lugar. Os componentes só leem daqui.
2. **`src/cenas/`**: troque `exemplo.tsx` pela cena do perfil (assunto, cenário e personagens desenhados em código, a partir do roteiro de cada edição). Depois aponte `src/Edicao.tsx` para a cena nova.
3. **`src/base/`**: mude o desenho dos componentes (forma da HUD, da caixa, da tarja e dos cards) quando o guia pedir, mas mantenha as props e as regras abaixo. Para variar por edição, sorteie com `sorteio(semente)`.
4. **`src/Capa.tsx`**: capa por tipo de vídeo. A cor vem de `script.capa.fundo`, que segue o ciclo da grade. O texto fica no corte 3:4 e longe dos ícones do Instagram.

## Peças de `src/base/`
| Peça | O que faz |
|---|---|
| `Legenda` | Blocos de legenda que acendem palavra por palavra com a voz (`words.json`: `{w,start,end}`). O texto não reflui. |
| `Hud` | Pequena e fixa no canto. O slot é configurável (rótulo e valores no tempo, ou `children`). |
| `Insert` | Dado ou número grande com rótulo (`script.dados`). |
| `CardSeguir` | Pausa para pedir para seguir (`script.seguir = {t, dur}`). |
| `CardFinal` | Card com a oferta no final (`script.oferta.card`). Dura ≥ 1,6 s depois da última palavra. |
| `GanchoAbertura` | Primeiros 3 s: o assunto grande, que se lê em 1 s sem legenda. Já aparece no quadro 0 e se mexe. |
| `AreaSegura` | `prenderY`, `NaAreaSegura` e `GuiaAreaSegura`. Mantêm texto, HUD e cards em y 285–1635. |
| `Camera3D` / `Camada` | Camadas em profundidade com paralaxe. Movimentos: push, pull, pan, tilt, orbita e fixa. |
| `Fundo` | Gradiente vivo na paleta, com luz que passeia e vinheta. |
| `anim.ts` | `presenca()` (entra e sai) e `sorteio()`, o aleatório com semente. |

## Regras que o código precisa manter
- **Sem piscada:** nada de `Math.random` ou `Date.now` no render. Use `sorteio(semente)`. Geometria, material e listas são criados uma vez. Elemento entra e sai por opacidade, nunca montando e desmontando a cada quadro.
- **`soOverlay`:** com esta prop, desenhe só textos, HUD, inserts e cards sobre preto. O `piscadas.py` usa esse modo.
- **Fonte própria:** carregue antes do primeiro quadro (`@remotion/google-fonts` ou `@remotion/fonts`, ou `delayRender`). Fonte que chega no meio do render faz o texto pular.
- **Área segura:** todo texto passa por `NaAreaSegura` ou `prenderY`.

## Testar
```
npm install
npx tsc --noEmit
npx remotion still src/index.ts Edicao out/teste.png --frame=45
npx remotion render src/index.ts Edicao out/teste.mp4 --frames=0-89 --muted
npx remotion studio src/index.ts
```
Sem `--props`, as composições usam o exemplo de `public/exemplo/` (`script.json` e `words.json`).
