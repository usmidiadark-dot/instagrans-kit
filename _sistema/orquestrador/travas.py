"""Trava por edição: evita duas sessões (automação ou conversa) mexendo na mesma edição ao mesmo tempo.
Uso (na raiz do projeto):
  python _sistema/orquestrador/travas.py ver [ID]               lista as travas vivas, com quem, desde quando e há quanto tempo parada
  python _sistema/orquestrador/travas.py pegar ID [--nota X]    conversa avisa que está nessa edição (o dono é a própria conversa, pelo CLAUDE_CODE_SESSION_ID)
  python _sistema/orquestrador/travas.py soltar ID [--resumo "o que ficou decidido/feito"] [--forcar]
                                                                libera; com --resumo grava out/<ID>/ULTIMA-SESSAO.md (o próximo `pegar` mostra); --forcar solta a trava de outra conversa
  python _sistema/orquestrador/travas.py batida | fim           chamados pelos hooks Stop / SessionEnd (.claude/settings.json): leem o JSON do hook no stdin,
                                                                gravam um resumo automático (último pedido + última resposta) e, no `fim`, soltam a trava
Código de saída de `pegar`: 0 = pegou; 3 = outra sessão já está nela (não mexer; avisar o usuário).
Travas ficam em logs/travas/<ID>.json. Vale enquanto o processo dono (automação: o claude -p; conversa: o CLAUDE_PID dela) estiver vivo;
sem processo conhecido, cai para 3 h desde a última batida. Conversa fechada ou caída = trava some sozinha."""
import argparse, ctypes, datetime as dt, json, os, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
PASTA = ROOT / "logs" / "travas"
VALE_SEM_PID_S = 3 * 3600
MANUAL = "(resumo escrito pela conversa)"

def _vivo(pid):
    """processo existe? (Windows: OpenProcess + código de saída 259 = ainda rodando)"""
    if not pid: return False
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h: return False
        cod = ctypes.c_ulong(); ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(cod)); ctypes.windll.kernel32.CloseHandle(h)
        return cod.value == 259
    except Exception:
        return False

def eu():
    """identidade desta conversa: (sessao, pid) vindos do ambiente do Claude Code"""
    return os.environ.get("CLAUDE_CODE_SESSION_ID", ""), int(os.environ.get("CLAUDE_PID") or 0) or None

def ler(id_):
    f = PASTA / f"{id_}.json"
    if not f.exists(): return None
    try: t = json.loads(f.read_text(encoding="utf-8"))
    except ValueError: return None
    t["parada_min"] = int((time.time() - f.stat().st_mtime) / 60)
    viva = _vivo(t["pid"]) if t.get("pid") else time.time() - f.stat().st_mtime < VALE_SEM_PID_S
    if not viva:  # dono não existe mais: trava velha some sozinha
        f.unlink(missing_ok=True); return None
    return t

def _dono(t): return t.get("sessao") or t.get("dono") or ""

def pegar(id_, quem, dono="", pid=None, nota="", sessao=""):
    """True se pegou (ou renovou a sua); False se outra sessão está nela."""
    atual = ler(id_)
    if atual and (atual.get("quem") != quem or _dono(atual) != (sessao or dono)): return False
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{id_}.json").write_text(json.dumps({"quem": quem, "dono": dono, "sessao": sessao, "pid": pid, "nota": nota,
        "inicio": atual["inicio"] if atual else dt.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
    return True

def pasta_edicao(id_):
    achadas = [d for d in ROOT.glob(f"*/out/{id_}") if d.is_dir()]
    return achadas[0] if achadas else None

def ultima_sessao(id_):
    d = pasta_edicao(id_); f = d / "ULTIMA-SESSAO.md" if d else None
    return f.read_text(encoding="utf-8").strip() if f and f.exists() else ""

def gravar_resumo(id_, corpo, quem, manual=False):
    d = pasta_edicao(id_)
    if not d: return False
    f = d / "ULTIMA-SESSAO.md"
    if not manual and f.exists() and MANUAL in f.read_text(encoding="utf-8").split("\n", 1)[0]:  # não sobrescreve o que a conversa escreveu de propósito
        return False
    cab = f"# Última sessão ({dt.datetime.now():%d/%m/%Y %H:%M}, {quem or 'conversa'}) " + (MANUAL if manual else "(resumo automático: últimas mensagens)")
    f.write_text(cab + "\n\n" + corpo + "\n", encoding="utf-8")
    return True

def soltar(id_, resumo="", dono="", forcar=False):
    t = ler(id_)
    if t and not forcar and t.get("quem") == "chat" and _dono(t) not in ("", dono, eu()[0]):
        return False
    (PASTA / f"{id_}.json").unlink(missing_ok=True)
    if resumo: gravar_resumo(id_, resumo, dono or eu()[0][:8], manual=True)
    return True

def _textos(transcript):
    """(último pedido do usuário, última resposta do assistente) do arquivo de transcrição"""
    u = a = ""
    try:
        for line in open(transcript, encoding="utf-8", errors="ignore"):
            try: d = json.loads(line)
            except ValueError: continue
            m = d.get("message") or {}; c = m.get("content")
            txt = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text") if isinstance(c, list) else ""
            txt = txt.strip()
            if not txt: continue
            if d.get("type") == "user" and not txt.startswith("<"): u = txt
            elif d.get("type") == "assistant": a = txt
    except OSError: pass
    return u[:500], a[:900]

def _hook(fim):
    try: ev = json.loads(sys.stdin.buffer.read().decode("utf-8"))   # utf-8 explícito: o caminho pode ter acento e o stdin do Windows é cp1252
    except Exception: return
    sid = ev.get("session_id", "")
    if not sid or not PASTA.exists(): return
    u, a = _textos(ev.get("transcript_path", ""))
    for f in PASTA.glob("*.json"):
        try: t = json.loads(f.read_text(encoding="utf-8"))
        except ValueError: continue
        if t.get("quem") != "chat" or t.get("sessao") != sid: continue
        gravar_resumo(f.stem, f"**Último pedido do usuário:** {u}\n\n**Última resposta:** {a}", sid[:8])
        if fim: f.unlink(missing_ok=True)
        else: os.utime(f, None)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["ver", "pegar", "soltar", "batida", "fim"]); ap.add_argument("id", nargs="?")
    ap.add_argument("--nota", default=""); ap.add_argument("--dono", default=""); ap.add_argument("--resumo", default=""); ap.add_argument("--forcar", action="store_true")
    r = ap.parse_args()
    if r.cmd in ("batida", "fim"): _hook(r.cmd == "fim"); sys.exit(0)
    if r.cmd == "ver":
        ids = [r.id] if r.id else sorted(f.stem for f in PASTA.glob("*.json")) if PASTA.exists() else []
        vivas = [(i, ler(i)) for i in ids]; vivas = [(i, t) for i, t in vivas if t]
        for i, t in vivas: print(f'{i}: {t["quem"]} ({_dono(t)[:8]}) desde {t["inicio"]}, sem sinal há {t["parada_min"]} min {t.get("nota", "")}')
        if not vivas: print("nenhuma trava viva")
    elif r.cmd == "pegar":
        if not r.id: sys.exit("falta o ID da edição")
        sessao, pid = eu(); dono = r.dono or sessao[:8]
        if not (sessao or r.dono): sys.exit("sem CLAUDE_CODE_SESSION_ID: passe --dono <nome-curto-da-conversa>")
        ok = pegar(r.id, "chat", dono=dono, pid=pid, nota=r.nota, sessao=sessao)
        t = ler(r.id)
        print("pegou" if ok else f'OCUPADA: {t["quem"]} ({_dono(t)[:8]}) desde {t["inicio"]}, sem sinal há {t["parada_min"]} min {t.get("nota", "")}')
        if ok and (u := ultima_sessao(r.id)): print("\n--- o que a sessão anterior deixou ---\n" + u)
        sys.exit(0 if ok else 3)
    else:
        if not r.id: sys.exit("falta o ID da edição")
        if not soltar(r.id, r.resumo, r.dono, r.forcar): sys.exit("a trava é de outra conversa; use --forcar se tiver certeza")
        print("solta" + (" (resumo gravado)" if r.resumo and pasta_edicao(r.id) else ""))
