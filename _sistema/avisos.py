"""Caixa de avisos entre conversas. Uso: avisos.py criar|listar|conferido (ver _sistema/avisos/LEIA-ME.md)."""
import argparse, datetime as dt, json, re, shutil, sys, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent / "avisos"
PEND, LIDOS = BASE / "pendentes", BASE / "lidos"


def papeis():
    """Papéis válidos: o prefixo de cada perfil (perfil.yaml → prefixo) + sistema + geral. 'todos' = todos eles."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "orquestrador"))
        from perfis_cfg import carrega
        pref = [str(p.get("prefixo") or p["pasta"]).lower() for p in carrega(Path(__file__).resolve().parents[1])["perfis"]]
    except Exception:
        pref = []
    return list(dict.fromkeys(pref + ["sistema", "geral"]))


PAPEIS = papeis()


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40] or "aviso"


def destinos(txt):
    if txt.strip().lower() == "todos":
        return list(PAPEIS)
    r = [x.strip().lower() for x in txt.split(",") if x.strip()]
    ruins = [x for x in r if x not in PAPEIS]
    if ruins or not r:
        sys.exit(f"papel invalido: {ruins or txt}. Validos: {', '.join(PAPEIS)} ou todos")
    return r


def carrega():
    out = []
    for f in sorted(PEND.glob("*.json")):
        try:
            out.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            pass
    return out


def falta(a):
    return [p for p in a["para"] if p not in a.get("conferido_por", [])]


def linha(a):
    para = "todos" if len(a["para"]) >= len(PAPEIS) else ",".join(a["para"])
    return f'{a["id"]} | {a["de"]}->{para} | {a["titulo"]} | falta: {",".join(falta(a))}'


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("criar")
    for k in ("de", "para", "titulo", "mudou", "conferir"):
        c.add_argument("--" + k, required=True)
    sp.add_parser("listar")
    k = sp.add_parser("conferido")
    k.add_argument("--id", required=True)
    k.add_argument("--papel", required=True)
    a = ap.parse_args()
    PEND.mkdir(parents=True, exist_ok=True)
    LIDOS.mkdir(parents=True, exist_ok=True)
    if a.cmd == "criar":
        if a.de.lower() not in PAPEIS:
            sys.exit(f"papel invalido em --de: {a.de}")
        agora = dt.datetime.now()
        aid = agora.strftime("%Y%m%d-%H%M%S") + "-" + slug(a.titulo)
        d = {"id": aid, "criado": agora.isoformat(timespec="seconds"), "de": a.de.lower(), "para": destinos(a.para),
             "titulo": a.titulo, "mudou": a.mudou, "conferir": a.conferir, "conferido_por": []}
        (PEND / f"{aid}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print("criado:", aid)
    elif a.cmd == "listar":
        av = carrega()
        if not av:
            print("(sem avisos pendentes)")
        for _, d in av:
            print(linha(d))
    else:
        f = PEND / f"{a.id}.json"
        p = a.papel.lower()
        if p not in PAPEIS:
            sys.exit(f"papel invalido: {p}")
        if not f.exists():
            sys.exit(f"aviso nao encontrado em pendentes: {a.id}")
        d = json.loads(f.read_text(encoding="utf-8"))
        if p not in d["para"]:
            sys.exit(f"{p} nao e destinatario deste aviso ({','.join(d['para'])})")
        if p not in d["conferido_por"]:
            d["conferido_por"].append(p)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        if not falta(d):
            shutil.move(str(f), str(LIDOS / f.name))
            print("todos conferiram -> movido para lidos/")
        else:
            print("conferido por", p, "| falta:", ",".join(falta(d)))


if __name__ == "__main__":
    main()
