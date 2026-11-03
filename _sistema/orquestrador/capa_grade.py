"""Simula como a capa aparece na grade do Instagram (o ícone de reel pode tampar a última letra do título e a contagem de views o canto de
baixo). Recorta o 3:4 da grade (y 240–1680) e desenha por cima o ícone de reel (canto superior direito) e a contagem de views (canto
inferior esquerdo), nas posições da grade real (medidas numa captura do app).
Uso:  python _sistema/orquestrador/capa_grade.py <cover.jpg> [saida.jpg]   → capa_grade.jpg ao lado da capa
Também: capa_grade.zonas_livres(cover.jpg) mede o quanto de TEXTO claro (creme/amarelo/tinta) cai dentro das duas zonas, para o qa.py e o render.py."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ZONAS = {"icone": (860, 262, 1040, 420), "views": (20, 1470, 500, 1600)}  # coordenadas da capa 1080×1920 (a capa do perfil deve deixar estas zonas sem texto)

def _fonte(tam):
    for n in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try: return ImageFont.truetype(n, tam)
        except OSError: pass
    return ImageFont.load_default()

def simula(cover, saida=None):
    im = Image.open(cover).convert("RGB").crop((0, 240, 1080, 1680)); d = ImageDraw.Draw(im, "RGBA")
    x0, y0, x1, y1 = ZONAS["icone"]; cx, cy = (x0 + x1) / 2 + 10, (y0 + y1) / 2 - 240 - 10
    d.rounded_rectangle((cx - 44, cy - 44, cx + 44, cy + 44), 18, fill=(255, 255, 255, 235))  # ícone de reel (quadrado branco com play)
    d.polygon([(cx - 14, cy - 22), (cx - 14, cy + 22), (cx + 24, cy)], fill=(20, 20, 20, 255))
    vx, vy = ZONAS["views"][0] + 50, (ZONAS["views"][1] + ZONAS["views"][3]) / 2 - 240
    d.ellipse((vx - 34, vy - 18, vx + 2, vy + 18), outline=(255, 255, 255, 255), width=6)  # ícone de visualização
    d.text((vx + 18, vy - 30), "1.801", font=_fonte(64), fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 160))
    saida = Path(saida) if saida else Path(cover).with_name("capa_grade.jpg")
    im.save(saida, quality=90); return saida

def zonas_livres(cover):
    """Fração de pixels 'de texto' (creme, amarelo ou tinta escura) dentro de cada zona: heurística por cor, boa para capa de fundo chapado
    colorido. Perfil com outra paleta: confira a olho no capa_grade.jpg."""
    a = np.asarray(Image.open(cover).convert("RGB")).astype(int); r = {}
    for nome, (x0, y0, x1, y1) in ZONAS.items():
        z = a[y0:y1, x0:x1]; R, G, B = z[..., 0], z[..., 1], z[..., 2]
        creme = (R > 235) & (G > 225) & (B > 195) & (B < 240)
        amarelo = (R > 240) & (G > 215) & (B < 110)
        tinta = (R < 45) & (G < 45) & (B < 55)
        r[nome] = round(float((creme | amarelo | tinta).mean()), 4)
    return r

if __name__ == "__main__":
    print(simula(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)); print(zonas_livres(sys.argv[1]))
