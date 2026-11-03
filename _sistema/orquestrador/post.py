"""Etapa 08 · post de reel pela Instagram Graph API (login do Facebook, upload resumível do arquivo local).
Uso (na raiz do projeto):
  python _sistema/orquestrador/post.py checar   [--perfil X]               confere tokens, contas e cota (só leitura)
  python _sistema/orquestrador/post.py publicar <item.json> [--dry-run]    posta um item da fila
  python _sistema/orquestrador/post.py proximo  [--perfil X] [--dry-run]   posta o próximo item vencido de cada perfil
Item da fila (<perfil>/posts/04-aprovado/<AAAA-MM-DD_HHMM>.json):
  {"id": "abc-001", "horario": "2026-10-23 17:30", "video": "meu-perfil/out/abc-001/video.mp4",
   "legenda": "...", "capa_offset_ms": 1000}
Credenciais só no .env: IG_USER_ID_<X>, IG_TOKEN_<X> (nomes em perfil.yaml → user_id_env / token_env), META_APP_ID, META_APP_SECRET, META_GRAPH_VERSION.
Vídeo longo que o upload direto recusa: com perfis.yaml → padrao.cloudflare: true, sobe uma cópia num deploy de prévia do Cloudflare Pages
(npx wrangler) e publica por link; desligado (padrão), só o upload direto com as tentativas."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, datetime as dt, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests, yaml
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[2]
try: sys.stdout.reconfigure(encoding="utf-8")  # agendador/console do Windows (cp1252) quebrava em "→"
except Exception: pass
load_dotenv(ROOT / ".env")
CFG = carrega(ROOT)
GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"
VER = os.getenv("META_GRAPH_VERSION") or "v26.0"
TENTATIVAS, ESPERA_S = 3, 600  # automacao.md §3: 3 tentativas, 10 min entre elas
TZ = ZoneInfo(CFG["padrao"].get("fuso", "America/New_York"))

# ---------- perfis e credenciais ----------
def perfis_ativos():
    return [p for p in CFG["perfis"] if p.get("status") == "ativo" and p.get("token_env")]

def acha_perfil(chave):
    for p in perfis_ativos():
        if chave in (p.get("prefixo"), p.get("handle"), p["pasta"]): return p
    sys.exit(f"perfil não encontrado (ou sem token_env): {chave}. Ativos: {', '.join(p['pasta'] for p in perfis_ativos()) or 'nenhum'}")

def credenciais(p):
    uid, tok = os.getenv(p["user_id_env"], "").strip(), os.getenv(p["token_env"], "").strip()
    falta = [n for n, v in ((p["user_id_env"], uid), (p["token_env"], tok)) if not v]
    return uid, tok, falta

def pausado(p):
    return bool(CFG["padrao"].get("pausado") or p.get("pausado") or p.get("paused"))

def api(metodo, caminho, **kw):
    r = requests.request(metodo, f"{GRAPH}/{VER}/{caminho}", timeout=kw.pop("timeout", 60), **kw)
    if not r.ok: raise RuntimeError(f"{metodo} {caminho} → {r.status_code}: {r.text[:400]}")
    return r.json()

# ---------- checagens ----------
def valida_video(video):
    """Regras de reel da Graph API: MP4 H.264 + AAC, 9:16, 3 s a 15 min, 23–60 fps, até 300 MB."""
    if not video.exists(): return [f"vídeo não existe: {video}"]
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                                     capture_output=True, text=True).stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    erros = []
    if not v or v["codec_name"] != "h264": erros.append("vídeo precisa ser H.264")
    if not a or a["codec_name"] != "aac": erros.append("áudio precisa ser AAC")
    if v:
        if abs(v["width"] / v["height"] - 9 / 16) > 0.01: erros.append(f'proporção {v["width"]}×{v["height"]} não é 9:16')
        num, den = map(int, v["r_frame_rate"].split("/")); fps = num / den
        if not 23 <= fps <= 60: erros.append(f"fps {fps:.2f} fora de 23–60")
    dur, tam = float(info["format"]["duration"]), int(info["format"]["size"])
    if not 3 <= dur <= 900: erros.append(f"duração {dur:.1f} s fora de 3 s–15 min")
    if tam > 300 * 2**20: erros.append(f"arquivo com {tam / 2**20:.0f} MB (máx. 300)")
    return erros

def checar(p):
    uid, tok, falta = credenciais(p)
    out = {"perfil": p["handle"], "pausado": pausado(p)}
    if falta: return {**out, "ok": False, "erro": f"faltam no .env: {', '.join(falta)}"}
    try:
        conta = api("GET", uid, params={"fields": "username,followers_count,media_count", "access_token": tok})
        cota = api("GET", f"{uid}/content_publishing_limit", params={"fields": "config,quota_usage", "access_token": tok})
        out.update(conta=conta, cota=cota.get("data", [{}])[0])
        app_id, app_secret = os.getenv("META_APP_ID"), os.getenv("META_APP_SECRET")
        if app_id and app_secret:
            dbg = api("GET", "debug_token", params={"input_token": tok, "access_token": f"{app_id}|{app_secret}"})["data"]
            exp = dbg.get("expires_at") or 0
            dias = (exp - time.time()) / 86400 if exp else None
            out["token"] = {"valido": dbg.get("is_valid"), "escopos": dbg.get("scopes"),
                            "vence_em_dias": round(dias, 1) if dias is not None else "não vence",
                            "alerta": dias is not None and dias < 7}
        if out.get("token"): out["capa_propria"] = "pages_manage_posts" in (out["token"].get("escopos") or [])
        esperado = p["handle"].lstrip("@")
        out["ok"] = conta.get("username") == esperado
        if not out["ok"]: out["erro"] = f'token é da conta @{conta.get("username")}, esperado @{esperado}'
    except Exception as e:
        out.update(ok=False, erro=str(e))
    return out

# ---------- capa ----------
def capa_url(capa, tok):
    """A Graph API só aceita capa própria por link público: sobe a capa como foto NÃO publicada da página ligada
    à conta (precisa de pages_manage_posts) e devolve o link da imagem. Ninguém vê a foto na página."""
    pagina = api("GET", "me", params={"fields": "id", "access_token": tok})["id"]
    with open(capa, "rb") as f:
        r = requests.post(f"{GRAPH}/{VER}/{pagina}/photos", data={"published": "false", "access_token": tok},
                          files={"source": (capa.name, f, "image/jpeg")}, timeout=120)
    if not r.ok: raise RuntimeError(f"capa → {r.status_code}: {r.text[:300]}")
    foto = r.json()["id"]
    imgs = api("GET", foto, params={"fields": "images", "access_token": tok})["images"]
    url = max(imgs, key=lambda i: i["width"] * i["height"])["source"]
    if requests.get(url, timeout=60).status_code != 200: raise RuntimeError("link da capa não abre sem login")
    return url, foto

# ---------- publicação ----------
IG_MAX_MBPS, IG_MAX_MB = 20, 250  # especificação do Instagram para reels: até 25 Mbps e 300 MB (margem de folga)

def cabe_no_ig(video):
    """Render de alta qualidade pode sair acima da especificação do Instagram (bitrate/tamanho). Recodifica uma cópia ao lado se passar do limite.
    (O ProcessingFailedError do upload é outra coisa: intermitente, em todos os perfis e tamanhos; quem resolve são as tentativas.)"""
    try: fmt = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=bit_rate,size", "-of", "json", str(video)],
                                         capture_output=True, text=True, check=True).stdout)["format"]
    except Exception: return video
    if int(fmt.get("bit_rate", 0)) <= IG_MAX_MBPS * 1e6 and int(fmt.get("size", 0)) <= IG_MAX_MB * 1e6: return video
    leve = video.with_name("_video_ig.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-map", "0:v", "-map", "0:a?", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
                    "-maxrate", "16M", "-bufsize", "32M", "-c:a", "copy", "-movflags", "+faststart", str(leve)], check=True)
    print(f"{video.name}: {int(fmt['bit_rate']) / 1e6:.0f} Mbps / {int(fmt['size']) / 1e6:.0f} MB acima do limite do Instagram -> {leve.name}")
    return leve

CONTEINER_MAX_H = 3  # contêiner que ficou processando vale até 3 h; depois a rodada cria outro

class Processando(Exception):
    """O contêiner foi para o processamento assíncrono: a próxima rodada do agendador retoma o mesmo (container.json)."""

def finaliza(cid, uid, tok):
    mid = api("POST", f"{uid}/media_publish", data={"creation_id": cid, "access_token": tok})["id"]
    link = api("GET", mid, params={"fields": "permalink,timestamp", "access_token": tok})
    return {"container_id": cid, "media_id": mid, "permalink": link.get("permalink"), "timestamp": link.get("timestamp")}

LINK_MAX_MB = 24  # Cloudflare Pages: até 25 MiB por arquivo

def log_link(msg):
    """Pelo agendador o print some: o caminho por link deixa o rastro em logs/post-link.log."""
    print(msg); (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "post-link.log").open("a", encoding="utf-8") as f: f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")

def video_por_link(video, p, ident):
    try: return _video_por_link(video, p, ident)
    except Exception as e: log_link(f"{ident}: erro no caminho por link: {e!r}"); return None

def _video_por_link(video, p, ident):
    """Opcional (perfis.yaml → padrao.cloudflare: true): o upload direto (rupload) de vídeo longo às vezes volta 400 e o contêiner trava em
    IN_PROGRESS; por video_url o mesmo vídeo termina. Gera uma cópia ≤ 24 MB e sobe num deploy de PRÉVIA (branch próprio) do Cloudflare Pages
    do perfil (oferta.link_bio ou video_host *.pages.dev; precisa de `npx wrangler` logado); a página principal não muda. Devolve o link público ou None."""
    host = urllib.parse.urlparse((p.get("oferta") or {}).get("link_bio") or p.get("video_host") or "").hostname or ""  # video_host: perfil sem página própria hospeda o arquivo temporário em outro projeto Pages
    npx = shutil.which("npx")
    if not host.endswith(".pages.dev") or not npx: log_link(f"{ident}: sem link_bio .pages.dev ou sem npx no PATH (npx={npx})"); return None
    projeto, ramo = host.split(".")[0], re.sub(r"[^a-z0-9-]", "-", f"post-{ident}".lower())[:28]
    pasta = video.parent / "_link"; (pasta / "v").mkdir(parents=True, exist_ok=True)
    (pasta / "index.html").write_text("<!doctype html><title>.</title>", encoding="utf-8")
    dur = float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
                                          capture_output=True, text=True).stdout)["format"]["duration"])
    kbps = int(LINK_MAX_MB * 8e3 * 0.92 / dur) - 128  # vídeo + 128k de áudio cabendo em 24 MB
    leve = pasta / "v" / f"{ident}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-map", "0:v", "-map", "0:a", "-c:v", "libx264", "-preset", "slow",
                    "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.15)}k", "-bufsize", f"{kbps * 2}k", "-profile:v", "high", "-level:v", "4.0",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(leve)], check=True)
    if leve.stat().st_size > 25 * 2**20: log_link(f"{ident}: cópia com {leve.stat().st_size / 1e6:.0f} MB passa de 25 MiB"); return None
    try:  # pelo agendador o wrangler pode travar sem console: entrada vazia, modo CI e limite de tempo
        r = subprocess.run([npx, "wrangler", "pages", "deploy", str(pasta), "--project-name", projeto, "--branch", ramo, "--commit-dirty=true"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300,
                           env={**os.environ, "CI": "true", "WRANGLER_SEND_METRICS": "false"})
    except subprocess.TimeoutExpired:
        log_link(f"{ident}: deploy da prévia passou de 5 min ({projeto}/{ramo}); sem link nesta rodada"); return None
    url = f"https://{ramo}.{projeto}.pages.dev/v/{leve.name}"
    if r.returncode != 0 or requests.head(url, timeout=60).status_code != 200:
        log_link(f"{ident}: deploy da prévia falhou ({projeto}/{ramo}) rc={r.returncode}: {(r.stdout + r.stderr)[-400:]!r}"); return None
    log_link(f"{ident}: vídeo por link: {url} ({leve.stat().st_size / 1e6:.0f} MB, {kbps} kbps)")
    return url

def publish_reel(video, legenda, uid, tok, capa_offset_ms=1000, capa=None, pendente=None, link=None, teste=False, audio=None):
    dados_cont = {"media_type": "REELS", "upload_type": "resumable", "caption": legenda, "access_token": tok}
    if teste: dados_cont["trial_params"] = json.dumps({"graduation_strategy": "MANUAL"})  # reel de teste: só não seguidores veem; MANUAL = não vira reel normal sozinho em 72 h
    if audio: dados_cont["audio_configuration"] = json.dumps(audio)  # música da biblioteca da Meta: {audio_id, audio_volume, video_volume}
    if capa and capa.exists(): dados_cont["cover_url"] = capa_url(capa, tok)[0]  # capa própria (style-guide → Capa)
    else: dados_cont["thumb_offset"] = capa_offset_ms
    cid = api("POST", f"{uid}/media", data=dados_cont)["id"]
    dados = video.read_bytes()
    r = requests.post(f"{RUPLOAD}/{VER}/{cid}", headers={"Authorization": f"OAuth {tok}", "offset": "0",
                                                         "file_size": str(len(dados))}, data=dados, timeout=900)
    # o arquivo chega inteiro e o 400 ProcessingFailedError vem do processamento síncrono; vídeo curto termina ali e dá 200, vídeo longo cai no processamento assíncrono,
    # que pode levar muito mais que 10 min. Quem decide é o status do contêiner, e o mesmo contêiner é retomado nas rodadas seguintes.
    erro_upload = None if r.ok else f"upload -> {r.status_code}: {r.text[:400]}"
    if erro_upload: print(f"{erro_upload} (confiro o contêiner {cid} antes de desistir)")
    if erro_upload and link and (url := link()):  # vídeo longo: o contêiner do upload direto é abandonado (nunca publicado) e vale o do link
        dados_cont.pop("upload_type"); dados_cont["video_url"] = url
        cid = api("POST", f"{uid}/media", data=dados_cont)["id"]; erro_upload = None
    for _ in range(12 if erro_upload else 60):  # 2 min se foi para o assíncrono; 10 min no caminho normal
        st = api("GET", cid, params={"fields": "status_code,status", "access_token": tok})
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") in ("ERROR", "EXPIRED"): raise RuntimeError(f"processamento falhou: {st}" + (f" · {erro_upload}" if erro_upload else ""))
        time.sleep(10)
    else:
        if pendente:
            pendente.parent.mkdir(parents=True, exist_ok=True)
            pendente.write_text(json.dumps({"cid": cid, "criado": time.time(), "erro_upload": erro_upload}, ensure_ascii=False), encoding="utf-8")
            raise Processando(f"contêiner {cid} ainda processando; a próxima rodada retoma ({pendente.name})")
        raise TimeoutError("processamento não terminou")
    return finaliza(cid, uid, tok)

def perfil_do_item(item_path):
    partes = item_path.resolve().relative_to(ROOT).parts
    return next(p for p in perfis_ativos() if p["pasta"] == partes[0])

def publicar(item_path, dry_run=False, teste=False):
    item_path = pathlib.Path(item_path).resolve(); p = perfil_do_item(item_path)
    item = json.loads(item_path.read_text(encoding="utf-8"))
    sys.path.insert(0, str(pathlib.Path(__file__).parent)); from fila import com_palavra, confere_legenda
    video = ROOT / item["video"]; saida = ROOT / p["pasta"] / "out" / item["id"]
    try: script_ = json.loads((saida / "script.json").read_text(encoding="utf-8"))   # palavra/promessa do vídeo e SEM CTA (teste A/B)
    except Exception: script_ = None
    try: brief_ = json.loads((saida / "brief.json").read_text(encoding="utf-8"))
    except Exception: brief_ = None
    brief_cta = (brief_ or {}).get("cta")
    if item.get("ab_cta") is False or brief_cta is False: script_ = dict(script_ or {}, cta=False)   # teste A/B: edição SEM CTA nunca ganha a chamada
    # a chamada para comentar fica no CORPO, variada; o post.py nunca põe a linha no topo. Legenda já na regra volta igual.
    # A janela de repetição, o tamanho, a lição rápida e as hashtags são conferidos na entrada da fila, não aqui.
    item["legenda"] = com_palavra(item.get("legenda", ""), p, script_, ed=item["id"], horario=item.get("horario"), brief=brief_)
    rel = {"etapa": "08_post", "perfil": p["handle"], "item": str(item_path.relative_to(ROOT)), "dry_run": dry_run}
    erros = valida_video(video)
    erros += [f"legenda: {e}" for e in confere_legenda(item["legenda"], p, script_, ed=item["id"], horario=item.get("horario"), com_historico=False, brief=brief_)
              if not re.search(r"caracteres \(regra|mais de 3 hashtags|^hashtags:|^lição rápida:", e)]   # tamanho/lição/hashtags já passaram no fila.py; aqui só a estrutura da chamada
    if not item.get("legenda", "").strip(): erros.append("legenda vazia")
    if len(item.get("legenda", "")) > 2200: erros.append("legenda com mais de 2.200 caracteres")
    if pausado(p): erros.append("perfil pausado (perfil.yaml → pausado ou padrao.pausado)")
    if p.get("post_manual") and not dry_run and not teste: erros.append("postagem manual (perfil.yaml → post_manual): a pessoa agenda à mão no app/Business Suite")
    if not dry_run and not teste and len((p.get("grade") or {}).get("ciclo") or []) > 1:  # grade: a cor da capa tem que continuar o feed real; confere antes de publicar
        sys.path.insert(0, str(pathlib.Path(__file__).parent)); import feed_check
        erros += feed_check.confere_item(p, item["id"])
    conta = checar(p); rel["conta"] = conta
    if not conta["ok"]: erros.append(f'conta: {conta.get("erro")}')
    rel["erros"] = erros
    if dry_run or erros:
        rel["status"] = "dry-run" if not erros else "bloqueado"
        print(json.dumps(rel, ensure_ascii=False, indent=1)); return rel
    uid, tok, _ = credenciais(p)
    pendente = None if teste else saida / "container.json"
    if pendente and pendente.exists():  # contêiner de uma rodada anterior: publica se terminou, espera se ainda processa, recria se morreu/velho
        c = json.loads(pendente.read_text(encoding="utf-8")); idade_h = (time.time() - c["criado"]) / 3600
        try: st = api("GET", c["cid"], params={"fields": "status_code", "access_token": tok}).get("status_code")
        except Exception as e: st = f"erro: {e}"
        if st == "FINISHED":
            rel.update(finaliza(c["cid"], uid, tok), status="publicado", tentativas="retomado"); pendente.unlink()
        elif st == "IN_PROGRESS" and idade_h < (0.25 if c.get("erro_upload") else CONTEINER_MAX_H):  # upload direto com erro quase nunca termina: depois de 15 min tenta o link
            rel.update(status="processando", conteiner=c["cid"], idade_min=round(idade_h * 60))
            print(json.dumps(rel, ensure_ascii=False, indent=1)); return rel
        else:
            print(f'contêiner {c["cid"]} {st} ({idade_h:.1f} h): crio outro'); pendente.unlink()
    video = cabe_no_ig(video)  # uma vez só, antes das tentativas
    for n in range(1, (1 if teste else TENTATIVAS) + 1):
        if rel.get("status") == "publicado": break
        try:
            rel.update(publish_reel(video, item["legenda"], uid, tok, item.get("capa_offset_ms", 1000), ROOT / item["capa"] if item.get("capa") else None, pendente,
                                    link=(lambda: video_por_link(video, p, item["id"])) if CFG["padrao"].get("cloudflare") else None, teste=teste, audio=item.get("audio")), status="publicado", tentativas=n)  # item["audio"]: música da biblioteca da Meta
            break
        except Processando as e:  # não cria outro contêiner nesta rodada (nem segura os outros perfis 30 min)
            rel.update(status="processando", aviso=str(e)); print(json.dumps(rel, ensure_ascii=False, indent=1)); return rel
        except Exception as e:
            rel.setdefault("falhas", []).append({"tentativa": n, "erro": str(e)})
            if n < TENTATIVAS: time.sleep(ESPERA_S)
    saida.mkdir(parents=True, exist_ok=True)
    if teste:  # reel de teste não mexe na fila: guarda só o registro
        rel["modo"] = "teste (trial reel, graduação MANUAL)"; rel.setdefault("status", "falhou")
        (saida / "teste_trial.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(rel, ensure_ascii=False, indent=1)); return rel
    if rel.get("status") == "publicado":
        (saida / "post.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
        destino = ROOT / p["pasta"] / "posts" / "05-publicado"; destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / item_path.name
        if alvo.exists(): alvo = destino / f"{item_path.stem}_{rel.get('id') or item.get('id', 'post')}.json"  # mesmo horário de um post anterior: nunca sobrescreve o registro dele
        shutil.move(str(item_path), alvo)
        if p.get("fila_em_ordem"): empurra_fila(p, item)
        if p.get("facebook_page_id"): rel["facebook"] = post_facebook(p, item, saida)
    else:
        rel["status"] = "falhou"
        (saida / "fail.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rel, ensure_ascii=False, indent=1)); return rel

def post_facebook(p, item, saida):
    """Reel também na Página do Facebook, junto com o Instagram (perfil.yaml → facebook_page_id). Falha aqui NUNCA derruba o post do Instagram: só registra."""
    tok = ""
    try:
        G = f"{GRAPH}/{VER}"; pid = p["facebook_page_id"]; tok = os.getenv(p["token_env"], "").strip()
        ini = requests.post(f"{G}/{pid}/video_reels", params={"upload_phase": "start", "access_token": tok}, timeout=60).json()
        dados = (ROOT / item["video"]).read_bytes()
        requests.post(ini["upload_url"], headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(dados))}, data=dados, timeout=300).raise_for_status()
        r = requests.post(f"{G}/{pid}/video_reels", params={"upload_phase": "finish", "video_id": ini["video_id"], "video_state": "PUBLISHED", "description": item.get("legenda", ""), "access_token": tok}, timeout=120)
        r.raise_for_status(); res = {"status": "enviado", "video_id": ini["video_id"]}
    except Exception as e:
        res = {"status": "falhou", "erro": (str(e).replace(tok, "***") if tok else str(e))[:300]}
    (saida / "post_facebook.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res

def empurra_fila(p, item):
    """perfil.yaml → fila_em_ordem: se a edição saiu dias depois do horário (ex.: parte 1 atrasada), empurra as seguintes pelos
    mesmos dias, para o "parte 2 amanhã" continuar certo."""
    atraso = (dt.datetime.now(TZ).date() - dt.datetime.strptime(item["horario"], "%Y-%m-%d %H:%M").date()).days
    if atraso <= 0: return
    pasta = ROOT / p["pasta"] / "posts" / "04-aprovado"
    for f in sorted(pasta.glob("*.json"), reverse=True):  # do último para o primeiro: o nome novo nunca bate num que ainda vai andar
        it = json.loads(f.read_text(encoding="utf-8"))
        novo = dt.datetime.strptime(it["horario"], "%Y-%m-%d %H:%M") + dt.timedelta(days=atraso)
        it["horario"] = novo.strftime("%Y-%m-%d %H:%M")
        (pasta / f'{novo.strftime("%Y-%m-%d_%H%M")}.json').write_text(json.dumps(it, ensure_ascii=False, indent=1), encoding="utf-8")
        if f.name != f'{novo.strftime("%Y-%m-%d_%H%M")}.json': f.unlink()
        print(f'{it["id"]}: empurrado {atraso} dia(s) -> {it["horario"]}')

def proximo(p, dry_run=False):
    """Um post por execução e por perfil: o item mais antigo cujo horário (fuso de perfis.yaml → padrao.fuso) já chegou."""
    agora = dt.datetime.now(TZ)
    fila = sorted((ROOT / p["pasta"] / "posts" / "04-aprovado").glob("*.json"))
    vencidos = [f for f in fila if dt.datetime.strptime(json.loads(f.read_text(encoding="utf-8"))["horario"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ) <= agora]
    if not vencidos: print(f'{p["handle"]}: nada vencido (fila={len(fila)})'); return None
    return publicar(vencidos[0], dry_run)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["checar", "publicar", "proximo", "testar-capa"])
    ap.add_argument("item", nargs="?"); ap.add_argument("--perfil"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--teste", action="store_true", help="publicar: reel de teste (trial), sem graduar sozinho, sem mexer na fila")
    a = ap.parse_args()
    alvo = [acha_perfil(a.perfil)] if a.perfil else perfis_ativos()
    if a.cmd == "checar": print(json.dumps([checar(p) for p in alvo], ensure_ascii=False, indent=1))
    elif a.cmd == "testar-capa":  # sobe a capa como foto não publicada, confere o link público e apaga a foto
        item = json.loads(pathlib.Path(a.item).read_text(encoding="utf-8")); p = perfil_do_item(pathlib.Path(a.item).resolve())
        _, tok, _ = credenciais(p); url, foto = capa_url(ROOT / item["capa"], tok)
        api("DELETE", foto, params={"access_token": tok})
        print(json.dumps({"capa": item["capa"], "link_publico_ok": True, "foto_de_teste_apagada": True}, ensure_ascii=False))
    elif a.cmd == "publicar": publicar(a.item, a.dry_run, a.teste)
    else:
        for p in alvo: proximo(p, a.dry_run)
