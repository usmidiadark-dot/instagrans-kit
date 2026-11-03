"""Checagem de piscadas (nada que aparece e some rápido pode passar).
Renderiza só a camada de textos/HUD/inserts (prop soOverlay: sem a cena, sobre preto) em 270×480 e analisa quadro a quadro
numa grade de células de 15 px. Reprova:
  - aparece_e_some: algo acende numa região e apaga em menos de MIN_ON s (e não é só a borda de algo crescendo);
  - some_e_volta: a mesma coisa apaga e volta em até MAX_GAP s (0,5; o conteúdo antes e depois do buraco é o mesmo).
Troca de conteúdo no mesmo lugar (um bloco de legenda dando lugar ao seguinte) não conta.
Uso (na raiz do projeto):  python _sistema/orquestrador/piscadas.py <pasta_da_edicao> [--props props.json] [--composicao X]
Grava <pasta>/piscadas.json com "passou". O render.py chama isto e inclui no gate."""
import argparse, json, pathlib, subprocess, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
W, H, CEL, FPS = 270, 480, 15, 30
MIN_ON, MAX_GAP, LIMIAR = 0.4, 0.5, 40     # s, s, brilho (0–255) para a célula contar como "acesa"
MIN_PIXELS = 0.12                           # fração da célula acesa; abaixo disso é borda/antialias


def porta_livre():
    """Porta livre para o servidor do Remotion: com várias sessões renderizando ao mesmo tempo (perfis diferentes), todas
    disputavam a 3000 e uma renderizava a composição da outra ("Could not find composition"). O sistema escolhe uma porta vaga."""
    import socket
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

def renderizar(pasta, props, comp, remotion):
    p = json.loads(pathlib.Path(props).read_text(encoding="utf-8")); p["soOverlay"] = True
    tmp = pasta / "_props_overlay.json"; tmp.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    out = pasta / "_overlay.mp4"
    r = subprocess.run(["npx", "remotion", "render", "src/index.ts", comp, str(out), f"--props={tmp}", "--scale=0.25", "--muted",
                        "--codec=h264", "--crf=12", "--log=error", f"--port={porta_livre()}"], cwd=remotion, capture_output=True, text=True, shell=sys.platform == "win32")
    tmp.unlink(missing_ok=True)
    if r.returncode: sys.exit(f"render do overlay falhou:\n{r.stderr[-1500:]}")
    return out

def quadros(video):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W)

def analisar(fr):
    n = len(fr); gy, gx = H // CEL, W // CEL
    cel = fr[:, :gy * CEL, :gx * CEL].reshape(n, gy, CEL, gx, CEL).transpose(0, 1, 3, 2, 4)  # n, gy, gx, CEL, CEL
    acesa = (cel > LIMIAR).mean(axis=(3, 4)) >= MIN_PIXELS
    eventos = []
    for y in range(gy):
        for x in range(gx):
            s = acesa[:, y, x]
            if not s.any(): continue
            d = np.diff(np.r_[0, s.astype(np.int8), 0]); ini, fim = np.where(d == 1)[0], np.where(d == -1)[0]  # runs [ini, fim)
            for k, (a, b) in enumerate(zip(ini, fim)):
                if 2 <= b - a and (b - a) / FPS < MIN_ON and a > 0 and b < n:  # 1 quadro só = ruído de borda/brilho no limiar
                    # borda de algo que cresce/encolhe (orbe respirando, giz): os vizinhos ficam acesos o tempo todo → não é piscada
                    viz = acesa[a:b, max(y - 1, 0):y + 2, max(x - 1, 0):x + 2].reshape(b - a, -1)
                    if viz.all(axis=0).sum() >= 3: continue
                    # algo que só passou pela célula (painel deslizando, giz sendo riscado): a vizinhança estava acesa logo antes ou logo depois
                    if acesa[a - 1, max(y - 1, 0):y + 2, max(x - 1, 0):x + 2].any() or acesa[b, max(y - 1, 0):y + 2, max(x - 1, 0):x + 2].any(): continue
                    eventos.append({"tipo": "aparece_e_some", "t": round(a / FPS, 2), "dur_s": round((b - a) / FPS, 2), "y": y * CEL * 4, "x": x * CEL * 4})
                if k + 1 < len(ini):
                    gap = (ini[k + 1] - b) / FPS
                    if 2 / FPS <= gap <= MAX_GAP:  # buraco de 1 quadro = ruído de limiar
                        antes, depois = cel[b - 1, y, x].astype(float), cel[ini[k + 1], y, x].astype(float)
                        buraco = cel[b:ini[k + 1], y, x].astype(float).mean()
                        if antes.mean() - buraco < 8: continue  # não escureceu de verdade: brilho suave oscilando no limiar (objeto do card respirando, 23/10/2026)
                        if np.abs(antes - depois).mean() < 18:  # mesmo conteúdo antes e depois do buraco
                            eventos.append({"tipo": "some_e_volta", "t": round(b / FPS, 2), "dur_s": round(gap, 2), "y": y * CEL * 4, "x": x * CEL * 4})
    # agrupa por (tipo, instante): várias células da mesma piscada viram um evento
    agr = {}
    for e in eventos:
        k = (e["tipo"], round(e["t"] * 4) / 4)
        g = agr.setdefault(k, {"tipo": e["tipo"], "t": e["t"], "dur_s": e["dur_s"], "celulas": 0, "regiao_y": [e["y"], e["y"]]})
        g["celulas"] += 1; g["regiao_y"] = [min(g["regiao_y"][0], e["y"]), max(g["regiao_y"][1], e["y"])]
    return sorted([g for g in agr.values() if g["celulas"] >= 2], key=lambda g: g["t"])

# área segura do feed: o reel também aparece no feed sem abrir, cortado no centro em 4:5 → tudo que é texto/HUD/card
# fica em y 285–1635 (1080×1920) e fora da coluna de botões (x > 950 entre y 1000 e 1635). Conta células acesas fora por ≥ 0,2 s.
SEG_TOPO, SEG_BASE, BOT_X, BOT_Y, MIN_FORA = 285, 1635, 950, 1000, 0.2

def fora_da_area(fr):
    n = len(fr); gy, gx = H // CEL, W // CEL
    cel = fr[:, :gy * CEL, :gx * CEL].reshape(n, gy, CEL, gx, CEL).transpose(0, 1, 3, 2, 4)
    acesa = (cel > LIMIAR).mean(axis=(3, 4)) >= MIN_PIXELS
    ys = (np.arange(gy) * CEL + CEL / 2) * 4; xs = (np.arange(gx) * CEL + CEL / 2) * 4  # centro da célula em px do vídeo cheio
    fora = (ys[:, None] < SEG_TOPO) | (ys[:, None] > SEG_BASE) | ((xs[None, :] > BOT_X) & (ys[:, None] > BOT_Y))
    conta = (acesa & fora[None]).sum(axis=(1, 2)) >= 2
    ev = []; d = np.diff(np.r_[0, conta.astype(np.int8), 0]); ini, fim = np.where(d == 1)[0], np.where(d == -1)[0]
    for a, b in zip(ini, fim):
        if (b - a) / FPS < MIN_FORA: continue
        k = (acesa[a:b] & fora[None]).any(axis=0); yy, xx = np.where(k)
        ev.append({"t": round(a / FPS, 2), "ate": round(b / FPS, 2), "y": [int(ys[yy.min()]), int(ys[yy.max()])], "x": [int(xs[xx.min()]), int(xs[xx.max()])]})
    return ev

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pasta"); ap.add_argument("--props"); ap.add_argument("--composicao"); a = ap.parse_args()
    pasta = pathlib.Path(a.pasta).resolve(); perfil = pasta.relative_to(ROOT).parts[0]
    if not a.composicao:
        sys.path.insert(0, str(pathlib.Path(__file__).parent)); from render import comp_do_perfil
        a.composicao = comp_do_perfil(perfil)["edicao"]
    video = renderizar(pasta, a.props or pasta / "props.json", a.composicao, ROOT / perfil / "remotion")
    fr = quadros(video); ev = analisar(fr); fora = fora_da_area(fr); video.unlink(missing_ok=True)
    res = {"regra": {"min_visivel_s": MIN_ON, "max_buraco_s": MAX_GAP, "area_segura": [SEG_TOPO, SEG_BASE], "botoes": [BOT_X, BOT_Y]}, "eventos": ev, "fora_da_area": fora, "passou": not ev}
    (pasta / "piscadas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(0 if res["passou"] else 1)

if __name__ == "__main__":
    main()
