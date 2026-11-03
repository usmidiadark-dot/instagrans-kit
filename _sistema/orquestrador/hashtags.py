"""Hashtags de todos os perfis: 3 FIXAS do perfil + 3 VARIÁVEIS sorteadas do banco do perfil que não aparecem nos 3 posts
anteriores (nem nos 3 seguintes já agendados). Ficam numa linha só, UMA LINHA EM BRANCO depois do texto da legenda.
Config: <perfil>/perfil.yaml → hashtags: {fixas: [3], variaveis: [>= 12], por_tema: {<script.tema>: [...]}}; sem isso o perfil fica sem o bloco (no máximo 3 hashtags).
Uso:  python _sistema/orquestrador/hashtags.py aplicar [--perfil <pasta>]   (reescreve as legendas já na fila 04-aprovado, em ordem de horário)"""
import json, pathlib, random, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TAG = re.compile(r"#\w+")
BLOCO = re.compile(r"(?:\s*#\w+)+\s*\Z")   # bloco de hashtags no fim da legenda

def config(p):
    """{'fixas': [3], 'variaveis': [>= 12], 'por_tema': {tema: [...]}} do perfil (perfil.yaml → hashtags); None se o perfil não tem."""
    c = (p or {}).get("hashtags")
    return c if isinstance(c, dict) and c.get("fixas") and c.get("variaveis") else None

def separa(texto):
    """(corpo sem o bloco de hashtags do fim, lista de hashtags do fim)."""
    m = BLOCO.search(texto.rstrip())
    if not m: return texto.rstrip(), []
    return texto.rstrip()[:m.start()].rstrip(), TAG.findall(m.group(0))

def _itens(p):
    """[(horario, id, [hashtags do fim])] de tudo que o perfil já publicou ou tem na fila, em ordem de horário."""
    pasta = ROOT / p["pasta"] / "posts"; out = []
    for sub in ("05-publicado", "04-aprovado"):
        for f in (pasta / sub).glob("*.json"):
            try: d = json.loads(f.read_text(encoding="utf-8"))
            except Exception: continue
            if d.get("horario") and d.get("legenda"): out.append((d["horario"], d.get("id"), [t.lower() for t in separa(d["legenda"])[1]]))
    return sorted(out)

def usadas_perto(p, ed, horario=None):
    """Hashtags dos 3 posts antes (e dos 3 depois, se já agendados) deste horário; sem horário: dos 3 últimos do perfil."""
    todos = [x for x in _itens(p) if x[1] != ed]
    if horario:
        antes = [x for x in todos if x[0] < horario][-3:]; depois = [x for x in todos if x[0] > horario][:3]
        viz = antes + depois
    else: viz = todos[-3:]
    return {t for x in viz for t in x[2]}

def tema_da_edicao(p, ed):
    """Campo "tema" do out/<ed>/script.json (chave de hashtags.por_tema no perfil.yaml); None se não houver."""
    try: return json.loads((ROOT / p["pasta"] / "out" / ed / "script.json").read_text(encoding="utf-8")).get("tema")
    except Exception: return None

def banco_do_tema(p, ed, cfg):
    """Banco por assunto (cfg['por_tema'][tema]) só com tags que também estão em 'variaveis'; [] se o perfil/edição não tem."""
    por = cfg.get("por_tema") or {}; t = tema_da_edicao(p, ed)
    ok = {v.lower() for v in cfg["variaveis"]}
    return [x for x in (por.get(t) or por.get(str(t).upper()) or []) if x.lower() in ok] if t else []

def aplica(texto, p, ed, horario=None):
    """Troca o bloco de hashtags do fim por: linha em branco + 3 fixas + 3 variáveis (sorteio por edição, fora dos vizinhos). Sem config: não mexe."""
    cfg = config(p)
    if not cfg: return texto
    corpo, _ = separa(texto)
    fixas = [t.lower() for t in cfg["fixas"]]
    viz = usadas_perto(p, ed, horario); rng = random.Random(f"{p['pasta']}:{ed}")
    def livres_de(banco, excl=()): return [t for t in banco if t.lower() not in viz and t.lower() not in fixas and t not in excl]
    var = []
    tema = banco_do_tema(p, ed, cfg)   # combina com o assunto (por_tema); se faltar, completa do banco inteiro
    if tema: var = rng.sample(livres_de(tema), min(3, len(livres_de(tema))))
    resto = livres_de(cfg["variaveis"], var)
    if len(var) + len(resto) < 3: resto = [t for t in cfg["variaveis"] if t.lower() not in fixas and t not in var]   # banco pequeno demais: não trava (o confere avisa)
    var += rng.sample(resto, 3 - len(var))
    return corpo + "\n\n" + " ".join(cfg["fixas"] + var)

def confere(texto, p, ed, horario=None):
    """Erros da regra (vazio = ok). Perfil sem config: não confere."""
    cfg = config(p)
    if not cfg: return []
    erros = []; corpo, tags = separa(texto); baixo = [t.lower() for t in tags]
    fixas = [t.lower() for t in cfg["fixas"]]
    if len(tags) != 6: return [f"hashtags: precisam ser 6 (3 fixas + 3 variáveis), a legenda tem {len(tags)}"]
    if baixo[:3] != fixas: erros.append(f"hashtags: as 3 primeiras são as fixas do perfil {cfg['fixas']}")
    if any(t not in [v.lower() for v in cfg["variaveis"]] for t in baixo[3:]): erros.append("hashtags: as 3 variáveis têm que sair do banco do perfil")
    bt = {x.lower() for x in banco_do_tema(p, ed, cfg)}
    if bt and sum(t in bt for t in baixo[3:]) < 2: erros.append(f"hashtags: pelo menos 2 das 3 variáveis têm que ser do assunto (hashtags.por_tema) {sorted(bt)}")
    rep = [t for t in baixo[3:] if t in usadas_perto(p, ed, horario)]
    if rep: erros.append(f"hashtags: variável repetida dos 3 posts vizinhos {rep}")
    if not texto.rstrip().endswith(" ".join(tags)) or not re.search(r"\S\n\n#\w+", texto): erros.append("hashtags: todas numa linha só, uma linha em branco depois do texto")
    return erros

if __name__ == "__main__":
    import yaml
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from perfis_cfg import carrega
    cfg = carrega(ROOT); alvo = sys.argv[sys.argv.index("--perfil") + 1] if "--perfil" in sys.argv else None
    for p in cfg["perfis"]:
        if alvo and p["pasta"] != alvo or not config(p): continue
        for f in sorted((ROOT / p["pasta"] / "posts" / "04-aprovado").glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8")); novo = aplica(d["legenda"], p, d["id"], d["horario"])
            if novo != d["legenda"]:
                d["legenda"] = novo; f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            print(p["pasta"], d["id"], d["horario"], separa(novo)[1], confere(novo, p, d["id"], d["horario"]) or "ok")
