"""Precheck (ANTES do render): mede os textos da composição em quadros amostrados e reprova o que o QA só pegaria depois do render.
Checa: texto sobreposto, texto coberto, fora do quadro / da área segura, contraste contra o fundo real (por pixel) e texto pequeno.
Uso (na raiz do projeto):  python _sistema/orquestrador/precheck/precheck.py <pasta_da_edicao> [--passo 15] [--min-fonte 28] [--mantem-quadros]
Lê da pasta: props.json (o render.py grava; se faltar, monta de script.json + words.json). Grava <pasta>/precheck.json.
Gravidade: "erros" reprovam (passou=false); "avisos" só informam. Rodar entre mix.py e render.py: precheck → corrige → render."""
import sys as _sys; _sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, json, pathlib, re, shutil, subprocess, sys, time
import numpy as np
import yaml
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
AQUI = pathlib.Path(__file__).resolve().parent
# Calibração (8 edições reais; CALIBRACAO.md): só sobreposição curta e forte e texto fora da área segura reprovam.
# Persistente (≥ 10 amostras) ou leve (caixa tocando < 50%) = layout/texto inclinado, só aviso; coberto/fora do quadro/contraste por pixel/texto pequeno = aviso.
ERROS = {"texto_sobreposto", "fora_da_area_segura"}
PERSISTENTE, RATIO_FORTE = 10, 0.5


def perfil_de(pasta):
    perfil = pasta.relative_to(ROOT).parts[0]
    p = next((x for x in carrega(ROOT)["perfis"] if x.get("pasta") == perfil), {})
    return perfil, p


def luz(rgb):
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def contraste_local(img, it):
    """Contraste da cor do texto contra o que está de fato atrás dele no quadro: pixels da caixa que NÃO são da cor do texto."""
    m = re.match(r"rgba?\(([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)", it["cor"])
    if not m or it["w"] * it["h"] < 400 or it["op"] < 0.5: return None
    tc = np.array([float(m.group(i)) for i in (1, 2, 3)])
    x0, y0 = max(it["x"], 0), max(it["y"], 0); x1, y1 = min(it["x"] + it["w"], img.shape[1]), min(it["y"] + it["h"], img.shape[0])
    if x1 - x0 < 6 or y1 - y0 < 6: return None
    reg = img[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    dist = np.linalg.norm(reg - tc, axis=1)
    bg = reg[dist > 90]
    if len(bg) < 0.2 * len(reg): return None   # quase tudo é da cor do texto (ou não dá para separar): não mede
    lt = float(luz(tc)); lb = luz(bg)
    c = (np.maximum(lt, lb) + 0.05) / (np.minimum(lt, lb) + 0.05)
    return round(float(np.median(c)), 2)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(); ap.add_argument("pasta"); ap.add_argument("--passo", type=int, default=2, help="varredura do DOM a cada N quadros (2 pega troca de legenda de 2-3 quadros)"); ap.add_argument("--pixel-passo", type=int, default=60)
    ap.add_argument("--min-fonte", type=float, default=28); ap.add_argument("--composicao"); ap.add_argument("--mantem-quadros", action="store_true")
    ap.add_argument("--nas-palavras", action="store_true", help="mede 3 quadros a partir de cada palavra (pega troca de legenda); sem pixel"); a = ap.parse_args()
    pasta = pathlib.Path(a.pasta).resolve(); perfil, pf = perfil_de(pasta)
    sys.path.insert(0, str(ROOT / "_sistema" / "orquestrador")); import render
    comp = a.composicao or render.comp_do_perfil(perfil)["edicao"]
    props = pasta / "props.json"
    if not props.exists():
        props = pasta / "_props_precheck.json"
        props.write_text(json.dumps({"script": json.loads((pasta / "script.json").read_text(encoding="utf-8")),
                                     "words": json.loads((pasta / "words.json").read_text(encoding="utf-8"))}, ensure_ascii=False), encoding="utf-8")
    saida = pasta / "precheck_bruto.json"; quadros = pasta / "_precheck_quadros"
    seg = (pf.get("qualidade") or {}).get("area_segura")
    cmd = ["node", str(AQUI / "precheck.mjs"), str(ROOT / perfil / "remotion"), comp, str(props), str(saida), f"--passo={a.passo}",
           f"--min-fonte={a.min_fonte}", f"--frames-dir={quadros}", f"--pixel-passo={a.pixel_passo}"]
    if a.nas_palavras:   # amostra onde a legenda troca de bloco (sobreposição de 3 quadros some no passo de 15)
        w = json.loads((pasta / "words.json").read_text(encoding="utf-8")); fr = sorted({int(x["start"] * 30) + d for x in w for d in (-1, 0, 1, 2) if int(x["start"] * 30) + d >= 0})
        cmd = [c for c in cmd if not c.startswith("--frames-dir")] + ["--frames=" + ",".join(map(str, fr))]
    if seg: cmd.append("--safe=" + ",".join(str(v) for v in [seg[0], seg[1], seg[2], seg[3]]))   # perfil.yaml → qualidade.area_segura: [y0, y1, x0, x1]
    t0 = time.time(); r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode: sys.exit("precheck (node) falhou:\n" + (r.stderr or r.stdout)[-2000:])
    bruto = json.loads(saida.read_text(encoding="utf-8")); med = json.loads(saida.with_suffix(".medidas.json").read_text(encoding="utf-8"))
    for x in bruto["achados"]:
        if x["tipo"] == "texto_sobreposto":
            if x["n"] >= PERSISTENTE: x["tipo"] = "sobreposicao_persistente"
            elif x["detalhe"].get("ratio", 1) < RATIO_FORTE: x["tipo"] = "sobreposicao_leve"
    achados = {(x["tipo"], json.dumps(x["detalhe"], sort_keys=True, ensure_ascii=False)): x for x in bruto["achados"]}
    # contraste por pixel, quadro a quadro
    loc = {}
    for f, itens in med["medidas"].items():
        arq = quadros / f"f{f}.jpg"
        if not arq.exists(): continue
        img = np.asarray(Image.open(arq).convert("RGB"))
        for it in itens:
            c = contraste_local(img, it)
            if c is not None and c < 3:
                k = it["txt"]; d = loc.setdefault(k, {"tipo": "contraste_local_baixo", "detalhe": {"txt": k, "contraste_mediano": c, "minimo": 3}, "t0": int(f) / 30, "t1": int(f) / 30, "n": 0})
                d["t1"] = int(f) / 30; d["n"] += 1; d["detalhe"]["contraste_mediano"] = min(d["detalhe"]["contraste_mediano"], c)
    todos = list(achados.values()) + [{**v, "t0": round(v["t0"], 2), "t1": round(v["t1"], 2)} for v in loc.values()]
    erros = [x for x in todos if x["tipo"] in ERROS]; avisos = [x for x in todos if x["tipo"] not in ERROS]
    out = {"composicao": comp, "quadros_medidos": bruto["quadros_medidos"], "passo": a.passo, "tempo_s": round(time.time() - t0), "passou": not erros, "erros": erros, "avisos": avisos}
    (pasta / "precheck.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in (saida, saida.with_suffix(".medidas.json"), pasta / "_props_precheck.json"): p.unlink(missing_ok=True)
    if not a.mantem_quadros: shutil.rmtree(quadros, ignore_errors=True)
    print(f"precheck {pasta.name}: {'OK' if out['passou'] else 'REPROVADO'} · {len(erros)} erro(s), {len(avisos)} aviso(s) · {out['quadros_medidos']} quadros em {out['tempo_s']} s")
    for x in erros: print("  ERRO ", x["tipo"], f'{x["t0"]}-{x["t1"]}s', json.dumps(x["detalhe"], ensure_ascii=False))
    for x in avisos: print("  aviso", x["tipo"], f'{x["t0"]}-{x["t1"]}s', json.dumps(x["detalhe"], ensure_ascii=False))
    sys.exit(0 if out["passou"] else 1)


if __name__ == "__main__":
    main()
