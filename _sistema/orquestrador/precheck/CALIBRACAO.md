# Precheck de texto — calibração

**O que é:** mede o texto do DOM da composição Remotion a cada 2 quadros (uma carga de página só) + contraste por pixel em stills a cada 60 quadros. ~2–3 min por vídeo de ~30 s. Uso: `python -X utf8 _sistema/orquestrador/precheck/precheck.py <pasta_da_edicao>` → `<pasta>/precheck.json` (`passou`, `erros`, `avisos`). Código: `precheck.py`, `precheck.mjs`, `medidor.ts`. Não altera a composição; o código temporário que injeta é apagado ao final.

## Regras depois da calibração
| Tipo | Gravidade | Por quê |
|---|---|---|
| `texto_sobreposto` (2 textos com caixas sobrepostas ≥ 50%, por < 10 amostras, nenhum inclinado nem escondido sob card opaco) | **ERRO** | pega legenda empilhada (2 blocos juntos por 2–3 quadros nas trocas) e card colidindo com outro texto |
| `fora_da_area_segura` (`perfil.yaml → qualidade.area_segura`, os 4 valores) | **ERRO** | sem falso alarme na calibração |
| `sobreposicao_persistente` (≥ 10 amostras), `sobreposicao_leve` (< 50%), `texto_sobreposto_girado` | aviso | textos que se tocam por poucos px, ou texto inclinado de propósito |
| `texto_coberto`, `fora_do_quadro`, `contraste_baixo`, `contraste_local_baixo`, `texto_pequeno` | aviso | decorativo/animado/por desenho: sombra e contorno enganam o contraste por pixel; rótulos pequenos de HUD são escolha de design |

## O que a calibração mostrou
- Em edições com troca de legenda seca (um bloco sai antes do outro entrar), o precheck discrimina bem: as limpas passam com 0 erros.
- Edições com troca de legenda em cruzamento reprovam pelo bloco sobreposto, mesmo tendo passado no QA visual: o precheck pega o que o olho perde em quadro parado.
- Entrada de card final com fade curto por cima de outro texto conta como erro.

## Em aberto
1. **Entrada do card final** (fade de ~0,3 s com texto fantasma por baixo) conta como erro? Hoje conta; dá para virar aviso.
2. **Contraste por pixel** segue só como aviso. Valeria um limite próprio por tipo de texto (legenda × HUD × marca desenhada).
3. **Ligar no fluxo:** ainda NÃO está no `produzir.md`/`orquestrador.py`. Sugestão: rodar entre `mix.py` e `render.py` só como relatório por algumas edições, depois virar gate. Soma ~2–3 min por edição.
4. **Cada perfil:** o `medidor` é genérico (lê o DOM); falta testar cada composição (Three.js em canvas não tem texto no DOM).
