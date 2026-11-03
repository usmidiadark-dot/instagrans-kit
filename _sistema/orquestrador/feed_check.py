"""Confere o FEED REAL do Instagram contra o ciclo de cores da grade (rodar sempre que mexer em vídeos/capas, antes de dar a tarefa por
completa). Só leitura.
Lê os reels publicados pela Graph API, mede a cor de fundo de cada capa (borda esquerda, parte de baixo) e confere:
  1. da mais antiga para a mais nova, cada cor é a seguinte do ciclo (perfil.yaml → grade.ciclo);
  2. a fila (04-aprovado) continua a partir da última cor do feed, em ordem de horário, e a capa de cada uma (script.json e cover.jpg) bate;
  3. quantos posts o Instagram tem x quantos o 05-publicado conhece.
Uso:  python _sistema/orquestrador/feed_check.py <perfil_pasta ou prefixo>      (saída 0 = ok, 1 = problema)"""
import io, json, pathlib, sys
import requests, yaml
from PIL import Image
import post  # credenciais, api

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _hex(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def _ys(p):
    """perfil.yaml → grade.amostra_y: linhas (fração da altura) onde medir (capa com moldura/arte clara embaixo: use a faixa de cima)."""
    return tuple((p.get("grade") or {}).get("amostra_y") or (0.78, 0.80, 0.82))

def _xs(p):
    """perfil.yaml → grade.amostra_x: colunas de pixel onde medir o fundo (capa com moldura nas bordas: afaste da borda)."""
    return tuple((p.get("grade") or {}).get("amostra_x") or (4, 8, 12))

def cor_da_capa(img, ciclo, xs=(4, 8, 12), ys=(0.78, 0.80, 0.82)):
    """Cor do ciclo mais próxima do fundo da capa (amostra na borda esquerda, 80% da altura: fora da janela, do selo e do contador de views)."""
    im = img.convert("RGB"); w, h = im.size
    px = [im.getpixel((x, int(h * y))) for x in xs for y in ys]
    m = tuple(sorted(c[i] for c in px)[len(px) // 2] for i in range(3))
    dist = lambda c: sum((a - b) ** 2 for a, b in zip(m, _hex(c)))
    return min(ciclo, key=dist), m

def conferir(perfil_pasta):
    p = next((x for x in post.CFG["perfis"] if perfil_pasta in (x.get("pasta"), x.get("prefixo"), x.get("handle"))), None)
    if not p: sys.exit(f"perfil não encontrado: {perfil_pasta}")
    ciclo = [c.upper() for c in (p.get("grade") or {}).get("ciclo") or []]
    problemas, linhas = [], []
    if len(ciclo) < 2: return {"ok": True, "obs": "perfil sem ciclo de cores (capa única): nada a conferir", "problemas": []}
    uid, tok, falta = post.credenciais(p)
    if falta: return {"ok": False, "problemas": [f"faltam no .env: {', '.join(falta)}"]}
    midia = post.api("GET", f"{uid}/media", params={"fields": "id,timestamp,thumbnail_url,media_url,media_type,permalink", "limit": 50, "access_token": tok})["data"]
    reels = sorted(midia, key=lambda m: m["timestamp"])  # da mais antiga para a mais nova
    cores = []
    for m in reels:
        url = m.get("thumbnail_url") or m.get("media_url")
        try: c, med = cor_da_capa(Image.open(io.BytesIO(requests.get(url, timeout=60).content)), ciclo, _xs(p), _ys(p))
        except Exception as e: problemas.append(f'{m["permalink"]}: não consegui ler a capa ({e})'); c, med = None, None
        cores.append(c); linhas.append((m["timestamp"][:16], m["permalink"], c, med))
    # 1. sequência do feed
    for i in range(1, len(cores)):
        if cores[i - 1] and cores[i] and cores[i] != ciclo[(ciclo.index(cores[i - 1]) + 1) % len(ciclo)]:
            problemas.append(f"feed: {linhas[i][1]} ({linhas[i][0]}) está {cores[i]} depois de {cores[i - 1]}; o ciclo pede {ciclo[(ciclo.index(cores[i - 1]) + 1) % len(ciclo)]}")
    # 2. fila continua o feed
    ult = next((c for c in reversed(cores) if c), None)
    fila = []
    for f in (ROOT / p["pasta"] / "posts" / "04-aprovado").glob("*.json"):
        if f.name.startswith("._"): continue
        it = json.loads(f.read_text(encoding="utf-8")); fila.append((it["horario"], it["id"]))
    for h, ed in sorted(fila):
        if ult is None: break
        esperada = ciclo[(ciclo.index(ult) + 1) % len(ciclo)]
        s = json.loads((ROOT / p["pasta"] / "out" / ed / "script.json").read_text(encoding="utf-8"))
        fundo = ((s.get("capa") or {}).get("fundo") or "").upper()
        pc = ROOT / p["pasta"] / "out" / ed / "props-capa.json"  # perfil que guarda o fundo da capa nas props da capa, não no script.json
        if not fundo and pc.exists():
            try: fundo = ((json.loads(pc.read_text(encoding="utf-8")).get("capa") or {}).get("fundo") or "").upper()
            except Exception: pass
        cover = ROOT / p["pasta"] / "out" / ed / "cover.jpg"
        real = cor_da_capa(Image.open(cover), ciclo, _xs(p), _ys(p))[0] if cover.exists() else None
        if fundo != esperada: problemas.append(f"fila: {ed} ({h}) tem fundo {fundo or '—'}; o ciclo pede {esperada}")
        if real != esperada: problemas.append(f"fila: a cover.jpg de {ed} ({h}) está {real or 'ausente'}; o ciclo pede {esperada}")
        ult = esperada
    # 3. contagem
    pub = len({json.loads(f.read_text(encoding="utf-8"))["id"].split("-v")[0] for f in (ROOT / p["pasta"] / "posts" / "05-publicado").glob("*.json") if not f.name.startswith("._")})
    if pub != len(reels): problemas.append(f"contagem: Instagram tem {len(reels)} reel(s), 05-publicado conhece {pub} (post fora do sistema ou arquivo faltando)")
    return {"ok": not problemas, "feed": [(l[0], l[2]) for l in linhas], "proxima": ciclo[(ciclo.index(ult) + 1) % len(ciclo)] if ult else None, "problemas": problemas}

def confere_item(p, ed):
    """Gate de publicação (post.py): a capa de <ed> tem a cor que o ciclo pede depois do último reel do feed real.
    Devolve [] se estiver certo (ou se o perfil não tem ciclo / o feed não pôde ser lido: erro de rede não trava o post)."""
    ciclo = [c.upper() for c in (p.get("grade") or {}).get("ciclo") or []]
    if len(ciclo) < 2: return []
    try:
        uid, tok, falta = post.credenciais(p)
        if falta: return []
        midia = post.api("GET", f"{uid}/media", params={"fields": "timestamp,thumbnail_url,media_url", "limit": 1, "access_token": tok})["data"]
        if not midia: return []
        ult = cor_da_capa(Image.open(io.BytesIO(requests.get(midia[0].get("thumbnail_url") or midia[0]["media_url"], timeout=60).content)), ciclo, _xs(p), _ys(p))[0]
    except Exception: return []
    esperada = ciclo[(ciclo.index(ult) + 1) % len(ciclo)]
    cover = ROOT / p["pasta"] / "out" / ed / "cover.jpg"
    if not cover.exists(): return []
    real = cor_da_capa(Image.open(cover), ciclo, _xs(p), _ys(p))[0]
    return [] if real == esperada else [f"capa da grade: o último reel do feed é {ult}, a capa de {ed} é {real} e o ciclo pede {esperada} (rode grade.py {p['pasta']} e refaça a capa)"]

if __name__ == "__main__":
    r = conferir(sys.argv[1])
    print(json.dumps(r, ensure_ascii=False, indent=1)); sys.exit(0 if r["ok"] else 1)
