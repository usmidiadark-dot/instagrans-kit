"""Orquestrador do estúdio.
Uso (na raiz do projeto):  python _sistema/orquestrador/orquestrador.py status | produzir [--perfil X] [--id ID] [--dry-run] | publicar [--perfil X] | voz | voz-ok
produzir: escolhe a pauta (etapa 01, mecânica) e abre uma sessão do Claude Code (claude -p) que faz as etapas 01–07
          seguindo _sistema/orquestrador/produzir.md + <perfil>/producao.md. Os conectores MCP liberados para a sessão vêm de
          perfis.yaml → padrao.ferramentas_mcp (padrão: só o do ElevenLabs)."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, csv, datetime as dt, json, os, pathlib, re, shutil, subprocess, sys, time, yaml
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import travas  # trava por edição
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")  # console do Windows (cp1252)
CFG = carrega(ROOT)
ETAPAS = ["01_pauta", "02_roteiro", "03_voz", "04_cena", "05_render", "06_qa", "07_fila"]
LIMITE_SESSAO_S = 3 * 3600  # uma edição não pode passar de 3 h
# o que a sessão de produção pode usar sem pedir (roda sem ninguém para aprovar). Postar não está aqui: post.py roda fora da sessão.
FERRAMENTAS_BASE = ["Read", "Write", "Edit", "Glob", "Grep", "Agent", "WebSearch", "WebFetch", "TodoWrite", "ToolSearch",
                    "Bash(curl:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)", "Bash(npx remotion:*)", "Bash(cd:*)",
                    "Bash(python:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
                    "Bash(grep:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)"]
MCP_PADRAO = ["mcp__claude_ai_ElevenLabs"]   # voz; outros conectores só se a pessoa listar em perfis.yaml → padrao.ferramentas_mcp


def ferramentas(p=None):
    """Ferramentas liberadas para a sessão: a base + os MCP de padrao.ferramentas_mcp (+ perfil.yaml → ferramentas_mcp_extra do perfil)."""
    mcp = CFG["padrao"].get("ferramentas_mcp")
    mcp = list(MCP_PADRAO if mcp is None else mcp) + list((p or {}).get("ferramentas_mcp_extra") or [])
    return FERRAMENTAS_BASE + [m for m in dict.fromkeys(mcp) if m]

def perfis_ativos():
    return [p for p in CFG["perfis"] if p.get("status") == "ativo"]

def pausa_ativa(p):
    """perfil.yaml → pausa_programada {ate, motivo, por}: sem criar vídeo até 'ate' (hora local do PC); depois volta sozinho."""
    pp = p.get("pausa_programada") or {}
    try: return pp if pp.get("ate") and dt.datetime.now() < dt.datetime.fromisoformat(str(pp["ate"])) else None
    except ValueError: return None

def fila(p, pasta="04-aprovado"):
    d = ROOT / p["pasta"] / "posts" / pasta
    return sorted(f for f in d.glob("*.json") if not f.name.startswith("._")) if d.exists() else []

def status():
    for p in perfis_ativos():
        falhas = ROOT / p["pasta"] / "reviews" / "falhas"
        n = len([f for f in falhas.glob("*") if not f.name.startswith("._")]) if falhas.exists() else 0
        print(f'{p.get("handle", p["pasta"]):20} fila={len(fila(p))}  em_producao={len(fila(p, "02-em-producao"))}  publicados={len(fila(p, "05-publicado"))}  falhas={n}')

# ---------- etapa 01 (parte mecânica): próxima pauta não usada nos últimos 90 dias ----------
def estados_formato(p):
    """Estado de cada formato na tabela do <perfil>/formatos.md (automacao.md §9)."""
    arq = ROOT / p["pasta"] / "formatos.md"
    if not arq.exists(): return {}
    est = {}
    for linha in arq.read_text(encoding="utf-8").splitlines():
        cols = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(cols) >= 2 and cols[1] in ("base", "em teste", "ativo", "cortado"): est[cols[0]] = cols[1]
    return est

def _num(nome, prefixo):
    m = re.fullmatch(rf"{re.escape(prefixo)}-(\d+)", nome)
    return int(m.group(1)) if m else None

def decide_cta(p, edicao, forcado=None, pauta=None):
    """Teste A/B de CTA (<perfil>/format.json → ab_cta = {"desde": 8, "comeca": true}): a edição sai COM ou SEM a chamada
    para comentar. Ordem: flag da linha de comando (--com-cta/--sem-cta) > coluna 'cta' da pautas.csv (sim/nao) > alternância (a oposta da
    última edição do teste, lida de script.json → ab_cta ou brief.json → cta; sem histórico = 'comeca'). Perfil sem ab_cta: sempre com CTA."""
    if p.get("sem_cta_sempre"): return False   # perfil.yaml → sem_cta_sempre: nenhum vídeo novo pede comentário
    if forcado is not None: return forcado
    v = ((pauta or {}).get("cta") or "").strip().lower()
    if v in ("sim", "com", "true", "1", "s"): return True
    if v in ("nao", "não", "sem", "false", "0", "n"): return False
    try: ab = json.loads((ROOT / p["pasta"] / "format.json").read_text(encoding="utf-8")).get("ab_cta")
    except Exception: ab = None
    if not ab: return True
    meu = _num(edicao, p["prefixo"]) or 10 ** 6
    hist = []
    for d in (ROOT / p["pasta"] / "out").glob(f'{p["prefixo"]}-*'):
        n = _num(d.name, p["prefixo"])
        if n is None or n < ab.get("desde", 0) or n >= meu: continue
        marca = None
        for arq, chave in (("script.json", "ab_cta"), ("brief.json", "cta")):
            try: x = json.loads((d / arq).read_text(encoding="utf-8")).get(chave)
            except Exception: x = None
            if isinstance(x, bool): marca = x; break
        if marca is not None: hist.append((n, marca))
    return (not max(hist)[1]) if hist else bool(ab.get("comeca", True))

class SemPauta(Exception): pass

def escolher_pauta(p, edicao=None, cta=None):
    if edicao and (ROOT / p["pasta"] / "out" / edicao / "brief.json").exists():  # retomar uma edição já iniciada
        pasta = ROOT / p["pasta"] / "out" / edicao
        recente = max((f.stat().st_mtime for f in pasta.rglob("*") if f.is_file()), default=0)
        if time.time() - recente < 15 * 60 and not (pasta / "ATUALIZAR.md").exists():  # arquivo mexido há < 15 min: a sessão anterior ainda trabalha (ATUALIZAR.md na pasta libera a retomada)
            sys.exit(f"{edicao}: arquivos mudaram há {int((time.time() - recente) / 60)} min; outra sessão ainda está nela. Não retomo.")
        brief = json.loads((pasta / "brief.json").read_text(encoding="utf-8"))
        if cta is not None and brief.get("cta") is not cta:  # retomada com --com-cta/--sem-cta: a flag manda
            brief["cta"] = cta; (pasta / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")
        return pasta, brief
    arq = ROOT / p["pasta"] / "pautas.csv"
    linhas = list(csv.DictReader(arq.read_text(encoding="utf-8").splitlines()))
    estados = estados_formato(p)
    livres = [l for l in linhas if not (l.get("usado_em") or "").strip() and estados.get(l["formato"], "base") != "cortado"]
    ordem = {"ativo": 0, "base": 1, "em teste": 2}  # §9: ativo primeiro, nunca cortado
    livre = min(livres, key=lambda l: ordem.get(estados.get(l["formato"], "base"), 1)) if livres else None
    prio = [l for l in livres if (l.get("prioridade") or "").strip()]   # pauta com a coluna prioridade preenchida (assunto do momento) passa na frente da rotação de formato
    prio.sort(key=lambda l: (l.get("prioridade") or "").strip() == "sorteio")   # prioridade 'sorteio' fica atrás das outras prioridades
    if prio: livre = prio[0]
    elif livres and (p.get("qualidade") or {}).get("montagem_varia"):
        # rotação de formato, só em perfil com qualidade.montagem_varia (série que conta uma história segue a ordem do banco):
        # nunca o formato da edição anterior se houver outro livre; entre os livres, o que menos saiu nas últimas 6 edições
        ult_f = [l["formato"] for l in sorted((l for l in linhas if (l.get("usado_em") or "").strip()), key=lambda l: l["usado_em"])][-6:]
        cand = [l for l in livres if not ult_f or l["formato"] != ult_f[-1]] or livres
        livre = min(cand, key=lambda l: (ult_f.count(l["formato"]), ordem.get(estados.get(l["formato"], "base"), 1)))
    if not livre: raise SemPauta(f'{p["handle"]}: banco de pautas vazio')   # não é erro da rodada: o rodízio segue para o próximo perfil
    out = ROOT / p["pasta"] / "out"
    nums = [int(m.group(1)) for d in out.glob(f'{p["prefixo"]}-*') if (m := re.match(rf'{p["prefixo"]}-(\d+)$', d.name))]
    edicao = edicao or f'{p["prefixo"]}-{(max(nums) + 1 if nums else 1):03d}'
    pasta = out / edicao; pasta.mkdir(parents=True, exist_ok=True)
    brief = {"profile": p["handle"], "id": edicao, "topic": livre["tema"], "angle": livre["angulo"], "format": livre["formato"],
             "sources": [s for s in (livre.get("fontes") or "").split(";") if s.strip()], "data": dt.date.today().isoformat()}
    tem_ab = cta is not None or (livre.get("cta") or "").strip() or "ab_cta" in (json.loads((ROOT / p["pasta"] / "format.json").read_text(encoding="utf-8")) if (ROOT / p["pasta"] / "format.json").exists() else {})
    fmt_ = json.loads((ROOT / p["pasta"] / "format.json").read_text(encoding="utf-8")) if (ROOT / p["pasta"] / "format.json").exists() else {}
    if fmt_.get("final") == "seguir": brief["cta"] = False; brief["final"] = "seguir"; tem_ab = False   # format.json → final: seguir: sem chamada para comentar; o final é o card de SEGUIR (script.seguir)
    if tem_ab: brief["cta"] = decide_cta(p, edicao, cta, livre)   # teste A/B de CTA: false = sem palavra, sem chamada, sem card
    if (livre.get("palavra") or "").strip() and brief.get("cta") is not False: brief["palavra"], brief["promessa"] = livre["palavra"].strip().upper(), (livre.get("promessa") or "").strip()  # palavra de comentário por vídeo (pautas.csv → palavra, promessa)
    if (livre.get("gancho") or "").strip(): brief["gancho"] = {"fala": livre["gancho"].strip(), "tela": (livre.get("gancho_tela") or "").strip(), "visual": (livre.get("gancho_visual") or "").strip()}  # gancho pronto da pauta (pautas.csv → gancho, gancho_tela, gancho_visual)
    if (livre.get("periodo") or "").strip(): brief["periodo"] = livre["periodo"].strip()  # pautas.csv → periodo (ex.: manha/tarde/noite): horário do post em perfil.yaml → periodos
    (pasta / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")
    livre["usado_em"] = edicao
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)
    em = ROOT / p["pasta"] / "posts" / "02-em-producao"; em.mkdir(parents=True, exist_ok=True)
    (em / f"{edicao}.json").write_text(json.dumps({"id": edicao, "tema": livre["tema"], "inicio": dt.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
    return pasta, brief

LIMITE_ARQ = ROOT / "logs" / "limite-sessao.json"

def limite_ativo():
    """Limite de uso do Claude: a sessão automática morre com "You've hit your session limit · resets 2:10pm". Sem isto cada checagem de 30 min
    queimava uma pauta e abria uma sessão que morria no mesmo instante. Devolve a hora em que o limite volta, se ainda não voltou."""
    try: ate = dt.datetime.fromisoformat(json.loads(LIMITE_ARQ.read_text(encoding="utf-8"))["ate"])
    except Exception: return None
    return ate if dt.datetime.now() < ate else None

def le_limite_no_log(log):
    """Se o log da sessão terminou no limite de uso, devolve a hora de volta (datetime local); senão None."""
    import re
    try: txt = log.read_text(encoding="utf-8", errors="replace")
    except Exception: return None
    m = re.search(r"hit your (?:session |\d+-hour |weekly |week )?limit.{0,40}?resets (\d{1,2})(?::(\d{2}))?\s*([ap]m)", txt, re.I)
    if not m: return None
    h, mi, ap = int(m.group(1)) % 12, int(m.group(2) or 0), m.group(3).lower()
    ate = dt.datetime.now().replace(hour=h + (12 if ap == "pm" else 0), minute=mi, second=0, microsecond=0)
    return ate if ate > dt.datetime.now() else ate + dt.timedelta(days=1)

VOZ_ARQ = ROOT / "logs" / "voz-sem-credito.json"
VOZ_MIN = 2000  # caracteres que precisam sobrar no ElevenLabs para abrir uma edição (narração de ~60 s = ~1000); padrao.voz_min_creditos muda

def _chave_eleven():
    """Chave do ElevenLabs só para LER o saldo (env ou .env). Vazia = sem como ler. Use uma chave restrita: só 'user_read', sem permissão de gerar voz."""
    if (k := os.environ.get("ELEVENLABS_API_KEY", "").strip()): return k
    try:
        for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if l.strip().startswith("ELEVENLABS_API_KEY="): return l.split("=", 1)[1].split("#")[0].strip().strip("\"'")
    except Exception: pass
    return ""

def voz_saldo():
    """Caracteres que restam no ElevenLabs, ou None se não deu para ler. SÓ LEITURA (GET /v1/user/subscription): não gera voz e não gasta crédito."""
    k = _chave_eleven()
    if not k: return None
    try:
        import urllib.request
        r = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": k})
        d = json.loads(urllib.request.urlopen(r, timeout=15).read().decode("utf-8"))
        return int(d["character_limit"]) - int(d["character_count"])
    except Exception: return None

def voz_bloqueada():
    """Motivo (texto) se a voz está sem crédito, senão None. Com chave de leitura: confere o saldo de verdade. Sem chave: vale a trava deixada
    por uma sessão que morreu por falta de crédito (logs/voz-sem-credito.json) até alguém rodar 'orquestrador.py voz-ok'. Não consegue ler = não bloqueia."""
    minimo = CFG["padrao"].get("voz_min_creditos", VOZ_MIN)
    if (saldo := voz_saldo()) is not None:
        if saldo < minimo: return f"ElevenLabs com {saldo} caracteres (precisa de {minimo})"
        VOZ_ARQ.unlink(missing_ok=True); return None
    try: return f'ElevenLabs sem crédito desde {json.loads(VOZ_ARQ.read_text(encoding="utf-8"))["quando"]} (liberar: orquestrador.py voz-ok)'
    except Exception: return None

def le_falta_voz_no_log(log):
    """True se o log terminou por falta de crédito/cota da voz (e não por defeito da edição)."""
    try: txt = log.read_text(encoding="utf-8", errors="replace")
    except Exception: return False
    return bool(re.search(r"quota_exceeded|insufficient[_ ](?:credits|characters)|out of (?:credits|characters)|not enough (?:credits|characters)|creator tier or above|ligue o conector do ElevenLabs|sem cr[eé]dito", txt, re.I))

class _Chaves(dict):
    """Chave desconhecida entre chaves no texto de produção (ex.: "{gancho_falado, amigo, loop}") fica como está, em vez de dar KeyError antes de abrir a sessão."""
    def __missing__(self, k): return "{" + k + "}"

def produzir(p, edicao=None, cta=None):
    if CFG["padrao"].get("pausado") or p.get("pausado"): print(f'{p["handle"]}: pausado'); return
    if not edicao and (lim := limite_ativo()): print(f'{p["handle"]}: limite de uso do Claude até {lim:%H:%M}, não abro sessão'); return
    if not edicao and (vz := voz_bloqueada()): print(f'{p["handle"]}: {vz}; não abro sessão'); return
    reserva(p)
    if not edicao and (pp := pausa_ativa(p)): print(f'{p["handle"]}: pausa programada até {pp["ate"]} ({pp.get("motivo", "")})'); return
    if not edicao and p.get("producao_ate"):  # perfil.yaml → producao_ate: produzir só até a fila cobrir este dia (fuso do padrao) e parar
        ultimo = max((json.loads(f.read_text(encoding="utf-8"))["horario"] for f in fila(p)), default="")
        if ultimo >= f'{p["producao_ate"]} {max(p["horarios"])}': print(f'{p["handle"]}: fila já cobre {p["producao_ate"]} (producao_ate), não produzo'); return
    alvo = p.get("fila_alvo", CFG["padrao"].get("fila_alvo", 3))  # por perfil, senão o padrão
    if not edicao and len(fila(p)) >= alvo: print(f'{p["handle"]}: fila cheia ({len(fila(p))}/{alvo}), nada a produzir'); return
    if edicao and (t := travas.ler(edicao)):  # trava por edição (travas.py): outra sessão já está nela
        print(f'{p["handle"]}: {edicao} está com {t["quem"]} ({t.get("dono", "")}) desde {t["inicio"]}, não abro outra sessão'); return
    for f in fila(p, "02-em-producao"):  # uma edição por perfil de cada vez: não abre outra enquanto a anterior trabalha (trava viva, ou log mexido há < 15 min)
        logs_ed = sorted((ROOT / "logs").glob(f"{f.stem}_*.log"), key=lambda x: x.stat().st_mtime)
        if not edicao and ((t := travas.ler(f.stem)) or (logs_ed and time.time() - logs_ed[-1].stat().st_mtime < 15 * 60)):
            print(f'{p["handle"]}: {f.stem} ainda em produção{" (" + t["quem"] + ")" if t else ""}, não abro outra'); return
    if (p.get("qualidade") or {}).get("montagem_varia"):  # a auditoria de repetição olha as últimas edições antes de cada produção
        subprocess.run([sys.executable, str(ROOT / "_sistema" / "orquestrador" / "auditoria.py"), p["pasta"]], capture_output=True, cwd=ROOT)
    pasta, brief = escolher_pauta(p, edicao, cta)
    chaves = dict(id=brief["id"], handle=p["handle"], pasta=pasta.relative_to(ROOT).as_posix(), perfil=p["pasta"], idioma=("português do Brasil" if str(p.get("idioma_conteudo", "")).lower().startswith("pt") else "inglês"),
                  cta_modo=("FINAL DE SEGUIR (brief.json → final: seguir; sem palavra nem chamada)" if brief.get("final") == "seguir" else "SEM CTA (brief.json → cta: false)") if brief.get("cta") is False else "COM CTA")   # producao.md do perfil pode citar {cta_modo}
    if "cta" in brief: print(f'{brief["id"]}: teste A/B de CTA → {chaves["cta_modo"]}')
    etapas = ROOT / p["pasta"] / "producao.md"  # etapas próprias do perfil (cena em código, sem voz...)
    if not etapas.exists(): sys.exit(f'{p["handle"]}: falta {etapas.relative_to(ROOT)} (etapas de produção do perfil)')
    prompt = (ROOT / "_sistema" / "orquestrador" / "produzir.md").read_text(encoding="utf-8").format_map(
        _Chaves(instrucoes_perfil=etapas.read_text(encoding="utf-8").format_map(_Chaves(chaves)), **chaves))
    logs = ROOT / "logs"; logs.mkdir(exist_ok=True)
    log = logs / f'{brief["id"]}_{dt.datetime.now():%Y%m%d_%H%M}.log'
    print(f'{brief["id"]}: "{brief["topic"]}" → sessão do Claude Code (log: {log.relative_to(ROOT)})')
    ini = time.time(); sessao = None
    em = ROOT / p["pasta"] / "posts" / "02-em-producao" / f'{brief["id"]}.json'
    with log.open("w", encoding="utf-8") as f:
        # claude.exe direto (sem cmd.exe, que corta o comando na 1ª quebra de linha) e prompt pela entrada padrão.
        # stream-json: cada passo da sessão vira uma linha legível no log, ao vivo (acompanhar: abrir o .log).
        proc = subprocess.Popen([shutil.which("claude") or "claude", "-p", "--model", "sonnet", "--allowedTools", ",".join(ferramentas(p)), "--output-format", "stream-json", "--verbose"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", cwd=ROOT, env={**os.environ, "INSTAGRANS_AUTO": "1"})
        travas.pegar(brief["id"], "auto", dono="auto", pid=proc.pid, nota=f'log {log.name}')  # trava viva enquanto este processo existir
        proc.stdin.write(prompt); proc.stdin.close()
        for linha in proc.stdout:
            try: ev = json.loads(linha)
            except ValueError: f.write(linha); f.flush(); continue
            if not isinstance(ev, dict): f.write(linha); f.flush(); continue
            if ev.get("session_id") and not sessao:
                sessao = ev["session_id"]
                f.write(f"# sessão {sessao} · para abrir a conversa inteira depois: claude --resume {sessao}\n")
                if em.exists(): em.write_text(json.dumps({**json.loads(em.read_text(encoding="utf-8")), "sessao": sessao}, ensure_ascii=False), encoding="utf-8")
            hora = dt.datetime.now().strftime("%H:%M")
            msg = ev.get("message") if isinstance(ev, dict) else None
            conteudo = msg.get("content") if isinstance(msg, dict) else None
            for b in conteudo if isinstance(conteudo, list) else []:  # alguns eventos trazem texto puro: ignora
                if not isinstance(b, dict): continue
                if ev.get("type") == "assistant" and b.get("type") == "text" and b["text"].strip(): f.write(f"[{hora}] {b['text'].strip()}\n")
                elif b.get("type") == "tool_use":
                    alvo_ = b["input"].get("command") or b["input"].get("file_path") or b["input"].get("description") or b["input"].get("query") or ""
                    f.write(f"[{hora}]   → {b['name']}: {str(alvo_)[:160]}\n")
            if ev.get("type") == "result": f.write(f"\n=== FIM ({ev.get('subtype')}) ===\n{ev.get('result', '')}\n")
            f.flush()
        try: proc.wait(timeout=LIMITE_SESSAO_S)
        except subprocess.TimeoutExpired: proc.kill()
    travas.soltar(brief["id"])
    na_fila = any(json.loads(i.read_text(encoding="utf-8"))["id"] == brief["id"] for i in fila(p))
    resumo = {"id": brief["id"], "codigo_saida": proc.returncode, "minutos": round((time.time() - ini) / 60, 1), "na_fila": na_fila,
              "fail": (pasta / "fail.json").exists(), "sessao": sessao}
    print(json.dumps(resumo, ensure_ascii=False))
    if not na_fila and (volta := le_limite_no_log(log)):  # morreu no limite de uso, não por defeito da edição: não conta como falha
        LIMITE_ARQ.write_text(json.dumps({"ate": volta.isoformat(timespec="minutes"), "edicao": brief["id"]}), encoding="utf-8")
        print(f'{brief["id"]}: limite de uso do Claude; volta às {volta:%H:%M}. Nenhuma sessão nova até lá.')
        if len(list(pasta.iterdir())) <= 1:  # nada foi produzido (só o brief): devolve a pauta e apaga a pasta vazia
            arq_ = ROOT / p["pasta"] / "pautas.csv"; ls_ = list(csv.DictReader(arq_.open(encoding="utf-8", newline="")))
            for l_ in ls_:
                if l_.get("usado_em") == brief["id"]: l_["usado_em"] = ""
            with arq_.open("w", encoding="utf-8", newline="") as f_: w_ = csv.DictWriter(f_, fieldnames=list(ls_[0].keys())); w_.writeheader(); w_.writerows(ls_)
            shutil.rmtree(pasta, ignore_errors=True); em.unlink(missing_ok=True)
        else: em.unlink(missing_ok=True); print(f'{brief["id"]}: tinha trabalho feito; retomar com: orquestrador.py produzir --perfil <perfil> --id {brief["id"]}')
        return resumo
    if not na_fila and le_falta_voz_no_log(log):  # voz sem crédito: trava as próximas aberturas (a edição ainda cai em falhas abaixo)
        VOZ_ARQ.write_text(json.dumps({"quando": dt.datetime.now().isoformat(timespec="minutes"), "edicao": brief["id"]}), encoding="utf-8")
        print(f'{brief["id"]}: voz sem crédito; nenhuma sessão nova até recarregar e rodar orquestrador.py voz-ok.')
    if not na_fila:  # alerta: vai para reviews/falhas (o e-mail/webhook entra no teste do agendador)
        falhas = ROOT / p["pasta"] / "reviews" / "falhas"; falhas.mkdir(parents=True, exist_ok=True)
        (falhas / f'{brief["id"]}.json').write_text(json.dumps({**resumo, "log": str(log.relative_to(ROOT))}, ensure_ascii=False, indent=1), encoding="utf-8")
        em.unlink(missing_ok=True)  # sai de 02-em-producao; o motivo fica em reviews/falhas e no fail.json
    else:  # edição refeita que passou: tira o registro da falha antiga
        (ROOT / p["pasta"] / "reviews" / "falhas" / f'{brief["id"]}.json').unlink(missing_ok=True)
    return resumo

RODIZIO_ARQ = ROOT / "logs" / "rodizio_produzir.json"

def ler_rodizio():
    try: return json.loads(RODIZIO_ARQ.read_text(encoding="utf-8")).get("ultimo")
    except Exception: return None

def grava_rodizio(p):
    try: RODIZIO_ARQ.parent.mkdir(exist_ok=True); RODIZIO_ARQ.write_text(json.dumps({"ultimo": p["pasta"], "em": dt.datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    except Exception as e: print(f"rodízio: não gravei o último atendido ({e})")

def rodizio_ordem(perfis):
    """Perfis na ordem do perfis.yaml, girados para começar logo depois do último atendido."""
    ult = ler_rodizio(); pastas = [p["pasta"] for p in perfis]
    if ult not in pastas: return list(perfis)
    k = pastas.index(ult) + 1
    return list(perfis[k:]) + list(perfis[:k])

def motivo_pular(p):
    """Só leitura (para o --dry-run): por que produzir() não produziria neste perfil agora; None = produziria. Espelha as guardas de produzir()."""
    if CFG["padrao"].get("pausado") or p.get("pausado"): return "pausado"
    if lim := limite_ativo(): return f"limite de uso do Claude até {lim:%H:%M}"
    if vz := voz_bloqueada(): return vz
    if pp := pausa_ativa(p): return f'pausa programada até {pp["ate"]}'
    if p.get("producao_ate"):
        ultimo = max((json.loads(f.read_text(encoding="utf-8"))["horario"] for f in fila(p)), default="")
        if ultimo >= f'{p["producao_ate"]} {max(p["horarios"])}': return f'fila já cobre {p["producao_ate"]} (producao_ate)'
    alvo = p.get("fila_alvo", CFG["padrao"].get("fila_alvo", 3))
    if len(fila(p)) >= alvo: return f"fila cheia {len(fila(p))}/{alvo}"
    for f in fila(p, "02-em-producao"):
        logs_ed = sorted((ROOT / "logs").glob(f"{f.stem}_*.log"), key=lambda x: x.stat().st_mtime)
        if (t := travas.ler(f.stem)) or (logs_ed and time.time() - logs_ed[-1].stat().st_mtime < 15 * 60): return f"{f.stem} ainda em produção"
    return None

def reserva(p):
    """Série por personagem (perfil.yaml → serie): edição da reserva volta para a fila quando o personagem dela é o da vez."""
    if not p.get("serie"): return
    sys.path.insert(0, str(ROOT / "_sistema" / "orquestrador")); import serie
    for i in serie.liberar_reserva(p["pasta"]): print(f'{p["handle"]}: {i} saiu da reserva para a fila (série do personagem)')

def publicar(p):
    reserva(p)
    subprocess.run([sys.executable, str(ROOT / "_sistema" / "orquestrador" / "post.py"), "proximo", "--perfil", p["prefixo"]], cwd=ROOT)
    if p.get("crosspost"):  # YouTube Shorts / TikTok (perfil.yaml → crosspost): só o que já saiu no Instagram; falha aqui nunca afeta o Instagram
        subprocess.run([sys.executable, str(ROOT / "_sistema" / "orquestrador" / "crosspost.py"), "proximo", "--perfil", p["prefixo"]], cwd=ROOT)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["status", "produzir", "publicar", "voz", "voz-ok"]); ap.add_argument("--perfil"); ap.add_argument("--id"); ap.add_argument("--dry-run", dest="dry", action="store_true")   # --dry-run: só mostra o rodízio de produzir, não produz nada
    g_ = ap.add_mutually_exclusive_group()   # teste A/B de CTA: força a edição com ou sem a chamada; sem flag = pautas.csv → cta ou alternância (format.json → ab_cta)
    g_.add_argument("--sem-cta", dest="cta", action="store_false", default=None); g_.add_argument("--com-cta", dest="cta", action="store_true", default=None)
    a = ap.parse_args()
    alvo = [p for p in perfis_ativos() if not a.perfil or a.perfil in (p.get("prefixo"), p.get("handle"), p["pasta"])]
    if a.perfil and not alvo:
        print("perfis ativos:", ", ".join(f'{p["pasta"]} ({p.get("prefixo")})' for p in perfis_ativos()) or "nenhum"); sys.exit(f"perfil não encontrado ou não ativo: {a.perfil}")
    if a.cmd == "produzir" and not a.perfil: alvo = [p for p in alvo if p.get("producao_auto")]  # agendador: só os perfis prontos (perfil.yaml → producao_auto)
    if a.cmd == "voz": print("saldo:", voz_saldo(), "| bloqueio:", voz_bloqueada() or "nenhum"); sys.exit(0)
    if a.cmd == "voz-ok": VOZ_ARQ.unlink(missing_ok=True); print("trava de voz liberada"); sys.exit(0)
    if a.cmd == "status":
        if not CFG["perfis"]: print("nenhum perfil configurado (perfis.yaml → ordem: []). Crie um a partir de _modelo-perfil/.")
        status()
    elif a.cmd == "produzir" and not a.perfil and not a.id:
        # RODÍZIO: cada rodada produz NO MÁXIMO 1 edição por perfil abaixo da fila_alvo, na ordem de perfis.yaml, começando no perfil seguinte
        # ao último atendido (guardado em logs/rodizio_produzir.json), para um perfil não segurar os outros.
        for p in rodizio_ordem(alvo):
            if a.dry:
                m = motivo_pular(p); print(f'[dry-run] {p["handle"]}: ' + (f"pula ({m})" if m else "produziria 1 edição")); continue
            try: r = produzir(p, None, a.cta)
            except SemPauta as e: print(e, '(sem pauta livre: a vez passa)'); r = {}
            if r is not None: grava_rodizio(p)   # atendido (deu certo ou falhou): a vez passa para o próximo
        if a.dry: print(f"[dry-run] último atendido guardado: {ler_rodizio()!r}; nada foi produzido nem gravado")
    else:
        for p in alvo:
            if a.cmd == "publicar": publicar(p); continue
            try:
                if a.id: produzir(p, a.id, a.cta); continue
            except SemPauta as e: print(e); continue
            # --perfil explícito (manual): até producao_max_por_noite edições, parando na fila cheia ou na primeira falha
            for _ in range(p.get("producao_max_por_noite", CFG["padrao"].get("producao_max_por_noite", 1))):
                try: r = produzir(p, None, a.cta)
                except SemPauta as e: print(e); break
                if not r or not r.get("na_fila"): break
