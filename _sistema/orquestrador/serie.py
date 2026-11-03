"""Série por personagem (opcional): N vídeos seguidos com o mesmo personagem, depois troca, para a grade ficar bonita em blocos e dar para
comparar qual personagem rende mais. perfil.yaml → serie = {tamanho: 3, ordem: [p1, p2, ...]}.
A história é a ordem de postagem: publicados (05-publicado) + fila (04-aprovado), pelo horário. O personagem de cada edição vem do
script.json da edição (campo personagem).
Uso (na raiz do projeto):  python _sistema/orquestrador/serie.py <pasta_do_perfil>   → imprime o personagem da vez e a série em curso"""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import json, pathlib, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = carrega(ROOT)

def perfil(pasta_perfil):
    return next(x for x in CFG["perfis"] if x.get("pasta") == pasta_perfil)

def personagem_de(pasta_perfil, id_):
    s = ROOT / pasta_perfil / "out" / id_ / "script.json"
    return json.loads(s.read_text(encoding="utf-8")).get("personagem") if s.exists() else None

def historia(pasta_perfil):
    """[(horario, id, personagem)] em ordem de postagem: publicados + fila."""
    itens = []
    for n, sub in enumerate(("05-publicado", "04-aprovado")):  # publicados antes da fila; publicados pela hora do arquivo (o horario deles é o slot antigo)
        for f in (ROOT / pasta_perfil / "posts" / sub).glob("*.json"):
            try: it = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError): continue
            if isinstance(it, dict) and it.get("id"): itens.append((n, f.stat().st_mtime if n == 0 else 0, it.get("horario", ""), it["id"]))
    vistos, out = set(), []
    for _, _, h, id_ in sorted(itens):
        if id_ in vistos: continue
        vistos.add(id_); out.append((h, id_, personagem_de(pasta_perfil, id_)))
    return out

def da_vez(pasta_perfil, hist=None):
    """Personagem que a próxima edição deve usar: continua a série do último post até completar o tamanho; depois a próxima da ordem."""
    cfg = perfil(pasta_perfil).get("serie") or {}
    tam, ordem = cfg.get("tamanho", 3), cfg.get("ordem", [])
    hist = [h for h in (historia(pasta_perfil) if hist is None else hist) if h[2]]
    if not hist: return (ordem or [None])[0], 0
    ultima = hist[-1][2]; n = 0
    for h in reversed(hist):
        if h[2] != ultima: break
        n += 1
    if n % tam: return ultima, n % tam
    usadas = []  # próxima da ordem que ainda não fechou série; se todas já tiveram, recomeça pela que está há mais tempo sem série
    for h in hist:
        if h[2] not in usadas: usadas.append(h[2])
    novas = [m for m in ordem if m not in usadas]
    if novas: return novas[0], 0
    candidatas = [m for m in ordem if m != ultima]
    return (min(candidatas, key=lambda m: max(i for i, h in enumerate(hist) if h[2] == m)) if candidatas else ultima), 0

if __name__ == "__main__":
    pasta = sys.argv[1].strip("/\\")
    m, n = da_vez(pasta)
    print(json.dumps({"personagem_da_vez": m, "ja_na_serie": n, "tamanho": (perfil(pasta).get("serie") or {}).get("tamanho", 3),
                      "historia": [f"{h} {i} {w}" for h, i, w in historia(pasta)]}, ensure_ascii=False, indent=1))

def liberar_reserva(pasta_perfil):
    """posts/03-reserva/: edição pronta que espera a vez da sua personagem. Quando a série dela é a da vez, volta para a fila no
    próximo horário do seu período, depois do último item da fila (a ordem da grade não quebra). Chamado pelo orquestrador
    (produzir e publicar) a cada 30 min. Devolve os ids liberados."""
    from fila import proximo_horario, TZ  # import aqui: fila.py também importa este módulo
    import datetime as dt
    p = perfil(pasta_perfil); res = ROOT / pasta_perfil / "posts" / "03-reserva"; fila_d = ROOT / pasta_perfil / "posts" / "04-aprovado"
    liberados = []
    for f in sorted(res.glob("*.json")) if res.exists() else []:
        it = json.loads(f.read_text(encoding="utf-8"))
        m = personagem_de(pasta_perfil, it["id"]); vez, n = da_vez(pasta_perfil)
        if m != vez: continue
        # entra no FIM da série dele: as novas do personagem ocupam os horários de antes e a
        # pronta (período fixo, ex.: noite) fecha a série, sem deixar buraco no dia
        n_res = sum(1 for g in res.glob("*.json") if personagem_de(pasta_perfil, json.loads(g.read_text(encoding="utf-8"))["id"]) == m)
        if n < (perfil(pasta_perfil).get("serie") or {}).get("tamanho", 3) - n_res: continue
        itens = [json.loads(g.read_text(encoding="utf-8")) for g in fila_d.glob("*.json")]
        s = json.loads((ROOT / pasta_perfil / "out" / it["id"] / "script.json").read_text(encoding="utf-8"))
        so = (p.get("periodos") or {}).get(s.get("periodo"))
        depois = max((dt.datetime.strptime(i["horario"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ) for i in itens), default=None)
        slot = proximo_horario(p, {i["horario"] for i in itens}, so, depois)
        it["horario"] = slot.strftime("%Y-%m-%d %H:%M")
        (fila_d / f'{slot.strftime("%Y-%m-%d_%H%M")}.json').write_text(json.dumps(it, ensure_ascii=False, indent=1), encoding="utf-8")
        f.unlink(); liberados.append(it["id"])
    return liberados
