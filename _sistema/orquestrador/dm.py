"""Resposta automática por DM: quem comenta a palavra-chave do perfil recebe por DM privada o link do 1º produto (`link_gratis`: nome histórico; pode ser pago, o preço só aparece na página)
(resposta privada a comentário, API do Instagram com login do Facebook) + uma resposta pública curta no comentário.
Segunda porta: nos perfis com curso_dm: true, o comentário que é só "HOW" recebe o link do curso (padrao.curso no perfis.yaml).
Cada comentário é respondido uma vez (registro em <perfil>/posts/dm_respondidos.json). Só vale até 7 dias após o comentário.
Uso (na raiz do projeto):
  python _sistema/orquestrador/dm.py [--perfil X] [--dry-run]       envia só nos perfis com oferta.dm_ativa e link_gratis
  python _sistema/orquestrador/dm.py --perfil X --teste-link URL     envia com um link de teste (para o 1º teste com conta própria)
Precisa no Instagram: Configurações → Mensagens → Ferramentas conectadas → "Permitir acesso às mensagens" ligado."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, datetime as dt, json, os, pathlib, random, re, sys, time
import requests, yaml
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")
CFG = carrega(ROOT)
G = f'https://graph.facebook.com/{os.getenv("META_GRAPH_VERSION") or "v26.0"}'
JANELA = dt.timedelta(days=7)  # limite da Meta para resposta privada

def api(metodo, caminho, **kw):
    r = requests.request(metodo, f"{G}/{caminho}", timeout=60, **kw)
    if not r.ok: raise RuntimeError(f"{metodo} {caminho} → {r.status_code}: {r.text[:300]}")
    return r.json()

def pagina(url, params):
    while url:
        d = requests.get(url, params=params, timeout=60).json()
        if "error" in d: raise RuntimeError(d["error"].get("message"))
        yield from d.get("data", [])
        url, params = d.get("paging", {}).get("next"), None

# Palavra de comentário POR VÍDEO: cada edição publicada traz script.cta = {palavra, promessa}; o comentário só dispara a DM
# no post dono da palavra (media_id em out/<id>/post.json). Posts antigos, sem script.cta, seguem a palavra fixa do perfil (oferta.palavra).
RESPOSTAS_PADRAO = ["sent 🟨 check your DMs", "on its way 🟨 look in your DMs", "dropped it in your DMs 🟨", "check your inbox 🟨", "your DMs 🟨 go look"]
DM_PADRAO = "here's {promessa} 🟨 {link}"

def formato_de(sc):
    """Chave da âncora/da DM: montagem.formato (quando a montagem é um dicionário) ou cta.formato (quando a montagem é texto)."""
    m = sc.get("montagem"); c = sc.get("cta") or {}
    return (m.get("formato") if isinstance(m, dict) else None) or c.get("formato") or ""

def por_midia(p):
    """{media_id: {palavra, promessa, formato, edicao}} das edições publicadas com chamada por vídeo."""
    out = {}
    for pj in (ROOT / p["pasta"] / "out").glob("*/post.json"):
        try:
            post = json.loads(pj.read_text(encoding="utf-8")); sj = pj.parent / "script.json"
            cta = (json.loads(sj.read_text(encoding="utf-8")).get("cta") or {}) if sj.exists() else {}
            if cta.get("palavra") and post.get("media_id"):
                formato = formato_de(json.loads(sj.read_text(encoding="utf-8")))
                out[post["media_id"]] = {"palavra": cta["palavra"], "promessa": cta.get("promessa", ""), "formato": formato, "edicao": pj.parent.name}
        except Exception: continue
    return out

def sem_cta(p):
    """media_ids das edições publicadas SEM chamada (brief.json → cta: false, teste A/B): a palavra fixa do perfil não vale nesses posts."""
    out = set()
    for pj in (ROOT / p["pasta"] / "out").glob("*/post.json"):
        try:
            brief = pj.parent / "brief.json"
            if brief.exists() and json.loads(brief.read_text(encoding="utf-8")).get("cta") is False:
                mid = json.loads(pj.read_text(encoding="utf-8")).get("media_id")
                if mid: out.add(mid)
        except Exception: continue
    return out

def resposta_do_video(of, info, link, comentario_id):
    """DM e resposta pública do vídeo: o modelo da DM e as respostas vêm de perfil.yaml → oferta (dm_por_video, respostas_publicas, ancoras), com padrão no código."""
    ancora = (of.get("ancoras") or {}).get(info.get("formato") or "padrao", "")
    modelo = of.get("dm_por_video") or DM_PADRAO
    respostas = of.get("respostas_publicas") or RESPOSTAS_PADRAO
    resp = respostas[sum(map(ord, str(comentario_id))) % len(respostas)]   # varia entre as frases, sempre a mesma para o mesmo comentário
    return {"dm": modelo.replace("{promessa}", info.get("promessa", "the file")).replace("{palavra}", info["palavra"]).replace("{link}", ((of.get("link_dm_base") if ancora else None) or link or "{link}") + ancora), "resposta_publica": resp}

def simular(p):
    """Teste sem enviar nada: para cada edição publicada ou na fila com chamada por vídeo, mostra a DM e a resposta pública que sairiam."""
    of = p.get("oferta") or {}; vistos = []
    for pasta in ("04-aprovado", "05-publicado"):
        for f in sorted((ROOT / p["pasta"] / "posts" / pasta).glob("*.json")):
            try: it = json.loads(f.read_text(encoding="utf-8")); sj = ROOT / p["pasta"] / "out" / it["id"] / "script.json"; sc = json.loads(sj.read_text(encoding="utf-8"))
            except Exception: continue
            cta = sc.get("cta") or {}
            if not cta.get("palavra"): continue
            info = {"palavra": cta["palavra"], "promessa": cta.get("promessa", ""), "formato": formato_de(sc)}
            r = resposta_do_video(of, info, of.get("link_gratis"), "teste-" + cta["palavra"])
            vistos.append({"edicao": it["id"], "palavra": cta["palavra"], "comentario_simulado": f'love this! {cta["palavra"].lower()} please', "casa": bool(re.search(rf'\b{re.escape(cta["palavra"])}\b', "love this! " + cta["palavra"].lower() + " please", re.I)), **r})
    return vistos

RESPOSTAS_VOTACAO = ["voto contado 🗳️", "anotado 🗳️ valendo!", "seu voto entrou 🗳️", "contabilizado 🗳️", "voto na urna 🗳️"]

VARIANTES_PADRAO = {"PUXAR": [r"pux\w{0,3}", r"pus+ar"], "SUBIR": [r"sub\w{0,3}", r"sob\w{0,3}"]}   # pt-BR: "puxa/puxo/eu puxo/pussar", "sobe/sobre/sobee/suba/subo"

def _radicais(w, cfg):
    """Padrões extras de uma opção: lista própria (votacao_variantes: {PALAVRA: [regex]}), a tabela padrão ou o radical do verbo (tira ar/er/ir/r)."""
    if isinstance(cfg, dict) and cfg.get(w): return list(cfg[w])
    if w.upper() in VARIANTES_PADRAO: return VARIANTES_PADRAO[w.upper()]
    base = re.sub(r"(ar|er|ir|r)$", "", w.lower())
    return [re.escape(base) + r"\w{0,3}"] if len(base) >= 3 else []

def opcoes_do_comentario(p, info, texto):
    """Opções da votação citadas no comentário. Sempre vale a palavra exata; com `votacao_variantes: true` (ou dicionário) no perfil também valem as variações
    (variações de escrita também contam). Quem cita as duas opções, ou nenhuma, não vota (quem chama já exige len == 1)."""
    texto = texto or ""; cfg = p.get("votacao_variantes"); out = []
    for w in info["palavras"]:
        exato = rf'(?<![\w-]){"[- ]?".join(map(re.escape, w.split("-")))}(?![\w-])'
        pads = [exato] + ([rf'(?<![\w-])(?:{x})(?![\w-])' for x in _radicais(w, cfg)] if cfg else [])
        if any(re.search(x, texto, re.I) for x in pads): out.append(w)
    return out

def votacoes(p):
    """{media_id: {edicao, palavras}} das edições publicadas do formato votação (script.json → votacao.opcoes)."""
    out = {}
    for pj in (ROOT / p["pasta"] / "out").glob("*/post.json"):
        try:
            mid = json.loads(pj.read_text(encoding="utf-8")).get("media_id"); sj = pj.parent / "script.json"
            ops = ((json.loads(sj.read_text(encoding="utf-8")).get("votacao") or {}).get("opcoes") or []) if sj.exists() else []
            pals = [o["palavra"] for o in ops if o.get("palavra")]
            if mid and len(pals) == 2: out[mid] = {"edicao": pj.parent.name, "palavras": pals}
        except Exception: continue
    return out

def processar_votacao(p, dry_run=False):
    """Perfis com dm_so_votacao: sem oferta, sem DM e sem link. Quem comenta uma das 2 palavras da votação recebe só uma resposta
    pública curta (uma vez por comentário) e o voto entra na contagem (out/<edição>/votacao.json → contagem; a vencedora é fechada por fecha_votacoes)."""
    uid, tok = os.getenv(p["user_id_env"], "").strip(), os.getenv(p["token_env"], "").strip()
    if not (uid and tok): return {"perfil": p["handle"], "pulado": "sem token"}
    vots = votacoes(p); reg_arq = ROOT / p["pasta"] / "posts" / "dm_respondidos.json"
    reg = json.loads(reg_arq.read_text(encoding="utf-8")) if reg_arq.exists() else {}
    agora = dt.datetime.now(dt.timezone.utc); proprio = p["handle"].lstrip("@").lower()
    respostas = p.get("votacao_respostas") or RESPOSTAS_VOTACAO; achados = []; votos = {}; votou = {}; mts = {}; primeiro = {}
    for r in reg.values():
        if r.get("voto") and r.get("edicao"): votou.setdefault(r["edicao"], set()).add((r.get("usuario") or "").lower())
    if vots:
        for m in pagina(f"{G}/{uid}/media", {"fields": "id,timestamp", "limit": 25, "access_token": tok}):
            if agora - dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) > JANELA + dt.timedelta(days=1): break
            info = vots.get(m["id"])
            if not info: continue
            mts[info["edicao"]] = m["timestamp"]
            for c in pagina(f"{G}/{m['id']}/comments", {"fields": "id,text,username,timestamp", "limit": 50, "access_token": tok}):
                if (c.get("username") or "").lower() == proprio: continue
                achou = opcoes_do_comentario(p, info, c.get("text"))
                if len(achou) != 1: continue   # sem palavra, ou as duas no mesmo comentário (não vale como voto)
                quem = (c.get("username") or "").lower()
                if quem in votou.setdefault(info["edicao"], set()) and c["id"] not in reg: continue   # 1 resposta por pessoa por vídeo
                votou[info["edicao"]].add(quem)
                votos.setdefault(info["edicao"], {}).setdefault(achou[0], set()).add(quem)
                primeiro.setdefault(info["edicao"], {})[achou[0]] = min(c.get("timestamp") or "9", primeiro.get(info["edicao"], {}).get(achou[0], "9"))
                if c["id"] in reg: continue
                item = {"comentario": c["id"], "usuario": c.get("username"), "texto": c.get("text"), "voto": achou[0], "edicao": info["edicao"]}
                if not dry_run:
                    try:
                        api("POST", f"{c['id']}/replies", data={"message": f'@{c.get("username")} {respostas[sum(map(ord, str(c["id"]))) % len(respostas)]}', "access_token": tok})
                        item["resposta_publica"] = "ok"; reg[c["id"]] = {**item, "em": agora.isoformat(timespec="seconds")}
                    except Exception as e: item["erro"] = str(e)
                achados.append(item)
    contagem = {ed: {w: len(us) for w, us in d.items()} for ed, d in votos.items()}
    if not dry_run:
        if achados: reg_arq.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
        for ed, cont in contagem.items():
            vj = ROOT / p["pasta"] / "out" / ed / "votacao.json"
            try: j = json.loads(vj.read_text(encoding="utf-8")) if vj.exists() else {}
            except Exception: j = {}
            j["contagem"] = cont; j["contagem_em"] = agora.isoformat(timespec="seconds"); vj.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    fechadas = fecha_votacoes(p, vots, contagem, mts, primeiro, agora, dry_run)
    res = {"perfil": p["handle"], "modo": "so_votacao", "votacoes_publicadas": len(vots), "enviando": not dry_run, "contagem": contagem, "fechadas": fechadas, "respostas": achados}
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "dm.log").open("a", encoding="utf-8") as f: f.write(json.dumps({"em": agora.isoformat(timespec="seconds"), **res}, ensure_ascii=False) + "\n")
    return res

def fecha_votacoes(p, vots, contagem, mts, primeiro, agora, dry_run):
    """Fecha a votação sozinha (vence a mais votada e vira pauta prioritária). Regra: 24 h depois do post
    (`perfil.yaml → votacao_fecha_h`), vence a palavra com MAIS pessoas diferentes; empate espera até 48 h e então vence quem recebeu o 1º voto;
    sem nenhum voto em 48 h, sorteia a palavra (prioridade 'sorteio', abaixo de 'votacao'). Ao fechar: grava vencedora em votacao.json e põe uma pauta com prioridade "votacao" no
    pautas.csv (o orquestrador pega pautas com prioridade primeiro) + arquivo posts/VOTACAO-VENCEDORA-<edição>.md para a sessão de produção."""
    h = float(p.get("votacao_fecha_h") or 24); fechou = []
    info_por_ed = {v["edicao"]: v for v in vots.values()}
    for ed, info in info_por_ed.items():
        if ed not in mts: continue
        vj = ROOT / p["pasta"] / "out" / ed / "votacao.json"
        try: j = json.loads(vj.read_text(encoding="utf-8")) if vj.exists() else {}
        except Exception: j = {}
        if j.get("vencedora"): continue
        idade = (agora - dt.datetime.fromisoformat(mts[ed].replace("+0000", "+00:00"))).total_seconds() / 3600
        if idade < h: continue
        cont = contagem.get(ed, {}); a, b = info["palavras"]; na, nb = cont.get(a, 0), cont.get(b, 0)
        if na == nb:
            if idade < 2 * h:
                fechou.append({"edicao": ed, "situacao": "empate/sem votos: espera"}); continue
            if na == 0:   # sem voto em 48 h, SORTEIA (determinístico por edição); a pauta não precisa ser a próxima da fila
                venc = random.Random(f"{p['pasta']}:{ed}").choice([a, b]); motivo = "sem votos em 48 h: palavra sorteada"
            else:
                pr = primeiro.get(ed, {}); venc = min((a, b), key=lambda w: pr.get(w, "9")); motivo = "empate: venceu o 1º voto"
        else: venc = a if na > nb else b; motivo = "mais votos"
        perd = b if venc == a else a
        item = {"edicao": ed, "vencedora": venc, "perdedora": perd, "contagem": cont, "motivo": motivo}
        if not dry_run:
            j.update({"vencedora": venc, "contagem": cont, "fechada_em": agora.date().isoformat(), "motivo": motivo})
            vj.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
            item["pauta"] = pauta_da_vencedora(p, ed, venc, perd, cont, motivo)
        fechou.append(item)
    return fechou

def pauta_da_vencedora(p, ed, venc, perd, cont, motivo):
    import csv
    sj = json.loads((ROOT / p["pasta"] / "out" / ed / "script.json").read_text(encoding="utf-8"))
    explica = next((o.get("explica", "") for o in sj["votacao"]["opcoes"] if o.get("palavra") == venc), "")
    arq = ROOT / p["pasta"] / "pautas.csv"; linhas = list(csv.DictReader(arq.read_text(encoding="utf-8").splitlines()))
    tema = f"{venc}: {explica}".strip(": ")
    if any(l.get("tema") == tema for l in linhas): return "já existia"
    novo = {k: "" for k in linhas[0].keys()}
    novo.update({"tema": tema, "angulo": f"VENCEDORA DA VOTAÇÃO {ed} ({motivo}; {cont}): o público pediu {venc} ({explica}). Vídeo de fatos no formato padrão com ângulo novo (se o tema já saiu em outra edição, outro ângulo); pode dizer que a votação escolheu. Perdedora: {perd}.",
                 "formato": "padrao", "prioridade": "sorteio" if motivo.startswith("sem votos") else "votacao"})
    linhas.append(novo)
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)
    (ROOT / p["pasta"] / "posts" / f"VOTACAO-VENCEDORA-{ed}.md").write_text(
        f"# Votação {ed} fechada\n\nVenceu **{venc}** ({motivo}; contagem {cont}). Pauta com prioridade `votacao` já está no topo do `pautas.csv`: produza esse vídeo antes das outras pautas. Apague este arquivo quando a edição entrar em produção.\n", encoding="utf-8")
    return "pauta criada"

def processar(p, dry_run=False, teste_link=None):
    if p.get("dm_so_votacao"): return processar_votacao(p, dry_run)
    of = p.get("oferta") or {}
    uid, tok = os.getenv(p["user_id_env"], "").strip(), os.getenv(p["token_env"], "").strip()
    if not (of and uid and tok): return {"perfil": p["handle"], "pulado": "sem oferta ou sem token"}
    link = teste_link or of.get("link_gratis")
    enviar = not dry_run and bool(link) and (of.get("dm_ativa") or teste_link)
    cu = CFG["padrao"].get("curso") or {}
    curso = not dry_run and not teste_link and bool(p.get("curso_dm") and cu.get("link"))
    reg_arq = ROOT / p["pasta"] / "posts" / "dm_respondidos.json"
    reg = json.loads(reg_arq.read_text(encoding="utf-8")) if reg_arq.exists() else {}
    agora = dt.datetime.now(dt.timezone.utc)
    padrao = re.compile(rf'\b{re.escape(of["palavra"])}\b', re.I)
    # curso: só o comentário que é a palavra sozinha ("how do I…" é dúvida do nicho, não pedido do curso)
    padrao_curso = re.compile(rf'[\W_]*{re.escape(cu.get("palavra", "HOW"))}[\W_]*', re.I) if p.get("curso_dm") else None
    proprio = p["handle"].lstrip("@").lower()
    videos = por_midia(p)   # palavra por vídeo: só vale no post dono dela
    sem_chamada = sem_cta(p)   # post sem CTA: nem a palavra fixa dispara a DM (o curso, só com a palavra sozinha, segue valendo)
    pag_id = api("GET", "me", params={"fields": "id", "access_token": tok})["id"]
    achados = []
    for m in pagina(f"{G}/{uid}/media", {"fields": "id,timestamp,permalink", "limit": 25, "access_token": tok}):
        if agora - dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) > JANELA + dt.timedelta(days=1): break
        for c in pagina(f"{G}/{m['id']}/comments", {"fields": "id,text,username,timestamp", "limit": 50, "access_token": tok}):
            quando = dt.datetime.fromisoformat(c["timestamp"].replace("+0000", "+00:00"))
            if c["id"] in reg or (c.get("username") or "").lower() == proprio or agora - quando > JANELA: continue
            texto = c.get("text") or ""
            info = videos.get(m["id"])
            if info:   # este post tem a palavra dele: só ela dispara (a fixa do perfil vale para os posts antigos)
                if re.search(rf'\b{re.escape(info["palavra"])}\b', texto, re.I): oferta, url, vai = {**of, **resposta_do_video(of, info, link, c["id"])}, "", enviar
                elif padrao_curso and padrao_curso.fullmatch(texto): oferta, url, vai = cu, of.get("link_curso") or cu.get("link"), curso
                else: continue
            elif m["id"] in sem_chamada:
                if padrao_curso and padrao_curso.fullmatch(texto): oferta, url, vai = cu, of.get("link_curso") or cu.get("link"), curso
                else: continue
            elif padrao.search(texto): oferta, url, vai = of, link, enviar
            elif padrao_curso and padrao_curso.fullmatch(texto): oferta, url, vai = cu, of.get("link_curso") or cu.get("link"), curso   # link_curso: página do curso com a cara do perfil
            else: continue
            item = {"comentario": c["id"], "usuario": c.get("username"), "texto": texto, "post": m.get("permalink"),
                    "oferta": "curso" if oferta is cu else "gratis"}
            if vai:
                try:
                    api("POST", f"{pag_id}/messages", json={"recipient": {"comment_id": c["id"]}, "message": {"text": oferta["dm"].replace("{link}", url)}},
                        params={"access_token": tok})
                    item["dm"] = "enviada"
                    if oferta.get("resposta_publica"):
                        api("POST", f"{c['id']}/replies", data={"message": f'@{c.get("username")} {oferta["resposta_publica"]}', "access_token": tok})
                        item["resposta_publica"] = "ok"
                    reg[c["id"]] = {**item, "em": agora.isoformat(timespec="seconds"), "teste": bool(teste_link)}
                except Exception as e:
                    item["erro"] = str(e)
            achados.append(item)
    if enviar or curso: reg_arq.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    res = {"perfil": p["handle"], "palavra": of["palavra"], "enviando": enviar, "curso_dm": curso,
           "motivo_sem_envio": None if enviar else ("dry-run" if dry_run else "sem link_gratis" if not link else "dm_ativa: false"),
           "comentarios_com_palavra": achados}
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "dm.log").open("a", encoding="utf-8") as f: f.write(json.dumps({"em": agora.isoformat(timespec="seconds"), **res}, ensure_ascii=False) + "\n")
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--perfil"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--teste-link")
    ap.add_argument("--simular", action="store_true", help="mostra a DM e a resposta pública de cada palavra por vídeo, sem enviar nada")
    a = ap.parse_args()
    if a.simular:
        for p in [x for x in CFG["perfis"] if x.get("status") == "ativo" and (not a.perfil or a.perfil in (x["prefixo"], x["handle"], x["pasta"]))]:
            print(json.dumps({"perfil": p["handle"], "simulacao": simular(p)}, ensure_ascii=False, indent=1))
        sys.exit(0)
    if a.teste_link and not a.perfil: sys.exit("--teste-link precisa de --perfil")
    alvo = [p for p in CFG["perfis"] if p.get("status") == "ativo" and (not a.perfil or a.perfil in (p.get("prefixo"), p.get("handle"), p["pasta"]))]
    for p in alvo:
        try: print(json.dumps(processar(p, a.dry_run, a.teste_link), ensure_ascii=False, indent=1))
        except Exception as e: print(json.dumps({"perfil": p["handle"], "erro": str(e)}, ensure_ascii=False))
