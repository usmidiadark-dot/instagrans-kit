"""Refs -> material de estilo. Tira medidas e quadros dos videos de referencia de um perfil.

Uso (na raiz do kit):
  python _sistema/orquestrador/refs.py baixar  <pasta-do-perfil>   # baixa os links de refs/links.txt (precisa do yt-dlp)
  python _sistema/orquestrador/refs.py analisar <pasta-do-perfil>  # quadros, folhas de contato, paleta, cortes, som
  python _sistema/orquestrador/refs.py status  <pasta-do-perfil>

Entrada: <perfil>/refs/*.mp4|mov|webm|mkv  +  <perfil>/refs/links.txt (um link por linha; # = comentario)
Saida:   <perfil>/refs/_analise/<video>/  (folha-gancho.png, folha-geral.png, quadros/, analise.json)
         <perfil>/refs/_analise/RESUMO.json  (medidas de todos, para o Claude escrever o estilo)
O Claude le as folhas (imagens) e o RESUMO e escreve <perfil>/estilo-extraido.md + remotion/src/estilo.ts
(skill analisar-refs). Este script so mede e prepara: quem decide o estilo e o Claude, olhando os quadros.
"""
import json, re, shutil, subprocess, sys, glob, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def _acha(nome):
    p = shutil.which(nome)
    if p:
        return p
    base = os.environ.get("LOCALAPPDATA", "")
    for g in glob.glob(str(Path(base) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg*" / "**" / (nome + ".exe")), recursive=True):
        return g
    sys.exit(f"'{nome}' nao encontrado. Rode instalar.ps1 (ou instale o ffmpeg) e reabra o terminal.")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def sonda(video):
    j = json.loads(_run([_acha("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)]).stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    num, _, den = (v.get("r_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    return {
        "duracao_s": round(float(j.get("format", {}).get("duration", 0)), 2),
        "largura": v.get("width"), "altura": v.get("height"), "fps": round(fps, 2),
        "tem_audio": a is not None,
    }


def cortes(video, limiar=0.30):
    """Tempos (s) de corte de cena. Ritmo = cortes por 10 s."""
    r = _run([_acha("ffmpeg"), "-hide_banner", "-i", str(video), "-vf", f"select='gt(scene,{limiar})',showinfo", "-an", "-f", "null", "-"])
    return [round(float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def som(video):
    r = _run([_acha("ffmpeg"), "-hide_banner", "-i", str(video), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"])
    m = re.search(r"I:\s+(-?[0-9.]+) LUFS", r.stderr[r.stderr.rfind("Summary"):] if "Summary" in r.stderr else "")
    return {"lufs": float(m.group(1))} if m else {}


def quadros(video, pasta, dur):
    """Gancho: 1 quadro a cada 0,25 s nos 3 primeiros segundos. Resto: 1 por segundo (no maximo 60)."""
    q = pasta / "quadros"
    q.mkdir(parents=True, exist_ok=True)
    ff = _acha("ffmpeg")
    _run([ff, "-y", "-hide_banner", "-t", "3", "-i", str(video), "-vf", "fps=4,scale=270:-2", str(q / "g_%03d.jpg")])
    passo = max(1.0, dur / 60)
    _run([ff, "-y", "-hide_banner", "-ss", "3", "-i", str(video), "-vf", f"fps=1/{passo},scale=270:-2", str(q / "r_%03d.jpg")])
    return sorted(q.glob("g_*.jpg")), sorted(q.glob("r_*.jpg")), passo


def folha(imgs, destino, colunas, rotulos):
    from PIL import Image, ImageDraw
    if not imgs:
        return
    ims = [Image.open(i).convert("RGB") for i in imgs]
    w, h = ims[0].size
    linhas = (len(ims) + colunas - 1) // colunas
    f = Image.new("RGB", (colunas * w, linhas * (h + 16)), (20, 20, 20))
    d = ImageDraw.Draw(f)
    for n, im in enumerate(ims):
        x, y = (n % colunas) * w, (n // colunas) * (h + 16)
        f.paste(im, (x, y + 16))
        d.text((x + 4, y + 2), rotulos[n], fill=(255, 255, 255))
    f.save(destino)


def paleta(imgs, k=6):
    """Cores dominantes (hex) por quantizacao; ignora quase-preto/quase-branco puro para achar a paleta do estilo."""
    from PIL import Image
    cont = {}
    for i in imgs[:: max(1, len(imgs) // 20)]:
        im = Image.open(i).convert("RGB").resize((48, 48)).quantize(colors=k, method=Image.Quantize.MEDIANCUT)
        pal = im.getpalette()[: k * 3]
        for n, cor in im.getcolors():
            rgb = tuple(pal[cor * 3: cor * 3 + 3])
            cont[rgb] = cont.get(rgb, 0) + n
    # junta cores parecidas (passos de 24)
    cx = {}
    for rgb, n in cont.items():
        ch = tuple(c // 24 * 24 + 12 for c in rgb)
        cx[ch] = cx.get(ch, 0) + n
    top = sorted(cx.items(), key=lambda t: -t[1])[:k]
    return ["#%02x%02x%02x" % c for c, _ in top]


def analisa_um(video, saida):
    pasta = saida / re.sub(r"[^\w.-]+", "_", video.stem)
    pasta.mkdir(parents=True, exist_ok=True)
    info = sonda(video)
    dur = info["duracao_s"] or 1
    cs = cortes(video)
    g, r, passo = quadros(video, pasta, dur)
    folha(g, pasta / "folha-gancho.png", 6, [f"{i * 0.25:.2f}s" for i in range(len(g))])
    folha(r, pasta / "folha-geral.png", 8, [f"{3 + i * passo:.0f}s" for i in range(len(r))])
    gancho = [c for c in cs if c <= 3]
    res = {
        "arquivo": video.name, **info, **som(video),
        "cortes_s": cs, "cortes_por_10s": round(len(cs) / dur * 10, 1),
        "cortes_no_gancho_0a3s": len(gancho),
        "paleta": paleta(g + r),
        "folhas": [str((pasta / "folha-gancho.png").relative_to(ROOT)), str((pasta / "folha-geral.png").relative_to(ROOT))],
    }
    (pasta / "analise.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def refs_dir(pasta):
    d = ROOT / pasta / "refs"
    if not d.is_dir():
        sys.exit(f"Crie a pasta {d} e ponha os videos de referencia (e um links.txt).")
    return d


def cmd_baixar(pasta):
    d = refs_dir(pasta)
    lk = d / "links.txt"
    links = [l.strip() for l in lk.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if lk.exists() else []
    if not links:
        return print("Sem links em refs/links.txt.")
    yt = shutil.which("yt-dlp") or sys.exit("Instale o yt-dlp: python -m pip install yt-dlp")
    for u in links:
        print("baixando", u)
        subprocess.run([yt, "-f", "mp4/bestvideo+bestaudio", "--merge-output-format", "mp4", "-o", str(d / "%(id)s.%(ext)s"), u])


def cmd_analisar(pasta):
    d = refs_dir(pasta)
    vids = sorted(p for p in d.iterdir() if p.suffix.lower() in EXT)
    if not vids:
        sys.exit("Nenhum video em refs/. Ponha os arquivos ou rode 'baixar' com links no links.txt.")
    saida = d / "_analise"
    todos = []
    for v in vids:
        print("analisando", v.name)
        todos.append(analisa_um(v, saida))
    n = len(todos)
    resumo = {
        "perfil": pasta, "videos": n, "itens": todos,
        "medianas": {
            "duracao_s": sorted(t["duracao_s"] for t in todos)[n // 2],
            "cortes_por_10s": sorted(t["cortes_por_10s"] for t in todos)[n // 2],
            "cortes_no_gancho_0a3s": sorted(t["cortes_no_gancho_0a3s"] for t in todos)[n // 2],
        },
        "links": (d / "links.txt").read_text(encoding="utf-8").splitlines() if (d / "links.txt").exists() else [],
    }
    (saida / "RESUMO.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Pronto: {saida / 'RESUMO.json'}. Proximo: peca ao Claude 'analise as refs do perfil {pasta}' (skill analisar-refs).")


def cmd_status(pasta):
    d = ROOT / pasta / "refs"
    print("refs:", len([p for p in d.glob("*") if p.suffix.lower() in EXT]) if d.is_dir() else 0, "videos;",
          "analise:", "ok" if (d / "_analise" / "RESUMO.json").exists() else "pendente")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("baixar", "analisar", "status"):
        sys.exit(__doc__)
    {"baixar": cmd_baixar, "analisar": cmd_analisar, "status": cmd_status}[sys.argv[1]](sys.argv[2])
