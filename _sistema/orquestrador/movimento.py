"""Conferência EM MOVIMENTO (depois que o QA aprova, o vídeo é conferido em movimento antes de entrar na fila: texto piscando
não aparece para o QA que olha quadros parados). Detector automático de PISCAR e folhas de quadros densos.
Piscar = um bloco da imagem que muda e VOLTA ao que era dentro de poucos quadros (A→B→A, até MAX_K quadros): texto/caixa/letra que aparece e some,
quebra de linha que pula. Câmera andando NÃO dispara: no pan suave o quadro de depois nunca volta ao de antes.
Uso (raiz):  python _sistema/orquestrador/movimento.py <pasta_da_edicao | video.mp4> [--folhas] [--densas [--passo 0.25]] [--saida movimento.json] [--estrito]
Grava <pasta>/movimento.json {passou, eventos[{t_s, quadro, blocos, k}], folhas[]}; sai com código 1 se reprovar. --folhas monta folhas de quadros
(a cada 3 quadros) ao redor de cada evento em <pasta>/movimento/ para olhar. Chamado pelo fila.py antes de entrar em 04-aprovado."""
import json, pathlib, subprocess, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
W, H = 270, 480          # análise em 1/4 da resolução (1080x1920), cinza
BW, BH = 18, 20          # bloco 18x20 → 15x24 blocos
MAX_K = 8                # piscar de até 8 quadros (0,27 s a 30 fps)
LIMIAR = 9.0             # diferença média (0–255) do bloco para contar como "mudou"
VOLTA = 0.30             # voltou ao que era: diferença entre antes e depois < 30% da menor mudança
MIN_BLOCOS = 2           # blocos juntos no mesmo quadro para virar evento (ruído de 1 bloco não reprova)

def _ffmpeg():
    import shutil
    f = shutil.which("ffmpeg")
    if f: return f
    import glob, os
    g = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe"))
    return g[0] if g else "ffmpeg"

def quadros(video):
    cmd = [_ffmpeg(), "-v", "error", "-i", str(video), "-vf", f"fps=30,scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W)

def _blocos(a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.float32)
    return d.reshape(H // BH, BH, W // BW, BW).mean(axis=(1, 3))

def detectar(q):
    """[(quadro, k, n_blocos, [(linha, col)…])] — quadro = primeiro quadro diferente (B) do A→B→A."""
    n = len(q); ach = {}
    for t in range(1, n - 1):
        dA = _blocos(q[t - 1], q[t])
        for k in range(1, MAX_K + 1):
            if t + k >= n: break
            dB = _blocos(q[t + k - 1], q[t + k]); dV = _blocos(q[t - 1], q[t + k])
            m = (dA > LIMIAR) & (dB > LIMIAR) & (dV < VOLTA * np.minimum(dA, dB))
            if m.any():
                for r, c in zip(*np.nonzero(m)): ach.setdefault(t, {}).setdefault((int(r), int(c)), k)
    return ach

def eventos(ach):
    """Agrupa quadros vizinhos (≤ 3 quadros de distância) e só mantém os que têm ≥ MIN_BLOCOS blocos num quadro."""
    ev = []
    for t in sorted(ach):
        bl = ach[t]
        if len(bl) < MIN_BLOCOS: continue
        if ev and t - ev[-1]["fim"] <= 3:
            ev[-1]["fim"] = t; ev[-1]["blocos"] = max(ev[-1]["blocos"], len(bl)); ev[-1]["k"] = max(ev[-1]["k"], max(bl.values()))
        else: ev.append({"quadro": t, "fim": t, "t_s": round(t / 30, 2), "blocos": len(bl), "k": max(bl.values())})
    return ev

def folhas(video, ev, pasta):
    from PIL import Image
    pasta.mkdir(exist_ok=True); out = []
    for i, e in enumerate(ev[:12]):
        a = max(0, e["quadro"] - 6); fim = pasta / f"evento{i + 1:02d}_{e['t_s']:.2f}s.jpg"
        tmp = pasta / f"_f{i}_%02d.png"
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{a / 30:.3f}", "-i", str(video), "-vf", "select='not(mod(n,2))',scale=270:480", "-frames:v", "12", str(tmp)], check=True)
        ims = [Image.open(str(pasta / f"_f{i}_{j:02d}.png")) for j in range(1, 13) if (pasta / f"_f{i}_{j:02d}.png").exists()]
        sh = Image.new("RGB", (270 * 6, 480 * 2))
        for j, im in enumerate(ims): sh.paste(im, ((j % 6) * 270, (j // 6) * 480))
        sh.save(fim, quality=80); out.append(fim.relative_to(ROOT).as_posix() if fim.is_relative_to(ROOT) else str(fim))
        for j in range(1, 13): (pasta / f"_f{i}_{j:02d}.png").unlink(missing_ok=True)
    return out

def folhas_densas(video, pasta, passo_s=0.5, cols=8, linhas=5, larg=180, alt=320):
    """Folhas de quadros densos (etapa b da regra, para o REVISOR olhar): 1 quadro a cada passo_s (0,25 nas peças novas, 0,5 no resto), carimbo do tempo em cada um."""
    from PIL import Image, ImageDraw
    pasta.mkdir(exist_ok=True); tmp = pasta / "_d_%04d.png"
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf", f"fps={1 / passo_s},scale={larg}:{alt}", str(tmp)], check=True)
    arqs = sorted(pasta.glob("_d_*.png")); por = cols * linhas; out = []
    for i in range(0, len(arqs), por):
        sh = Image.new("RGB", (larg * cols, alt * linhas)); dr = ImageDraw.Draw(sh)
        for j, a in enumerate(arqs[i:i + por]):
            x, y = (j % cols) * larg, (j // cols) * alt; sh.paste(Image.open(a), (x, y)); dr.rectangle((x, y, x + 52, y + 12), fill=(0, 0, 0)); dr.text((x + 2, y), f"{(i + j) * passo_s:.2f}s", fill=(255, 255, 0))
        fim = pasta / f"densa_{passo_s:.2f}s_{i // por + 1:02d}.jpg"; sh.save(fim, quality=78); out.append(fim.name)
    for a in arqs: a.unlink()
    return out

def confere(video):
    q = quadros(video); ev = eventos(detectar(q))
    return {"arquivo": str(video), "quadros": int(len(q)), "regra": {"max_k": MAX_K, "limiar": LIMIAR, "min_blocos": MIN_BLOCOS},
            "eventos": [{k: v for k, v in e.items() if k != "fim"} for e in ev], "passou": not ev,
            "gate": False,   # SÓ AVISO por enquanto: o A→B→A dispara também em vídeo bom (olhos, faíscas, balanço) e NÃO pega texto que reflui com a câmera andando; vale a etapa (b), folhas densas olhadas pelo revisor
            "nota": "não reprova sozinho; ver _sistema/qa-visual.md → conferência em movimento"}

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    alvo = pathlib.Path(sys.argv[1]); alvo = alvo if alvo.is_absolute() else pathlib.Path.cwd() / alvo
    video = alvo / "video.mp4" if alvo.is_dir() else alvo
    r = confere(video); pasta = video.parent
    if "--folhas" in sys.argv and r["eventos"]:
        evs = [dict(e, fim=e["quadro"]) for e in r["eventos"]]; r["folhas"] = folhas(video, evs, pasta / "movimento")
    if "--densas" in sys.argv:
        passo = float(sys.argv[sys.argv.index("--passo") + 1]) if "--passo" in sys.argv else 0.5
        r["folhas_densas"] = folhas_densas(video, pasta / "movimento", passo)
    if "--saida" in sys.argv: (pasta / sys.argv[sys.argv.index("--saida") + 1]).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("quadros", "passou")} | {"eventos": r["eventos"][:15]}, ensure_ascii=False))
    sys.exit(1 if ("--estrito" in sys.argv and not r["passou"]) else 0)
