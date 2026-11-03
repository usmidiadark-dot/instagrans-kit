"""Etapa 07 · fila: coloca uma edição aprovada no QA em <perfil>/posts/04-aprovado/<AAAA-MM-DD_HHMM>.json, no próximo horário livre.
Uso (na raiz do projeto):
  python _sistema/orquestrador/fila.py <perfil>/out/<id>            (o perfil sai do caminho)
  python _sistema/orquestrador/fila.py --perfil <pasta|prefixo> <id>
  python _sistema/orquestrador/fila.py --listar                       (perfis configurados)
O que confere antes de entrar na fila:
  1. qa.json, render_check.json e mix_check.json aprovados;
  2. legenda (lição rápida, hashtags 3 fixas + 3 variáveis, chamada no corpo ou SEM CTA, palavras proibidas);
  3. gates universais (gates_universais.py: gancho, seguir, card final, área segura, piscadas, áudio, HUD, variação);
  4. plugin do perfil: <pasta do perfil>/gates.py → gates(ctx) (contrato em CHAVES-PERFIL.md).
Achado "erro" barra; "aviso" só é impresso."""
import argparse, datetime as dt, importlib.util, json, os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from zoneinfo import ZoneInfo
from perfis_cfg import carrega

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")   # console do Windows (cp1252)
    except Exception: pass
CFG = carrega(ROOT)
TZ = ZoneInfo(CFG["padrao"].get("fuso", "America/New_York"))

import hashtags as HT       # 3 fixas + 3 variáveis, linha em branco antes
import legenda_cta as LC    # chamada para comentar no CORPO da legenda, variada por edição

HORARIO_LIMITE = None   # quem reconfere um item que já está na fila põe o horário dele aqui: só conta como "anterior" o que vem antes


def proximo_horario(p, ocupados, so=None, depois=None):
    """Próximo horário livre do perfil (perfil.yaml → horarios, no fuso do padrao). so = um horário só; depois = nunca antes deste."""
    agora = max(dt.datetime.now(TZ) + dt.timedelta(minutes=30), depois or dt.datetime.min.replace(tzinfo=TZ))
    dia = agora.date()
    horarios = [so] if so else (p.get("horarios") or [])
    if not horarios: sys.exit(f'{p.get("handle", p.get("pasta"))}: perfil.yaml sem `horarios` (ex.: ["09:00", "13:00", "19:00"])')
    for _ in range(60):
        for h in sorted(horarios):
            hh, mm = map(int, h.split(":"))
            slot = dt.datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=TZ)
            if slot > agora and slot.strftime("%Y-%m-%d %H:%M") not in ocupados: return slot
        dia += dt.timedelta(days=1)
    sys.exit("sem horário livre nos próximos 60 dias")


# ---------- legenda ----------
PROIBIDAS = ["buy", "shop", "sale", "discount", "offer", "deal", "limited", "hurry", "last chance", "don't miss",
             "dm me", "follow for", "follow us", "save this", "share this", "like this"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⬛-⭕]")
NUMERADA = re.compile(r"^\s*([1-9])[.)]\s+\S")


def emoji_do_perfil(p):
    """Emoji que fecha a linha de chamada: oferta.emoji, senão o último caractere da oferta.cta, senão o 1º emoji do banco legenda_cta, senão 💬."""
    of = (p or {}).get("oferta") or {}
    ultimo = (of.get("cta") or "").rstrip()[-1:]
    banco = ((p or {}).get("legenda_cta") or {}).get("emojis") or [""]
    return of.get("emoji") or (ultimo if ultimo and EMOJI.match(ultimo) else "") or banco[0] or "💬"


def cta_linha(script, p=None):
    """Linha crua de chamada do script.cta ('comment "PALAVRA" and I'll send you <promessa> <emoji>'), ou None."""
    c = (script or {}).get("cta")
    return f'comment "{c["palavra"]}" and I\'ll send you {c["promessa"]} {emoji_do_perfil(p)}' if isinstance(c, dict) and c.get("palavra") and c.get("promessa") else None


def sem_cta(script):
    """script.json → cta: false / sem_cta: true = edição SEM chamada para comentar."""
    return bool(script) and (script.get("sem_cta") is True or script.get("cta") is False)


def palavra_e_promessa(texto, p, script=None):
    """(PALAVRA, promessa) da edição: script.cta > a linha de chamada que já está na legenda > a oferta.cta do perfil. None = edição sem chamada."""
    if sem_cta(script): return None
    c = (script or {}).get("cta")
    if isinstance(c, dict) and c.get("palavra") and c.get("promessa"): return c["palavra"], c["promessa"]
    k = next((l for l in texto.split("\n") if LC.RE_CTA.search(l)), None)
    if k:
        d = LC.detecta(k, p)
        if d and d.get("promessa"): return d["palavra"], d["promessa"]
    if p.get("sem_cta_sempre") or p.get("ab_sem_cta_padrao"): return None
    return LC.promessa_fixa(p)


def tema_de(script, brief=None):
    """Emoji do tema do vídeo: (definido, emoji|None). Fonte: script.cta.emoji_tema > script.emoji_tema > brief.emoji_tema.
    1 a 3 emojis (str ou lista); definido=True com None = tema sem emoji (vale o pool do perfil)."""
    c = (script or {}).get("cta")
    for fonte in ((c if isinstance(c, dict) else None), script, brief):
        if isinstance(fonte, dict) and "emoji_tema" in fonte:
            e = fonte.get("emoji_tema")
            if e is None or (isinstance(e, str) and not e.strip()) or (isinstance(e, (list, tuple)) and not e): return True, None
            return True, (LC.tema_render(e) if not LC.tema_erros(e) else e)
    return False, None


def brief_de(pasta):
    try: return json.loads((pathlib.Path(pasta) / "brief.json").read_text(encoding="utf-8"))
    except Exception: return None


def confere_tema_na_entrada(script, p, brief=None):
    """Edição COM CTA tem que trazer a decisão do emoji do tema (emoji ou null)."""
    if sem_cta(script) or palavra_e_promessa(script.get("caption", ""), p, script) is None: return []
    definido, e = tema_de(script, brief)
    if not definido: return ['sem o emoji do tema: grave script.json → cta.emoji_tema (1 a 3 emojis do que aparece no vídeo) ou null (_sistema/legenda.md)']
    if e is None: return []
    erros = [f"emoji_tema {e!r}: {x}" for x in LC.tema_erros(e)]
    if not erros: erros = [f"emoji_tema: {x}" for x in LC.tema_no_roteiro(e, script)]
    return erros


def com_palavra(texto, p, script=None, ed=None, horario=None, brief=None):
    """A legenda ABRE com o gancho e a frase de comentário vai para o CORPO (3ª linha em diante, antes das hashtags), com frase e emoji do banco do
    perfil (perfil.yaml → legenda_cta), sorteados por edição. SEM CTA: tira a chamada. Legenda que já está na regra volta igual (o post.py chama isto)."""
    pp = palavra_e_promessa(texto, p, script)
    if pp is None: return LC.tira_cta(texto) if sem_cta(script) or p.get("sem_cta_sempre") else texto
    pal, prom = pp
    tema = tema_de(script, brief)[1]
    if LC.ja_na_regra(texto, p, pal, prom, tema=tema): return texto
    ed_ = ed or ((script or {}).get("id")); ate_ = horario or HORARIO_LIMITE
    if tema and LC.ja_na_regra(texto, p, pal, prom):
        t = LC.troca_emoji(texto, p, pal, prom, tema)
        if t and not LC.confere(t, p, pal, prom, ed=ed_, ate=ate_, tema=tema): return t
    return LC.monta(texto, p, pal, prom, ed=ed_, ate=ate_, tema=tema)


def opc(p, chave, padrao=None):
    """Valor pontilhado do perfil; senão de perfis.yaml → padrao; senão `padrao`."""
    for fonte in (p or {}, CFG.get("padrao") or {}):
        v = fonte
        for k in chave.split("."):
            v = v.get(k) if isinstance(v, dict) else None
            if v is None: break
        if v is not None: return v
    return padrao


def confere_licao_rapida(corpo, faixa=(120, 450)):
    """Lição rápida: 1ª linha = título; depois exatamente 3 linhas numeradas (1. 2. 3.); a linha de chamada (se houver) não conta; corpo de 120–450 caracteres."""
    erros = []
    linhas = [l for l in corpo.split("\n") if l.strip() and not LC.RE_CTA.search(l)]
    if not linhas: return ["lição rápida: legenda vazia"]
    if NUMERADA.match(linhas[0]): erros.append("lição rápida: a 1ª linha é o título (sem número)")
    num = [NUMERADA.match(l).group(1) for l in linhas[1:] if NUMERADA.match(l)]
    soltas = [l for l in linhas[1:] if not NUMERADA.match(l)]
    if num != ["1", "2", "3"]: erros.append(f"lição rápida: depois do título vêm 3 linhas numeradas 1., 2., 3. (tem {num or 'nenhuma'})")
    if soltas: erros.append(f"lição rápida: linha fora do formato ({soltas[0][:50]!r}); só título + 3 linhas numeradas (+ a chamada, se houver)")
    if not faixa[0] <= len(corpo) <= faixa[1]: erros.append(f"{len(corpo)} caracteres (regra: {faixa[0]}–{faixa[1]}, lição rápida: _sistema/legenda.md)")
    return erros


def confere_legenda(texto, p=None, script=None, ed=None, horario=None, com_historico=True, brief=None):
    """_sistema/legenda.md: COM CTA → 1ª linha = gancho, 1 frase de comentário do banco no corpo; SEM CTA → nada de chamada/DM/urgência.
    Lição rápida (perfil.yaml → legenda.licao_rapida, padrão true): título + 3 linhas numeradas, 120–450 caracteres.
    Hashtags (perfil.yaml → hashtags): 3 fixas + 3 variáveis, linha em branco antes; sem banco = no máximo 3. ≤ 3 emojis; nenhuma palavra de venda."""
    p = p or {}; erros = []
    if sem_cta(script) or (p.get("sem_cta_sempre") and not (script or {}).get("cta")): erros += LC.confere_sem_cta(texto)
    else:
        pp = palavra_e_promessa(texto, p, script)
        if pp: erros += LC.confere(texto, p, pp[0], pp[1], ed=ed or (script or {}).get("id"), ate=horario or HORARIO_LIMITE, com_historico=com_historico,
                                   tema=tema_de(script, brief)[1])
        elif p.get("ab_sem_cta_padrao"): erros += LC.confere_sem_cta(texto)
    if LC.conta_emojis(texto) > 3: erros.append("mais de 3 emojis")
    ht = HT.config(p)
    corpo = HT.separa(texto)[0] if ht else texto
    if opc(p, "legenda.licao_rapida", True): erros += confere_licao_rapida(corpo, tuple(opc(p, "legenda.caracteres", [120, 450])))
    if ht: erros += HT.confere(texto, p, ed or (script or {}).get("id"), horario)
    elif len(re.findall(r"#\w+", texto)) > 3: erros.append("mais de 3 hashtags")
    achadas = [w for w in PROIBIDAS + list(opc(p, "legenda.proibidas", []) or []) if re.search(r"\b" + re.escape(w) + r"\b", texto.lower())]
    if achadas: erros.append(f"palavras proibidas: {achadas}")
    return erros


def confere_sem_cta_sempre(script, p):
    """Perfil com perfil.yaml → sem_cta_sempre: true não aceita edição NOVA com script.cta preenchido nem legenda pedindo comentário (só na entrada da fila)."""
    if not (p or {}).get("sem_cta_sempre") or (p or {}).get("dm_so_votacao"): return []
    erros = []
    if script.get("cta"): erros.append("perfil com sem_cta_sempre: script.json → cta tem que ser false/ausente (final de SEGUIR)")
    m = LC.CHAMADA_SEM.search(script.get("caption") or "")
    if m: erros.append(f'perfil com sem_cta_sempre: a legenda pede comentário/DM ("{m.group(0)}")')
    return erros


# ---------- palavra de comentário por vídeo (perfis com oferta.secoes) ----------
PALAVRAS_RESERVADAS = {"HOW", "YES", "WOW"}


def confere_cta_video(script, pasta, p):
    """Palavra POR VÍDEO (_sistema/palavras-comentario.md): 3–7 letras maiúsculas, única entre perfis e nas últimas 10 edições do perfil,
    promessa igual à da seção (perfil.yaml → oferta.secoes), sem preço, chamada falada no fim da narração."""
    erros, cta = [], script["cta"]; pal = (cta.get("palavra") or "").strip(); of = p.get("oferta") or {}
    if not re.fullmatch(r"[A-Z]{3,7}", pal): erros.append(f'palavra de comentário "{pal}" fora de 3–7 letras maiúsculas')
    outros = set(PALAVRAS_RESERVADAS) | {str((CFG["padrao"].get("curso") or {}).get("palavra", "")).upper()} - {""}
    for pf in CFG.get("perfis", []):
        if pf.get("pasta") != p.get("pasta") and (pf.get("oferta") or {}).get("palavra"): outros.add(str(pf["oferta"]["palavra"]).upper())
    if pal in outros: erros.append(f'palavra "{pal}" igual à de outro perfil ou reservada')
    if pal in {(o.get("cta") or {}).get("palavra") for _, o in anteriores(pasta, p, 10) if isinstance(o.get("cta"), dict)}:
        erros.append(f'palavra "{pal}" repetida das últimas 10 edições do perfil')
    sec = (of.get("secoes") or {}).get(cta.get("secao") or "")
    prom = (cta.get("promessa") or "").strip()
    if not sec: erros.append(f'seção "{cta.get("secao")}" fora de perfil.yaml → oferta.secoes')
    elif prom != sec.get("promessa"): erros.append(f'promessa "{prom}" diferente da da seção ("{sec.get("promessa")}")')
    if re.search(r"\$|\bfree\b|\bcourse\b|\bbio\b|\bprice\b|\d+\s*(usd|dollars?)", prom, re.I): erros.append(f'promessa com preço/free/course/bio: "{prom}"')
    narr = pasta / "narracao.txt"
    if narr.exists():
        txt_n = re.sub(r"\[[^\]]*\]", "", narr.read_text(encoding="utf-8")).strip()
        ult_c = list(re.finditer(rf"\bcomment\s+{pal}\b", txt_n, re.I))
        if not ult_c or len(txt_n) - ult_c[-1].end() > 140: erros.append(f'a narração não termina com "Comment {pal} …"')
    return erros


# ---------- formato vizinho na grade ----------
def formato_da_edicao(ed, script=None, perfil=None):
    """Formato de uma edição do perfil (pasta): capa.formato, montagem.formato, script.formato ou a coluna 'formato' do pautas.csv; sem nada = padrao."""
    if not perfil: raise ValueError("formato_da_edicao: informe a pasta do perfil")
    pasta = ROOT / perfil / "out" / ed
    try: s = script or json.loads((pasta / "script.json").read_text(encoding="utf-8"))
    except Exception: s = {}
    f = (s.get("capa") or {}).get("formato") or (s.get("montagem") or {}).get("formato") or s.get("formato") or s.get("format")
    if f: return f
    try:
        import csv
        for r in csv.DictReader((ROOT / perfil / "pautas.csv").read_text(encoding="utf-8").splitlines()):
            if r.get("usado_em") == ed: return r.get("formato") or "padrao"
    except Exception: pass
    return "padrao"


def confere_formato_vizinho(script, pasta, perfil):
    """qualidade.formato_varia: o mesmo formato não fica a menos de 2 posts de distância na ordem de publicação (a grade não repete a forma de tela)."""
    try:
        import grade
        seq = [i for _, i in grade.sequencia(perfil)]
    except Exception: return []
    ed = pasta.name; meu = formato_da_edicao(ed, script, perfil)
    if ed in seq: k = seq.index(ed)
    else: seq = seq + [ed]; k = len(seq) - 1
    erros = []
    for d in (-2, -1, 1, 2):
        j = k + d
        if 0 <= j < len(seq) and meu != "padrao" and formato_da_edicao(seq[j], None, perfil) == meu:
            erros.append(f'formato "{meu}" igual ao de {seq[j]}, a {abs(d)} post(s) na grade (varie o formato)')
    return erros


# ---------- contexto dos gates e plugin do perfil ----------
def ler_json(f, padrao=None):
    try: return json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
    except Exception: return padrao


def anteriores(pasta, p, n=4):
    """[(id, script)] das edições do perfil na fila e no ar com horário antes desta (mais recente primeiro), no máximo n."""
    base = ROOT / p["pasta"]; itens = []
    for d in ("04-aprovado", "05-publicado"):
        for f in (base / "posts" / d).glob("*.json") if (base / "posts" / d).exists() else []:
            if f.name.startswith("._"): continue
            it = ler_json(f) or {}
            if not it.get("id") or it["id"] == pasta.name: continue
            if HORARIO_LIMITE is None or it.get("horario", "") < HORARIO_LIMITE: itens.append((it.get("horario", ""), it["id"]))
    out = []
    for _, i in sorted(set(itens), reverse=True):
        s = ler_json(base / "out" / i / "script.json")
        if s is not None: out.append((i, s))
        if len(out) >= n: break
    return out


def monta_ctx(pasta, p):
    """O `ctx` dos gates universais e do plugin <perfil>/gates.py (contrato em CHAVES-PERFIL.md)."""
    pasta = pathlib.Path(pasta).resolve()
    return {"ROOT": ROOT, "pasta": pasta, "id": pasta.name, "perfil": p, "padrao": CFG.get("padrao") or {},
            "script": ler_json(pasta / "script.json", {}), "brief": brief_de(pasta), "words": ler_json(pasta / "words.json"),
            "render_check": ler_json(pasta / "render_check.json"), "mix_check": ler_json(pasta / "mix_check.json"), "qa": ler_json(pasta / "qa.json", {}),
            "anteriores": lambda n=4: anteriores(pasta, p, n), "opc": lambda chave, padrao=None: opc(p, chave, padrao)}


def normaliza(lista, gate):
    """Achados do plugin: dict {nivel, gate, msg} ou str (= erro)."""
    out = []
    for x in lista or []:
        if isinstance(x, str): out.append({"nivel": "erro", "gate": gate, "msg": x})
        elif isinstance(x, dict) and x.get("msg"): out.append({"nivel": x.get("nivel") if x.get("nivel") in ("erro", "aviso") else "erro", "gate": x.get("gate") or gate, "msg": str(x["msg"])})
        else: out.append({"nivel": "erro", "gate": gate, "msg": f"achado fora do contrato: {x!r}"[:200]})
    return out


def gates_do_perfil(ctx):
    """Plugin <pasta do perfil>/gates.py → gates(ctx) -> list[dict|str]. Sem o arquivo: []. Arquivo que quebra = erro (falha fechada)."""
    arq = ROOT / ctx["perfil"]["pasta"] / "gates.py"
    if not arq.exists(): return []
    nome = "gates_perfil_" + re.sub(r"\W", "_", ctx["perfil"]["pasta"])
    try:
        spec = importlib.util.spec_from_file_location(nome, arq); mod = importlib.util.module_from_spec(spec)
        sys.modules[nome] = mod; spec.loader.exec_module(mod)
        if not callable(getattr(mod, "gates", None)): return [{"nivel": "erro", "gate": "plugin", "msg": f"{arq.relative_to(ROOT)} sem a função gates(ctx)"}]
        return normaliza(mod.gates(ctx), "plugin")
    except Exception as e:
        return [{"nivel": "erro", "gate": "plugin", "msg": f"{arq.relative_to(ROOT)} falhou: {type(e).__name__}: {e}"}]


# ---------- perfis ----------
def lista_perfis():
    if not CFG["perfis"]: return "nenhum perfil configurado (perfis.yaml → ordem: []). Crie um perfil a partir de _modelo-perfil/ e ponha a pasta em `ordem`."
    return "perfis: " + ", ".join(f'{p.get("pasta")} ({p.get("prefixo", "?")}, {p.get("status", "?")})' for p in CFG["perfis"])


def acha_perfil(chave):
    return next((p for p in CFG["perfis"] if chave in (p.get("pasta"), p.get("prefixo"), p.get("handle"))), None)


def perfil_da_pasta(pasta):
    try: perfil_pasta = pathlib.Path(pasta).resolve().relative_to(ROOT).parts[0]
    except ValueError: return None
    return acha_perfil(perfil_pasta)


# ---------- entrada na fila ----------
def main(pasta, p):
    pasta = pathlib.Path(pasta).resolve(); perfil_pasta = p["pasta"]
    pj_ = pasta / "post.json"   # edição já publicada não entra de novo; republicar de propósito: INSTAGRANS_REPUBLICAR=1
    if pj_.exists() and not os.environ.get("INSTAGRANS_REPUBLICAR"):
        pub_ = ler_json(pj_, {})
        if pub_.get("status") == "publicado" or pub_.get("media_id"): sys.exit(f"{pasta.name} já foi publicada ({pub_.get('permalink', 'sem link')}): não entra na fila de novo (INSTAGRANS_REPUBLICAR=1 para forçar)")
    for arq, chave in (("qa.json", "verdict"), ("render_check.json", "passou"), ("mix_check.json", "passou")):
        d = ler_json(pasta / arq)
        if d is None: sys.exit(f"{arq} ausente: rode a etapa antes")
        if chave == "verdict" and d.get("aprovado_dono"): continue   # o dono aprovou à mão (qa.json → aprovado_dono); o veredito do QA continua registrado
        if d.get(chave) not in ("pass", True): sys.exit(f"{arq} não aprovado: não entra na fila")
    fila = ROOT / perfil_pasta / "posts" / "04-aprovado"; fila.mkdir(parents=True, exist_ok=True)
    itens = {f: ler_json(f, {}) for f in fila.glob("*.json")}
    if any(i.get("id") == pasta.name for i in itens.values()): sys.exit(f"{pasta.name} já está na fila")
    script = ler_json(pasta / "script.json")
    if script is None: sys.exit("script.json ausente")
    periodo = script.get("periodo")
    so = (p.get("periodos") or {}).get(periodo) if periodo else None   # script.periodo → perfil.yaml → periodos: o post sai nesse horário
    if periodo and p.get("periodos") and not so: sys.exit(f"período {periodo!r} não existe em perfil.yaml → periodos")
    brief = brief_de(pasta)
    erros = confere_tema_na_entrada(script, p, brief) + confere_sem_cta_sempre(script, p)
    if erros: sys.exit(f"legenda fora da regra (_sistema/legenda.md): {'; '.join(erros)}")
    script["caption"] = com_palavra(script.get("caption", ""), p, script, ed=pasta.name, brief=brief)
    script["caption"] = HT.aplica(script["caption"], p, pasta.name)
    erros = [{"nivel": "erro", "gate": "legenda", "msg": e} for e in confere_legenda(script["caption"], p, script, ed=pasta.name, brief=brief)]
    if script.get("cta") and (p.get("oferta") or {}).get("secoes") and not p.get("dm_so_votacao"):
        erros += [{"nivel": "erro", "gate": "cta", "msg": e} for e in confere_cta_video(script, pasta, p)]
    if opc(p, "qualidade.formato_varia", False):
        erros += [{"nivel": "erro", "gate": "variacao", "msg": e} for e in confere_formato_vizinho(script, pasta, perfil_pasta)]
    import gates_universais as GU
    ctx = monta_ctx(pasta, p); ctx["script"] = script
    erros += GU.roda(ctx) + gates_do_perfil(ctx)
    for a in [x for x in erros if x["nivel"] == "aviso"]: print(f'AVISO ({a["gate"]}): {a["msg"]}')
    bloqueia = [x for x in erros if x["nivel"] == "erro"]
    if bloqueia and (ctx["qa"] or {}).get("aprovado_dono"):   # dono viu e aprovou: só achados de LAYOUT (área segura) deixam de bloquear
        leves = [x for x in bloqueia if x["gate"] == "area_segura"]
        for x in leves: print(f'AVISO (aprovado pelo dono, não bloqueia): {x["msg"]}')
        bloqueia = [x for x in bloqueia if x not in leves]
    if bloqueia: sys.exit("não entra na fila:\n- " + "\n- ".join(f'[{x["gate"]}] {x["msg"]}' for x in bloqueia))
    depois = None
    if p.get("serie"):   # série por personagem (perfil.yaml → serie): a edição usa o personagem da vez e entra depois do último da fila
        import serie
        vez, n = serie.da_vez(perfil_pasta)
        if script.get("personagem") != vez: sys.exit(f'série por personagem: o da vez é {vez} ({n} de {p["serie"].get("tamanho", 3)}), esta edição usa {script.get("personagem")!r} (script.json → personagem)')
        depois = max((dt.datetime.strptime(i["horario"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ) for i in itens.values() if i.get("horario")), default=None)
    if p.get("fila_em_ordem"):   # cada edição promete a próxima: nunca entra num buraco antes da última da fila
        depois = max((dt.datetime.strptime(i["horario"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ) for i in itens.values() if i.get("horario")), default=None)
    slot = proximo_horario(p, {i.get("horario") for i in itens.values()}, so, depois)
    item = {"id": pasta.name, "horario": slot.strftime("%Y-%m-%d %H:%M"), "fuso": str(TZ),
            "video": (pasta / "video.mp4").relative_to(ROOT).as_posix(), "capa": (pasta / "cover.jpg").relative_to(ROOT).as_posix(),
            "legenda": script["caption"], "capa_offset_ms": int((script.get("scene") or {}).get("capa_t", (script.get("capa") or {}).get("t", 1.0)) * 1000),
            "qa": (ctx["qa"] or {}).get("media_ponderada"),
            **({"ab_cta": bool(script["ab_cta"])} if "ab_cta" in script else {})}
    destino = fila / f'{slot.strftime("%Y-%m-%d_%H%M")}.json'
    destino.write_text(json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")
    try:   # conferência em movimento: out/<id>/movimento.json e folhas densas (0,5 s) em out/<id>/movimento/ para o revisor; só AVISO
        import movimento
        r_ = movimento.confere(pasta / "video.mp4"); r_["folhas_densas"] = movimento.folhas_densas(pasta / "video.mp4", pasta / "movimento", 0.5)
        (pasta / "movimento.json").write_text(json.dumps(r_, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e: print("AVISO movimento.py:", e)
    try:
        import drive; drive.enviar(perfil_pasta, pasta.name)   # cópia para a pasta do Drive (.env → DRIVE_PASTA; vazio = desligado); nunca bloqueia
    except Exception as e: print("AVISO drive.py:", e)
    LC.registra(p, pasta.name, item["horario"], item["legenda"])   # histórico da chamada da legenda (reviews/legendas.jsonl)
    (ROOT / perfil_pasta / "posts" / "02-em-producao" / f"{pasta.name}.json").unlink(missing_ok=True)
    if script.get("montagem"):   # histórico do sorteio de execução (quem sorteia lê para não repetir)
        h = ROOT / perfil_pasta / "reviews" / "montagens.jsonl"; h.parent.mkdir(parents=True, exist_ok=True)
        with h.open("a", encoding="utf-8") as f_: f_.write(json.dumps({**script["montagem"], "edicao": pasta.name}, ensure_ascii=False) + "\n")
    if opc(p, "qualidade.grade_por_ordem", False):   # cor da capa pela ordem real de publicação (grade.py): corrige esta e as seguintes, refazendo só a capa
        import grade
        for x in grade.acertar_fila(perfil_pasta): print(f'capa da grade: {x["id"]} {x["de"]} -> {x["para"]} ({"ok" if x["capa_ok"] else "FALHOU: " + x["saida"]})')
    if len((p.get("grade") or {}).get("ciclo") or []) > 1:   # confere o feed real e a fila (feed_check.py); o post.py barra a publicação se a cor quebrar
        try:
            import feed_check
            r = feed_check.conferir(perfil_pasta)
            print("feed_check:", "ok" if r["ok"] else "PROBLEMAS → " + " | ".join(r["problemas"]))
        except Exception as e: print(f"feed_check não rodou ({e})")
    print(f"{pasta.name} na fila: {destino.relative_to(ROOT)} ({item['horario']} {TZ})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n", 1)[1])
    ap.add_argument("edicao", nargs="?", help="caminho <perfil>/out/<id> ou só o <id> (com --perfil)")
    ap.add_argument("--perfil", help="pasta, prefixo ou handle do perfil")
    ap.add_argument("--listar", action="store_true", help="lista os perfis configurados e sai")
    a = ap.parse_args()
    if a.listar: print(lista_perfis()); sys.exit(0)
    if not a.edicao: print(lista_perfis()); sys.exit("informe a edição: fila.py <perfil>/out/<id>  ou  fila.py --perfil <perfil> <id>")
    if a.perfil:
        p = acha_perfil(a.perfil)
        if not p: print(lista_perfis()); sys.exit(f"perfil não encontrado: {a.perfil}")
        ed = pathlib.Path(a.edicao)
        pasta = ed if ed.is_absolute() or len(ed.parts) > 1 else ROOT / p["pasta"] / "out" / a.edicao
    else:
        pasta = pathlib.Path(a.edicao)
        p = perfil_da_pasta(pasta)
        if not p: print(lista_perfis()); sys.exit(f"não achei o perfil de {a.edicao}: passe --perfil <perfil> ou o caminho <perfil>/out/<id>")
    if not pathlib.Path(pasta).exists(): sys.exit(f"edição não encontrada: {pasta}")
    main(pasta, p)
