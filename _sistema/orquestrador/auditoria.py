"""Auditoria de repetição: o mesmo padrão, a mesma animação, o mesmo design voltando em edição após edição.
Lê os script.json das últimas edições de um perfil e acha, SOZINHA, o que se repete:
  1. dimensões conhecidas (HUD, ambiente, prova, marca, chamada, trilha, kit, transições, mundos…): quantos valores diferentes nas últimas N e qual domina;
  2. repetições NÃO catalogadas: qualquer par (caminho, valor) de texto curto que aparece em quase todas as edições (ex.: a cor de uma marca, o tema da HUD,
     um estilo que nunca foi sorteado). É o que pega o próximo "mesmo círculo" antes de alguém reclamar.
Grava <perfil>/reviews/auditoria_repeticao.md e .json. O montagem.py usa o 1º achado para escolher a "estreia: invente" da edição (criar uma variação do que está parado)
e o orquestrador roda isto antes de cada produção.
Uso (na raiz do projeto):  python _sistema/orquestrador/auditoria.py <pasta_do_perfil> [--ultimas 6]"""
import argparse, collections, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
# caminhos que são texto da edição ou números de tempo/posição: não contam como "design repetido"
IGNORAR = re.compile(r"(^|\.)(title|vo|text|texto|caption|rotulo|valor|unidade|status|sources|fontes|keywords|cast|description|o_que|id|edition|profile|format|titulo|linha1|linha2|"
                     r"arquivo|frio|quente|eq|label|promessa|palavra|fonte|nome|descricao|legenda_oculta|_unidades|periodo)(\[\])?$", re.I)

def achata(o, caminho="", out=None):
    out = {} if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("_"): continue
            achata(v, f"{caminho}.{k}" if caminho else k, out)
    elif isinstance(o, list):
        for v in o: achata(v, f"{caminho}[]", out)
    elif isinstance(o, str) and 1 <= len(o) <= 40 and not IGNORAR.search(caminho) and not re.fullmatch(r"[\d.,:\s%-]+", o):
        out.setdefault(caminho, set()).add(o)
    return out

def assinatura(pasta):
    s = json.loads((pasta / "script.json").read_text(encoding="utf-8")); m = s.get("montagem") or {}
    sfx = json.loads((pasta / "sfx.json").read_text(encoding="utf-8")) if (pasta / "sfx.json").exists() else {}
    mov = set()
    for sh in s.get("shots", []):
        for k in ("push-in", "pull-out", "órbita", "travelling", "grua", "dolly-zoom", "atravessa"):
            if k in (sh.get("camera") or {}).get("move", ""): mov.add(k)
    amb = s.get("ambiente"); amb = amb if isinstance(amb, str) else (amb or {}).get("nome")
    return {
        "formato": m.get("formato") or (s.get("format") or "?").split(" ")[0].split("—")[0].strip(),
        "hud": (s.get("hud") or {}).get("estilo") or ("placar" if s.get("hud") else "nenhuma"),
        "ambiente": amb or "nenhum",
        "prova": (s.get("prova") or {}).get("estilo") or "papel_fita",
        "marca": (s.get("prova") or {}).get("marca") or "caneta_vermelha",
        "chamada": (s.get("cta") or {}).get("estilo") or ("cartao_classico" if (s.get("oferta") or {}).get("card") or True else "nenhuma"),
        "trilha": pathlib.PurePosixPath(str(sfx.get("trilha", "?"))).stem, "kit": pathlib.PurePosixPath(str(sfx.get("pasta_sons", "?")).rstrip("/")).name,
        "mundo": "+".join(sorted({sh.get("cena", "?") for sh in s.get("shots", [])})),
        "transicoes": ",".join(sorted({sh.get("transicao", "corte") for sh in s.get("shots", [])[1:]})), "movimentos": ",".join(sorted(mov)),
        "gancho": str(s.get("gancho") or "?"),
    }, achata({k: v for k, v in s.items() if k not in ("shots",)}), achata({"shots": s.get("shots", [])})

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("perfil"); ap.add_argument("--ultimas", type=int, default=6); a = ap.parse_args()
    base = ROOT / a.perfil / "out"
    eds = sorted([d for d in base.iterdir() if re.fullmatch(r"[a-z]+-\d{3}", d.name) and (d / "script.json").exists() and (d / "video.mp4").exists()], key=lambda d: d.name)[-a.ultimas:]
    if len(eds) < 3: sys.exit("poucas edições para auditar")
    sigs = {d.name: assinatura(d) for d in eds}; dims = list(next(iter(sigs.values()))[0].keys())
    achados = []
    for dim in dims:
        vals = [sigs[n][0][dim] for n in sigs]; c = collections.Counter(vals); topo, qtd = c.most_common(1)[0]
        if qtd / len(vals) >= 0.6 and len(vals) >= 4: achados.append({"tipo": "dimensao", "dim": dim, "valor": topo, "em": f"{qtd}/{len(vals)}", "distintos": len(c), "peso": qtd / len(vals)})
    # repetições não catalogadas: (caminho, valor) em quase todas as edições
    por_ed = [{**sigs[n][1], **sigs[n][2]} for n in sigs]; cont = collections.Counter()
    for d in por_ed:
        for caminho, vs in d.items():
            for v in vs: cont[(caminho, v)] += 1
    conhecidos = ("hud.estilo", "ambiente", "prova", "cta", "montagem", "capa.fundo", "oferta", "scene.sky", "scene.subject", "scene.paper", "hud.tema", "hud.arquivo")
    for (caminho, v), q in cont.most_common(60):
        if q / len(por_ed) >= 0.83 and len(por_ed) >= 5 and not caminho.startswith(("shots[].layers", "shots[].beat", "shots[].cena", "shots[].camera.plane", "keywords", "cast")):
            achados.append({"tipo": "nao_catalogado", "caminho": caminho, "valor": v, "em": f"{q}/{len(por_ed)}", "peso": q / len(por_ed)})
    achados.sort(key=lambda x: (x["tipo"] != "dimensao", -x["peso"]))
    out = {"perfil": a.perfil, "edicoes": list(sigs), "assinaturas": {n: sigs[n][0] for n in sigs}, "achados": achados}
    rev = ROOT / a.perfil / "reviews"; rev.mkdir(exist_ok=True)
    (rev / "auditoria_repeticao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# Auditoria de repetição · {a.perfil}", "", f"Últimas {len(sigs)} edições: {', '.join(sigs)}.", "", "## Dimensões conhecidas (valor por edição)", "", "| dimensão | " + " | ".join(n.split("-")[-1] for n in sigs) + " |", "|---|" + "---|" * len(sigs)]
    for dim in dims: L.append(f"| {dim} | " + " | ".join(str(sigs[n][0][dim])[:18] for n in sigs) + " |")
    L += ["", "## Achados (o que está parado)", ""]
    L += [f"- **{x['dim']}** = `{x['valor']}` em {x['em']} (só {x['distintos']} valor(es) diferente(s))" if x["tipo"] == "dimensao" else f"- `{x['caminho']}` = `{x['valor']}` em {x['em']} (não estava no catálogo: criar variação)" for x in achados] or ["- nada parado"]
    (rev / "auditoria_repeticao.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{len(achados)} achado(s):"); [print(" -", (x.get("dim") or x.get("caminho")), "=", x["valor"], x["em"]) for x in achados[:12]]

if __name__ == "__main__": main()
