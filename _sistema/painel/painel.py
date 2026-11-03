"""Painel de Produção: página local, ao vivo, para bater o olho e saber o que está rodando, o que está parado e por quê.
Uso: python _sistema/painel/painel.py        (abre http://127.0.0.1:8765 no navegador)
     python _sistema/painel/painel.py --sem-abrir
Só lê: perfis.yaml, .env, posts/, out/<id>/ (inclusive cross_youtube.json / cross_tiktok.json do cross-post), reviews/falhas/, logs/, agendador
e (métricas) a Graph API da Meta e a YouTube Data API. Não muda nada no projeto; só grava logs/painel-alertas.json (o que já virou notificação do Windows).
O token do TikTok o painel NÃO testa: renovar o refresh token troca o valor no .env (crosspost.py faz isso ao postar)."""
import sys as _sys; _sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "orquestrador"))
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, base64, datetime as dt, html, json, mimetypes, os, re, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo
import requests, yaml

ROOT = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
sys.path.insert(0, str(ROOT / "_sistema" / "orquestrador"))
import post as meta  # credenciais e chamada da Graph API (carrega o .env)

_PAD = (carrega(ROOT).get("padrao") or {})
BR = ZoneInfo(_PAD.get("fuso_painel") or "America/Sao_Paulo")   # hora mostrada no painel (perfis.yaml → padrao.fuso_painel)
NY = ZoneInfo(_PAD.get("fuso") or "America/New_York")           # fuso dos horários de postagem (perfis.yaml → padrao.fuso)
PORTA = 8765
VIVO_S = 15 * 60          # log mexido há menos de 15 min = sessão trabalhando (mesma regra do orquestrador)
METRICAS_S = 10 * 60      # cache das métricas da Meta
DIARIO_H = 72
ETAPAS = [("pauta", "brief.json"), ("roteiro", "script.json"), ("voz", "voice.mp3"), ("cena", "props.json"),
          ("render", "video.mp4"), ("qa", "qa.json"), ("fila", None), ("post", None)]
REPROVA_REVISAR = 3      # reprovações em 24 h a partir das quais o painel pede revisão (abaixo disso o sistema só refaz)
ALERTAS_S = 60          # vigia de alertas: confere o estado a cada minuto
ALERTAS_F = LOGS / "painel-alertas.json"   # o que já foi avisado (sobrevive a reinício)
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # powershell sem piscar janela (roda pelo pythonw)
COR_PADRAO = ["#8a8f98", "#22252b"]   # perfil sem perfil.yaml → cor

def cores_do(p):
    """perfil.yaml → cor: "#RRGGBB" ou [destaque, fundo]; sem a chave, cinza."""
    c = p.get("cor")
    if isinstance(c, str): return [c, COR_PADRAO[1]]
    if isinstance(c, (list, tuple)) and c: return [c[0], c[1] if len(c) > 1 else COR_PADRAO[1]]
    return list(COR_PADRAO)

def ler_json(f):
    try: return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception: return None

def jsons(d):
    return sorted(f for f in d.glob("*.json") if not f.name.startswith("._")) if d.exists() else []

def hora(d):
    return {"br": d.astimezone(BR).strftime("%d/%m %H:%M"), "ny": d.astimezone(NY).strftime("%d/%m %H:%M"),
            "iso": d.isoformat(), "t": d.timestamp()}

def de_ny(texto):
    return dt.datetime.strptime(texto, "%Y-%m-%d %H:%M").replace(tzinfo=NY)

def quando_item(it):
    """Horário do item da fila: o REAL de postagem à mão (horarios-reais.json, hora local) se houver; senão o `horario` do json (fuso de postagem). Retorna (datetime, nota)."""
    try:
        r = (ler_json(Path(__file__).with_name("horarios-reais.json")) or {}).get(str(it.get("id")))
        if r and r.get("br"): return dt.datetime.strptime(r["br"], "%Y-%m-%d %H:%M").replace(tzinfo=BR), r.get("nota")
    except Exception: pass
    return (de_ny(it["horario"]) if it.get("horario") else None), None

def de_mtime(f):
    return dt.datetime.fromtimestamp(Path(f).stat().st_mtime).astimezone()

def logs_do(edicao):
    return sorted(LOGS.glob(f"{edicao}_*.log"), key=lambda f: f.stat().st_mtime) if LOGS.exists() else []

def titulo(texto):
    """1ª linha da legenda que não seja a chamada da palavra (comment "X" …; ela fica no corpo e a 1ª linha é o gancho)"""
    linhas = [l.strip() for l in (texto or "").split("\n") if l.strip()]
    return next((l for l in linhas if not l.startswith("💬") and 'comment "' not in l.lower()), linhas[0] if linhas else "")

def cfg():
    return carrega(ROOT)

# ---------- agendador do Windows (cache de 60 s) ----------
_tarefas = {"t": 0, "dados": []}
def tarefas():
    if time.time() - _tarefas["t"] < 60: return _tarefas["dados"]
    cmd = ("Get-ScheduledTask -TaskName 'INSTAGRANS*' | % { $i = Get-ScheduledTaskInfo -TaskName $_.TaskName; "
           "[pscustomobject]@{nome=$_.TaskName; estado=[string]$_.State; ultima=$i.LastRunTime.ToString('o'); "
           "proxima=$(if ($i.NextRunTime) { $i.NextRunTime.ToString('o') } else { '' }); resultado=$i.LastTaskResult} } | ConvertTo-Json")
    dados = []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=20,
                             creationflags=SEM_JANELA).stdout
        brutos = json.loads(out) if out.strip() else []
        for t in brutos if isinstance(brutos, list) else [brutos]:
            ultima = dt.datetime.fromisoformat(t["ultima"]) if t.get("ultima") else None
            nunca = not ultima or ultima.year < 2000 or t["resultado"] == 267011  # 0x41303 = ainda não rodou
            prox = dt.datetime.fromisoformat(t["proxima"]) if t.get("proxima") else None
            dados.append({"nome": t["nome"].replace("INSTAGRANS ", ""), "estado": t["estado"],
                          "ligada": t["estado"] in ("Ready", "Running"), "rodando": t["estado"] == "Running",
                          "nunca_rodou": nunca, "ultima": None if nunca else hora(ultima.astimezone()),
                          "proxima": hora(prox.astimezone()) if prox else None,
                          "resultado_ok": nunca or t["resultado"] in (0, 267009, 2147946720), "resultado": t["resultado"]})
    except Exception as e:
        dados = [{"nome": "?", "erro": str(e)}]
    _tarefas.update(t=time.time(), dados=dados)
    return dados

# ---------- métricas da Meta (cache por perfil, atualizado em segundo plano) ----------
_metricas, _trava = {}, threading.Lock()

def mapa_local(p):
    """permalink → dados locais da edição (id, capa, QA), a partir de out/<id>/post.json"""
    m = {}
    for f in (ROOT / p["pasta"] / "out").glob("*/post.json"):
        d = ler_json(f) or {}
        if d.get("permalink"):
            ed = f.parent.name; qa = ler_json(f.parent / "qa.json") or {}
            capa = f.parent / "cover.jpg"
            m[d["permalink"]] = {"id": ed, "capa": capa.relative_to(ROOT).as_posix() if capa.exists() else None,
                                 "qa": qa.get("media_ponderada")}
    return m

def buscar_metricas(p):
    uid, tok, falta = meta.credenciais(p)
    if falta: return {"perfil": p["handle"], "sem_meta": True}
    agora = int(time.time()); r = {"perfil": p["handle"], "atualizado": hora(dt.datetime.now(BR))}
    try:
        c = meta.api("GET", uid, params={"fields": "username,followers_count,follows_count,media_count", "access_token": tok})
        r["conta"] = {k: c.get(k) for k in ("username", "followers_count", "follows_count", "media_count")}
        try:
            a = meta.api("GET", f"{uid}/insights", params={"metric": "reach,views,profile_views,accounts_engaged,total_interactions",
                         "period": "day", "metric_type": "total_value", "since": agora - 7 * 86400, "until": agora, "access_token": tok})
            r["conta7d"] = {d["name"]: (d.get("total_value") or {}).get("value") for d in a["data"]}
        except Exception as e: r["conta7d_erro"] = str(e)[:200]
        midia = meta.api("GET", f"{uid}/media", params={"fields": "id,caption,permalink,timestamp,media_product_type,thumbnail_url,like_count,comments_count",
                                                        "limit": 25, "access_token": tok})["data"]
        locais = mapa_local(p); reels = []
        for it in midia:
            ins = {}
            try:
                d = meta.api("GET", f'{it["id"]}/insights', params={"metric": "views,reach,saved,shares,total_interactions,ig_reels_avg_watch_time,ig_reels_video_view_total_time",
                                                                     "access_token": tok})
                ins = {x["name"]: x["values"][0]["value"] for x in d["data"]}
            except Exception: pass
            loc = locais.get(it["permalink"], {})
            ts = dt.datetime.strptime(it["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
            reels.append({"media_id": it["id"], "link": it["permalink"], "quando": hora(ts), "titulo": titulo(it.get("caption")),
                          "views": ins.get("views"), "alcance": ins.get("reach"), "salvos": ins.get("saved"), "compart": ins.get("shares"),
                          "curtidas": it.get("like_count"), "coment": it.get("comments_count"), "interacoes": ins.get("total_interactions"),
                          "media_s": round(ins["ig_reels_avg_watch_time"] / 1000, 1) if ins.get("ig_reels_avg_watch_time") is not None else None,
                          "total_min": round(ins["ig_reels_video_view_total_time"] / 60000) if ins.get("ig_reels_video_view_total_time") is not None else None,
                          "id": loc.get("id"), "capa": loc.get("capa"), "qa": loc.get("qa"), "thumb": it.get("thumbnail_url")})
        r["reels"] = reels
    except Exception as e:
        r["erro"] = str(e)[:300]
    return r

def metricas(p, forcar=False):
    with _trava: c = _metricas.get(p["prefixo"])
    if forcar or not c or time.time() - c["_t"] > METRICAS_S:
        c = {**buscar_metricas(p), "_t": time.time()}
        with _trava: _metricas[p["prefixo"]] = c
    return c

def laco_metricas():
    while True:
        for p in cfg()["perfis"]:
            if p.get("status") == "ativo" and p.get("token_env"):
                try: metricas(p)
                except Exception: pass
        time.sleep(METRICAS_S)

# ---------- situação de cada perfil: o primeiro bloqueio vence ----------
def _data(v):
    try: return dt.datetime.fromisoformat(str(v)).replace(tzinfo=BR) if v else None
    except ValueError: return None

def pausa_ativa(p):
    """perfil.yaml → pausa_programada {ate, motivo, por}: pausa controlada com hora para voltar (o orquestrador religa sozinho)."""
    pp = p.get("pausa_programada") or {}
    try: ate = dt.datetime.fromisoformat(str(pp["ate"])).replace(tzinfo=BR) if pp.get("ate") else None
    except ValueError: return None
    return {**pp, "ate_dt": ate} if ate and dt.datetime.now(BR) < ate else None

def situacao(p, pad, apr, em_vivo, falhas_24h, auto, post_ligado, prod_desligada=False):
    if p.get("status") == "montando":  # perfil novo, fora da automação até virar ativo
        return "montando", "Em implantação", "Perfil novo: entra na automação quando voz, vídeo, Meta e DM estiverem prontos", []
    if p.get("status") != "ativo":
        return "fora", "Fora do PC", p.get("nicho") or "fora da automação", []
    motivos = []  # tudo que trava ou pede atenção, em ordem
    pp = pausa_ativa(p)  # vale também com producao_auto desligado por quem pausou (o job que religa troca o producao_auto na hora)
    volta = (pp["ate_dt"].strftime("%d/%m %H:%M") + " (local) / " + pp["ate_dt"].astimezone(NY).strftime("%d/%m %H:%M") + " (postagem)") if pp else ""   # com a data e os dois fusos ("às 00:00" sozinho parece que volta hoje)
    lim = None  # limite de uso do Claude estourado (orquestrador grava logs/limite-sessao.json): explica a fila vazia, não é falha do perfil
    try:
        lim = dt.datetime.fromisoformat(json.loads((ROOT / "logs" / "limite-sessao.json").read_text(encoding="utf-8"))["ate"])
        if lim <= dt.datetime.now(): lim = None
    except Exception: lim = None
    if lim: motivos.append(("info", f"Limite de uso do Claude estourado: a produção volta às {lim:%H:%M} ({lim:%d/%m}). Não é erro do perfil"))
    if pp: motivos.append(("info", f"Pausa programada até {volta}: {pp.get('motivo') or 'sem motivo'}. Volta sozinha, não é erro"
                                   + (f" (controlada pela {pp['por']})" if pp.get("por") else "")))
    meta.load_dotenv(ROOT / ".env", override=True)  # relê o .env: token novo aparece sem reiniciar o painel
    manual_sem_meta = bool(p.get("post_manual")) and (not p.get("token_env") or bool(meta.credenciais(p)[2]))  # postagem à mão de propósito (post_manual) sem token: falta de Meta não é alerta
    sem_meta = False if manual_sem_meta else (bool(meta.credenciais(p)[2]) if p.get("token_env") else True)
    sem_producao = not (ROOT / p["pasta"] / "producao.md").exists() and not (p.get("post_manual") and not p.get("producao_auto"))
    voz = p.get("voz")
    sem_voz = isinstance(voz, dict) and str(voz.get("voice_id", "")).upper() == "A_DEFINIR"
    if pad.get("pausado"): motivos.append(("crit", "Publicação pausada em todos os perfis (padrao.pausado)"))
    elif p.get("pausado"): motivos.append(("info", "Pausado de propósito (pausado: true no perfil.yaml do perfil); volta quando você despausar. Não é erro"))  # pausa decidida não pede atenção
    if sem_meta: motivos.append(("crit", "Meta não conectada: falta a página do Facebook e o token"))
    if manual_sem_meta: motivos.append(("info", "Postagem manual, sem Meta: você posta e o painel move o json para 05-publicado"))
    if sem_producao: motivos.append(("crit", "Produção do perfil ainda não montada (falta producao.md)"))
    if sem_voz: motivos.append(("warn", "Voz do ElevenLabs ainda não escolhida"))
    if prod_desligada: motivos.append(("crit", "Tarefa de produção desligada no agendador do Windows"))
    elif not auto and not pp: motivos.append(("info", "Produção automática ainda não ligada (producao_auto no perfil.yaml do perfil)"))  # etapa da implantação, não erro
    if not post_ligado: motivos.append(("crit", "Tarefa de postagem desligada"))
    # níveis: crit = parou / falta montar · warn = precisa de revisão sua · info = o sistema resolve sozinho, só para saber
    alvo = p.get("fila_alvo", pad.get("fila_alvo", 3))  # por perfil
    if not apr and pp: motivos.append(("info", f"Fila vazia por enquanto: volta a encher quando a pausa acabar, em {volta}"))
    elif not apr and not p.get("producao_auto"): motivos.append(("info", "Fila vazia: os vídeos saem à mão até ligar a produção automática"))  # implantação
    elif not apr and lim: motivos.append(("warn", f"Fila vazia por causa do limite do Claude; volta a encher depois das {lim:%H:%M}"))
    elif not apr: motivos.append(("crit", "Fila vazia: nenhum vídeo pronto para subir"))
    elif len(apr) < alvo:
        motivos.append(("info", f"Fila com {len(apr)} de {alvo} vídeos: a produção repõe sozinha" + (f" depois de {volta}" if pp else "")) if auto else
                       ("info", f"Fila com {len(apr)} de {alvo} vídeos: os vídeos saem à mão até ligar a produção automática") if not p.get("producao_auto") else
                       ("warn", f"Fila com {len(apr)} de {alvo} vídeos e sem produção automática: alguém precisa produzir"))
    if falhas_24h >= REPROVA_REVISAR:
        motivos.append(("warn", f"{falhas_24h} edições reprovadas no QA em 24 h: vale revisar roteiro e QA"))
    elif falhas_24h:
        motivos.append(("info", f"{falhas_24h} edição(ões) reprovada(s) no QA em 24 h: descartada(s), o sistema faz outra"))
    if pad.get("pausado") or p.get("pausado"): return "pausado", "Pausado", motivos[0][1], motivos
    if sem_meta or sem_producao: return "montando", "Montando", motivos[0][1], motivos
    if em_vivo and not auto: return "produzindo", "Produzindo à mão", "Sessão aberta à mão fazendo uma edição", motivos
    if em_vivo: return "produzindo", "Produzindo agora", "Sessão automática fazendo uma edição", motivos
    if not apr and not pp and not p.get("producao_auto") and post_ligado:  # nunca foi automático: ainda em implantação, não "parou"
        return "montando", "Montando", "Falta ligar a produção automática (producao_auto); até lá os vídeos saem à mão", motivos
    if not post_ligado or (not apr and not pp): return "parado", "Parado", next(m for n, m in motivos if n == "crit"), motivos
    if pp: return "programada", "Pausa programada", f"Volta a criar sozinho em {volta} · {pp.get('motivo') or ''}".rstrip(" ·"), motivos
    if not auto and not p.get("producao_auto"):  # ainda em implantação: posta sozinho, vídeo novo sai à mão
        return "rodando", "Posta sozinho · vídeos à mão", next((m for n, m in motivos if n == "info" and "Fila" in m), "Produção automática ainda não ligada"), motivos
    if not auto: return "atencao", "Só posta, não cria", motivos[0][1], motivos
    if any(n == "warn" for n, _ in motivos): return "atencao", "Precisa de revisão", next(m for n, m in motivos if n == "warn"), motivos
    return "rodando", "Rodando sozinho", next((m for n, m in motivos if n == "info"), "Produz e posta sem ninguém"), motivos

def modo(cod, auto, post_ligado):
    """o que roda sem ninguém, em uma frase"""
    if cod in ("fora", "montando", "pausado"): return "manual", "Ainda não automático" if cod == "montando" else "Automação parada"
    if cod == "programada": return "meio", "Posta normalmente; criação de vídeo em pausa controlada, volta sozinha"
    if auto and post_ligado: return "auto", "Automático: produz e posta sozinho"
    if post_ligado and cod == "produzindo": return "meio", "Posta sozinho; este vídeo está sendo feito à mão"
    if post_ligado: return "meio", "Posta sozinho o que está na fila, mas não cria vídeo novo"
    return "manual", "Não posta sozinho: postagem automática desligada"

def quadro(p, cod, apr, vivo, auto, post_ligado, prod_ligada, pad, motivos, cx):
    """O cartão diz em poucas palavras o que acontece AGORA, o que acontece DEPOIS (e se volta sozinho) e o que DEPENDE DELE.
    Regra: nenhuma frase pode parecer contradizer outra; sempre com a data completa quando houver volta."""
    n = len(apr); alvo = p.get("fila_alvo", pad.get("fila_alvo", 3)); pp = pausa_ativa(p)
    volta = (pp["ate_dt"].strftime("%d/%m às %H:%M") + " (local) / " + pp["ate_dt"].astimezone(NY).strftime("%d/%m %H:%M") + " (postagem)") if pp else ""
    cfg_auto = bool(p.get("producao_auto")); prod_desl = cfg_auto and not prod_ligada
    fila_txt = f"{n} vídeo{'s' if n != 1 else ''} na fila"
    voce = []
    if cod == "pausado":
        agora = "Parado de propósito: não posta e não cria." + (f" {fila_txt} retido{'s' if n != 1 else ''}." if n else "")
        depois = "Não volta sozinho. Só quando você liberar."
        voce.append("Liberar o perfil quando estiver pronto")
    elif pp:
        agora = (f"Em pausa de criação até {volta}. Posta só o que já está na fila ({fila_txt})." if n else f"Em pausa até {volta}. Fila vazia: nada posta nem cria até lá.")
        depois = (f"Em {volta.split(' (')[0]} volta sozinho: cria vídeo novo sempre que a fila ficar abaixo de {alvo}." if prod_ligada and cfg_auto
                  else f"Em {volta.split(' (')[0]} a pausa acaba, mas só volta a criar se a tarefa de produção estiver ligada." if cfg_auto
                  else f"Quando a pausa acabar, o perfil continua sem criar sozinho.")
        if cfg_auto and not prod_ligada: voce.append("Ligar a tarefa de produção até a pausa acabar")
    elif cod in ("montando", "fora") or not cfg_auto:
        agora = (f"Posta só o que já está na fila ({fila_txt})." if n else "Fila vazia: nada para postar.") if post_ligado else "Postagem automática desligada."
        depois = "Não cria vídeo sozinho: cada vídeo novo é feito à mão, quando você pede."
        if n < alvo: voce.append(f"Pedir novos vídeos (fila {n} de {alvo})")
        voce.append("Decidir se liga a produção automática (producao_auto)")
    elif vivo:
        agora = "Uma sessão está fazendo um vídeo agora." + (" (à mão)" if not auto else "")
        depois = "Quando terminar, passa pelo QA e entra na fila." if auto else "Quando terminar e passar no QA, entra na fila."
    elif not post_ligado:
        agora = "Não posta: a tarefa de postagem está desligada."; depois = "Nada acontece até ligar a tarefa de postagem."
        voce.append("Ligar a tarefa de postagem no Windows")
    elif prod_desl:
        agora = f"Posta só o que já está na fila ({n} de {alvo}). Não cria vídeo novo."
        depois = f"Hoje nada repõe a fila, porque a tarefa de produção está desligada. Quando for ligada, cria sozinho sempre que a fila ficar abaixo de {alvo} (até {pad.get('producao_max_por_noite', 1)} por checagem, a cada 30 min)."
        voce.append("Ligar a tarefa de produção no Windows para o perfil voltar a criar")
    else:
        agora = f"Tudo automático. Fila com {n} de {alvo}."
        depois = (f"Está abaixo de {alvo}: a próxima checagem (a cada 30 min) cria vídeo para repor." if n < alvo
                  else f"Quando a fila ficar abaixo de {alvo}, cria um vídeo novo sozinho.")
    ofe = p.get("oferta") or {}
    if p.get("status") == "ativo" and ofe.get("palavra") and not ofe.get("dm_ativa"): voce.append("DM desligada: falta o link do produto (link_gratis) para a resposta automática funcionar")
    voce += [t for nv, t in motivos if nv == "warn" and not t.startswith("Fila com")]
    voce += [f'{PLAT_NOME[pl]}: {d["texto"]}' for pl, d in cx["plats"].items() if d["estado"] in ("erro", "bloqueado")]
    voce += [f'cross-post de {x["id"]} ({PLAT_NOME[x["plataforma"]]}) falhou' for x in cx["fila"] if x["estado"] == "falhou"]
    voce += [f'Short {x["id"]}: {x["problema"]}' for x in cx["no_ar"] if x.get("problema")]
    return {"agora": agora, "depois": depois, "voce": voce}

def chaves(p, post_ligado, prod_ligada, cx, pausado_global=False, rot=None):
    """O que está LIGADO e o que está DESLIGADO de cada perfil, para bater o olho: [{nome, on, txt}]."""
    pausado = bool(p.get("pausado") or pausado_global); pp = pausa_ativa(p); ofe = p.get("oferta") or {}
    if pausado: posta = (False, "pausado")
    elif not post_ligado: posta = (False, "tarefa desligada")
    else: posta = (True, "")
    if pausado: cria = (False, "pausado")
    elif pp: cria = (False, "pausa até " + pp["ate_dt"].strftime("%d/%m"))
    elif rot: cria = (rot["on"], rot["txt"] if rot["on"] else "tarefa agendada não encontrada")
    elif not p.get("producao_auto"): cria = (False, "à mão")
    elif not prod_ligada: cria = (False, "tarefa desligada")
    else: cria = (True, "")
    if not ofe.get("palavra"): dm = (False, "não usa")
    elif not ofe.get("dm_ativa"): dm = (False, "desligada")
    elif not ofe.get("link_gratis"): dm = (False, "sem link")
    else: dm = (True, "")
    yt = (cx["plats"].get("youtube") or {})
    yts = (yt.get("estado") == "ligado", "" if yt.get("estado") == "ligado" else {"sem_config": "sem canal", "bloqueado": "bloqueado", "erro": "erro"}.get(yt.get("estado"), "sem canal"))
    return [{"nome": n, "on": v[0], "txt": v[1]} for n, v in (("Posta", posta), ("Cria", cria), ("DM", dm), ("YouTube", yts))]

def marcos(p, apr, auto):
    voz = p.get("voz"); ofe = p.get("oferta") or {}
    tem_voz = voz is None or (isinstance(voz, dict) and str(voz.get("voice_id", "")).upper() != "A_DEFINIR")
    tem_meta = (bool(p.get("post_manual")) and not p.get("token_env")) or (bool(p.get("token_env")) and not meta.credenciais(p)[2])
    return [{"nome": "guia", "ok": (ROOT / p["pasta"] / "guia.html").exists()},
            {"nome": "voz", "ok": tem_voz},
            {"nome": "produção", "ok": (ROOT / p["pasta"] / "producao.md").exists()},
            {"nome": "meta", "ok": tem_meta},
            {"nome": "agendador", "ok": auto},
            {"nome": "fila", "ok": bool(apr)},
            {"nome": "dm", "ok": bool(ofe.get("dm_ativa"))},
            {"nome": "loja", "ok": bool(ofe.get("link_gratis") or ofe.get("link_bio"))}]

def dm_ultimas():
    f = LOGS / "dm.log"; ult, enviados = {}, []
    if not f.exists(): return ult, enviados
    for linha in f.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
        try: ev = json.loads(linha)
        except ValueError: continue
        if ev.get("perfil"): ult[ev["perfil"]] = ev
        for c in ev.get("comentarios_com_palavra") or []:
            if isinstance(c, dict) and (c.get("enviado") or c.get("dm")): enviados.append((ev, c))
    return ult, enviados

# ---------- cross-post: YouTube Shorts e TikTok (_sistema/orquestrador/crosspost.py; pedido: PEDIDO-YOUTUBE.md) ----------
CROSS_S = 10 * 60          # cache da YouTube Data API e do teste de token (como as métricas do Instagram)
CROSS_ATRASO_MIN = 30      # o Short sai depois do reel (mesmo valor do crosspost.py)
CROSS_ATRASADO_MIN = 24 * 60    # ritmo do YouTube = 3/dia com 4 h de intervalo (28/10/2026): a fila acumula de propósito; só avisa depois de 24 h do horário devido
PLATS = ("youtube", "tiktok")
PLAT_NOME = {"youtube": "YouTube", "tiktok": "TikTok"}
PLAT_ENV = {"youtube": ("client_id_env", "client_secret_env", "refresh_token_env"), "tiktok": ("client_key_env", "client_secret_env", "refresh_token_env")}
YT_API = "https://www.googleapis.com/youtube/v3"
_yt, _yt_trava = {}, threading.Lock()

def env_valores():
    """.env lido na hora (colar uma credencial nova vale sem reiniciar o painel) por cima do ambiente"""
    from dotenv import dotenv_values
    v = dict(os.environ); v.update({k: x for k, x in dotenv_values(ROOT / ".env").items() if x})
    return v

def cross_faltas(p, plat, ev):
    c = ((p.get("crosspost") or {}).get(plat)) or {}
    return [c.get(k, k) for k in PLAT_ENV[plat] if not str(ev.get(c.get(k, ""), "")).strip()]

def cross_registros(p, plat="youtube"):
    """um registro por edição já enviada: out/<id>/cross_<plataforma>.json (o mais novo primeiro)"""
    r = []
    for f in (ROOT / p["pasta"] / "out").glob(f"*/cross_{plat}.json"):
        r.append({**(ler_json(f) or {}), "id": f.parent.name, "t": f.stat().st_mtime})
    return sorted(r, key=lambda x: -x["t"])

def yt_acesso(p, ev):
    c = p["crosspost"]["youtube"]
    r = requests.post("https://oauth2.googleapis.com/token", data={"client_id": ev[c["client_id_env"]], "client_secret": ev[c["client_secret_env"]],
                      "refresh_token": ev[c["refresh_token_env"]], "grant_type": "refresh_token"}, timeout=30)
    if not r.ok:
        try: j = r.json(); msg = j.get("error_description") or j.get("error") or r.text[:160]
        except ValueError: msg = r.text[:160]
        raise RuntimeError(f"token do YouTube recusado ({r.status_code}): {msg}")
    return r.json()["access_token"]

def yt_situacao(item):
    """o que o YouTube diz de um Short: publico, nao_listado, privado, removido (sumiu) ou rejeitado"""
    if item is None: return "removido"
    st = item.get("status") or {}
    if st.get("uploadStatus") == "deleted": return "removido"
    if st.get("uploadStatus") in ("rejected", "failed"): return "rejeitado"
    return {"public": "publico", "unlisted": "nao_listado", "private": "privado"}.get(st.get("privacyStatus"), "desconhecido")

def buscar_youtube(p):
    """canal (inscritos, views), os Shorts enviados pelo cross-post (views, likes, comentários, situação) e, se o token tiver o escopo, o Analytics de 7 dias"""
    agora = dt.datetime.now(BR); r = {"perfil": p["handle"], "atualizado": hora(agora), "shorts": []}
    ev = env_valores(); f = cross_faltas(p, "youtube", ev)
    if f: r["token"] = "faltam"; r["faltam_no_env"] = f; return r
    try: tok = yt_acesso(p, ev)
    except Exception as e: r["token"] = "erro"; r["erro"] = str(e)[:300]; return r
    r["token"] = "ok"; H = {"Authorization": f"Bearer {tok}"}
    try:
        ch = requests.get(f"{YT_API}/channels", params={"part": "snippet,statistics", "mine": "true"}, headers=H, timeout=30)
        if ch.ok and ch.json().get("items"):
            it = ch.json()["items"][0]; s = it.get("statistics", {})
            r["canal"] = {"id": it["id"], "titulo": it["snippet"].get("title"), "handle": it["snippet"].get("customUrl"),
                          "inscritos": None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0)),
                          "views": int(s.get("viewCount", 0)), "videos": int(s.get("videoCount", 0))}
        else: r["canal_erro"] = f"não consegui ler o canal ({ch.status_code}): {ch.text[:160]}"
        regs = cross_registros(p); ids = [x["video_id"] for x in regs if x.get("video_id")][:50]; achados, lido = {}, False
        if ids:
            v = requests.get(f"{YT_API}/videos", params={"part": "snippet,statistics,status", "id": ",".join(ids)}, headers=H, timeout=30)
            if v.ok: achados = {i["id"]: i for i in v.json().get("items", [])}; lido = True
            else: r["videos_erro"] = f"não consegui ler os Shorts ({v.status_code}): {v.text[:160]}"
        for x in regs:
            it = achados.get(x.get("video_id")); st = (it or {}).get("statistics") or {}
            r["shorts"].append({"id": x["id"], "video_id": x.get("video_id"), "url": x.get("url"), "enviado": hora(dt.datetime.fromtimestamp(x["t"]).astimezone()),
                                "titulo": ((it or {}).get("snippet") or {}).get("title"), "situacao": yt_situacao(it) if lido else None,
                                "privacidade": ((it or {}).get("status") or {}).get("privacyStatus"),
                                "views": int(st["viewCount"]) if "viewCount" in st else None, "likes": int(st["likeCount"]) if "likeCount" in st else None,
                                "comentarios": int(st["commentCount"]) if "commentCount" in st else None})
        sete = time.time() - 7 * 86400
        r["views_shorts_7d"] = sum(s["views"] or 0 for s, x in zip(r["shorts"], regs) if x["t"] >= sete)
        a = requests.get("https://youtubeanalytics.googleapis.com/v2/reports", params={"ids": "channel==MINE", "startDate": (agora - dt.timedelta(days=7)).date().isoformat(),
                         "endDate": agora.date().isoformat(), "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained"}, headers=H, timeout=30)
        if a.ok and a.json().get("rows"): r["analytics"] = dict(zip(("views", "minutos", "duracao_media_s", "inscritos_ganhos"), a.json()["rows"][0]))
        elif "accessNotConfigured" in a.text or "has not been used" in a.text: r["analytics_erro"] = "ative a YouTube Analytics API no projeto do Google Cloud"
        elif a.status_code in (401, 403): r["analytics_erro"] = "precisa do escopo yt-analytics.readonly e de nova autorização (crosspost.py auth-youtube) com esse escopo"
        elif not a.ok: r["analytics_erro"] = f"o Analytics respondeu {a.status_code}"
    except Exception as e: r["erro"] = str(e)[:300]
    return r

def youtube(p, forcar=False):
    pref = p["prefixo"]
    with _yt_trava: c = _yt.get(pref)
    if forcar or not c or time.time() - c["_t"] > CROSS_S:
        c = {**buscar_youtube(p), "_t": time.time()}
        with _yt_trava: _yt[pref] = c
    return c

def laco_drive():
    """A cada 15 min copia a fila aprovada para a pasta do Drive (drive_fila.py); sem .env → DRIVE_PASTA (ou pasta inexistente), não faz nada."""
    time.sleep(20)
    while True:
        try:
            base = (env_valores().get("DRIVE_PASTA") or "").strip().strip('"')
            if base and Path(base).exists():
                subprocess.run([sys.executable, str(AQUI / "drive_fila.py")], timeout=1500, capture_output=True, creationflags=SEM_JANELA)
        except Exception: pass
        time.sleep(900)


def laco_cross():
    time.sleep(3)
    while True:
        for p in cfg()["perfis"]:
            if p.get("status") == "ativo" and (p.get("crosspost") or {}).get("youtube"):
                try: youtube(p)
                except Exception: pass
        time.sleep(CROSS_S)

CROSS_TOLERANCIA_MIN = 120   # depois do horário previsto pelas regras do crosspost.py (a tarefa roda a cada 30 min; a cota do projeto pode atrasar mais um pouco)

def _prever_youtube(p, itens, agora):
    """'atrasado' só quando o crosspost.py DEVERIA ter enviado (regras dele: 3/dia por canal, 4 h entre envios, um por vez, do mais antigo ao mais novo) e não enviou.
    Lê as constantes e envios_do_canal do próprio crosspost.py (não duplica a regra); o teto do projeto (MAX_DIA, todos os canais juntos) também; a tolerância cobre o resto."""
    elegiveis = [x for x in itens if x["estado"] == "esperando"]
    if not elegiveis: return
    try:
        import crosspost as cp; maxd, horas = cp.MAX_DIA_CANAL, cp.INTERVALO_H; n_hoje, ult = cp.envios_do_canal(p); maxp, n_proj = cp.MAX_DIA, cp.enviados_hoje(p)[0]
    except Exception: maxd, horas, n_hoje, ult, maxp, n_proj = 3, 4, 0, None, 5, 0
    PT = ZoneInfo("America/Los_Angeles"); cont = {dt.datetime.now(PT).date(): n_hoje}; proj = {dt.datetime.now(PT).date(): n_proj}; prev = ult  # proj = teto do projeto Google (todos os canais juntos)
    for i, x in enumerate(sorted(elegiveis, key=lambda x: x["instagram"]["t"])):
        t = dt.datetime.fromtimestamp(x["devido"]["t"], BR); motivo = "30 min depois do Instagram"
        if prev and prev + dt.timedelta(hours=horas) > t: t = prev + dt.timedelta(hours=horas); motivo = f"{horas} h depois do último envio"
        while cont.get(t.astimezone(PT).date(), 0) >= maxd or proj.get(t.astimezone(PT).date(), 0) >= maxp:
            d = t.astimezone(PT).date(); motivo = f"limite de {maxd} por dia no canal" if cont.get(d, 0) >= maxd else f"teto de {maxp} envios/dia do projeto do YouTube (todos os canais juntos)"
            t = max(t, dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0, 0), PT))
        cont[t.astimezone(PT).date()] = cont.get(t.astimezone(PT).date(), 0) + 1; proj[t.astimezone(PT).date()] = proj.get(t.astimezone(PT).date(), 0) + 1
        atraso = (agora - t).total_seconds() / 60
        x.update(devido=hora(t.astimezone(BR)), falta_min=round(-atraso), posicao=i + 1, motivo_espera=motivo,
                 estado="atrasado" if i == 0 and atraso > CROSS_TOLERANCIA_MIN else "agora" if i == 0 and atraso >= 0 else "esperando")
        prev = max(t, agora)

def cross_perfil(p, ev):
    """tudo do cross-post de um perfil, lido dos arquivos (e do cache da API): situação por plataforma, fila, Shorts no ar e histórico"""
    c = p.get("crosspost") or {}; pref = p.get("prefixo", p["pasta"]); base = ROOT / p["pasta"]; agora = dt.datetime.now(BR)
    desde = str(c.get("desde", "")); cache = _yt.get(pref) or {}; fila, no_ar, diario = [], [], []
    regs = {pl: cross_registros(p, pl) for pl in PLATS}
    if c and p.get("status") == "ativo":
        for f in jsons(base / "posts" / "05-publicado"):  # mesma regra do crosspost.py proximo: já no Instagram, a partir de `desde`
            it = ler_json(f) or {}; ident = it.get("id"); saida = base / "out" / str(ident)
            if str(it.get("horario", "")) < desde or not (saida / "post.json").exists(): continue
            pj = ler_json(saida / "post.json") or {}
            if pj.get("status") != "publicado" or not pj.get("timestamp"): continue
            ig = dt.datetime.strptime(pj["timestamp"], "%Y-%m-%dT%H:%M:%S%z"); devido = ig + dt.timedelta(minutes=CROSS_ATRASO_MIN)
            for pl in PLATS:
                if not (c.get(pl) or {}).get("ativo") or (saida / f"cross_{pl}.json").exists(): continue
                erro = ler_json(saida / f"cross_{pl}_erro.json") or {}; faltas = cross_faltas(p, pl, ev); atraso = (agora - devido).total_seconds() / 60
                est = "bloqueado" if faltas else "falhou" if erro else "esperando" if pl == "youtube" else "atrasado" if atraso > CROSS_ATRASADO_MIN else "agora" if atraso >= 0 else "esperando"  # YouTube: o estado real sai de _prever_youtube (regras do crosspost.py)
                fila.append({"perfil": p["handle"], "pref": pref, "plataforma": pl, "id": ident, "titulo": titulo(it.get("legenda")), "capa": it.get("capa"),
                             "instagram": hora(ig.astimezone(BR)), "devido": hora(devido.astimezone(BR)), "falta_min": round(-atraso), "estado": est,
                             "erro": erro.get("erro"), "tentativas": erro.get("tentativas"), "faltam_no_env": faltas})
    _prever_youtube(p, [x for x in fila if x["plataforma"] == "youtube"], agora)
    esperado = (c.get("youtube") or {}).get("privacidade", "public")
    shorts = {s["video_id"]: s for s in (cache.get("shorts") or [])}
    for pl in PLATS:
        for x in regs[pl]:
            t = dt.datetime.fromtimestamp(x["t"]).astimezone(); ident = x["id"]
            capa = base / "out" / ident / "cover.jpg"; txt = ler_json(base / "out" / ident / "cross" / "textos.json") or {}
            if pl == "youtube":
                s = shorts.get(x.get("video_id")) or {}; sit = s.get("situacao")
                tit = s.get("titulo") or ((txt.get("youtube") or {}).get("title")) or ident
                problema = ("sumiu do canal (removido)" if sit == "removido" else "o YouTube rejeitou o vídeo" if sit == "rejeitado" else
                            f"está {sit.replace('_', ' ')} e deveria estar público (projeto de API sem auditoria sai privado)" if sit in ("privado", "nao_listado") and esperado == "public" else None)
                no_ar.append({"perfil": p["handle"], "pref": pref, "plataforma": pl, "id": ident, "video_id": x.get("video_id"), "link": x.get("url"), "titulo": tit,
                              "capa": capa.relative_to(ROOT).as_posix() if capa.exists() else None, "quando": hora(t), "views": s.get("views"), "likes": s.get("likes"),
                              "comentarios": s.get("comentarios"), "situacao": sit, "problema": problema})
                diario.append({"t": t.timestamp(), "quando": hora(t), "pref": pref, "tipo": "cross", "texto": f'Short no YouTube: "{tit}" ({ident})', "link": x.get("url")})
            else:
                tit = (txt.get("tiktok") or {}).get("title_curto") or ident; priv = x.get("privacidade")
                no_ar.append({"perfil": p["handle"], "pref": pref, "plataforma": pl, "id": ident, "link": None, "titulo": tit, "quando": hora(t),
                              "capa": capa.relative_to(ROOT).as_posix() if capa.exists() else None, "situacao": "privado" if priv == "SELF_ONLY" else "enviado", "views": None})
                diario.append({"t": t.timestamp(), "quando": hora(t), "pref": pref, "tipo": "cross",
                               "texto": f'Enviado ao TikTok{" (só para mim)" if priv == "SELF_ONLY" else ""}: "{tit}" ({ident})'})
    for pl in PLATS:  # falha registrada pelo crosspost.py (cross_<plataforma>_erro.json) de edição que ainda não foi enviada
        for f in (base / "out").glob(f"*/cross_{pl}_erro.json"):
            if (f.parent / f"cross_{pl}.json").exists(): continue
            d = ler_json(f) or {}; t = f.stat().st_mtime
            diario.append({"t": t, "quando": hora(dt.datetime.fromtimestamp(t).astimezone()), "pref": pref, "tipo": "cross_falha",
                           "texto": f'{PLAT_NOME[pl]}: cross-post de {f.parent.name} falhou ({d.get("tentativas", 1)}ª tentativa): {str(d.get("erro", ""))[:140]}'})

    def plat(pl):
        cf = c.get(pl)
        if not cf: return {"estado": "sem_config", "texto": "sem canal ainda", "proximo": None, "ultimo": None}
        faltas = cross_faltas(p, pl, ev); pend = [x for x in fila if x["plataforma"] == pl]; ult = regs[pl][0] if regs[pl] else None
        d = {"ativo": bool(cf.get("ativo")), "faltam_no_env": faltas}
        if not cf.get("ativo"): d.update(estado="desligado", texto="desligado · " + ("faltam credenciais no .env" if faltas else "credenciais no .env"))
        elif faltas: d.update(estado="bloqueado", texto="ligado, mas faltam no .env: " + ", ".join(faltas))
        elif pl == "youtube":
            tk = cache.get("token")
            d.update(estado="erro" if tk == "erro" else "ligado", token=tk, texto="ligado · token " + ("ok" if tk == "ok" else "recusado" if tk == "erro" else "sendo conferido"))
            if tk == "erro": d["erro"] = cache.get("erro")
        else: d.update(estado="ligado", texto="ligado · credenciais no .env (o token só é testado ao postar)")  # renovar o token do TikTok troca o valor no .env: o painel não mexe
        d["proximo"] = {k: pend[0][k] for k in ("id", "titulo", "devido", "falta_min", "estado")} if pend else None
        d["ultimo"] = {"id": ult["id"], "url": ult.get("url"), "quando": hora(dt.datetime.fromtimestamp(ult["t"]).astimezone())} if ult else None
        return d
    return {"plats": {pl: plat(pl) for pl in PLATS}, "fila": fila, "no_ar": no_ar, "diario": diario}

def cross_revisar(cx):
    """o que do cross-post depende de uma pessoa: credencial que falta ou token que caiu, envio que falhou/atrasou, Short privado/removido"""
    r = [f'{PLAT_NOME[pl]}: {d["texto"]}' for pl, d in cx["plats"].items() if d["estado"] in ("erro", "bloqueado")]
    r += [f'cross-post de {x["id"]} ({PLAT_NOME[x["plataforma"]]}) {x["estado"]}' for x in cx["fila"] if x["estado"] in ("falhou", "atrasado")]
    return r + [f'Short {x["id"]}: {x["problema"]}' for x in cx["no_ar"] if x.get("problema")]

_hash_capa = {}
def _dhash(chave, abrir):
    if chave in _hash_capa: return _hash_capa[chave]
    h = None
    try:
        from PIL import Image
        g = list(abrir().convert("L").resize((9, 8)).getdata())
        h = [1 if g[r * 9 + c] > g[r * 9 + c + 1] else 0 for r in range(8) for c in range(8)]
    except Exception: pass
    _hash_capa[chave] = h; return h

def _capa_igual(local, url, limite=8):
    """Confere a capa do arquivo da fila com a miniatura do reel no Instagram (hash de 64 bits; capas certas dão 0–1, erradas 14+). Sem como comparar = False."""
    if not local or not url: return False
    try:
        import io
        from PIL import Image
        arq = ROOT / local
        a = _dhash(("l", str(arq), arq.stat().st_mtime), lambda: Image.open(arq))
        b = _dhash(("u", url.split("?")[0]), lambda: Image.open(io.BytesIO(requests.get(url, timeout=15).content)))
        return bool(a and b) and sum(x != y for x, y in zip(a, b)) <= limite
    except Exception: return False

def _min_conferir(p):
    return int(((p.get("conferir_postagem") or {}).get("minutos_depois_do_horario")) or 5)

def _no_instagram(titulo, capa, m):
    """'sim' = reel com o mesmo título E a mesma capa; 'capa' = título igual mas capa diferente; None = não achei (ou sem leitura do Instagram)."""
    if not m or not m.get("reels"): return None
    nt = lambda t: re.sub(r"\W+", " ", str(t or "").lower()).strip()
    ig = [r for r in m["reels"] if r.get("titulo") and nt(r["titulo"]) == nt(re.sub(r"\s+[⚠⏳✍].*$", "", str(titulo or "")))]
    if not ig: return None
    return "sim" if any(_capa_igual(capa, r.get("thumb")) for r in ig) else "capa"

def conferir_postagem_manual(p):
    """Perfil post_manual: 5 min (perfil.yaml → conferir_postagem) depois do horário, se o reel está no Instagram (título + capa), move o json de 04-aprovado para 05-publicado marcando postado_manual/conferido_em. Sem evidência, não mexe."""
    base = ROOT / p["pasta"]; apr = jsons(base / "posts" / "04-aprovado"); mov = []
    if not apr: return mov
    agora = dt.datetime.now(BR); lim = _min_conferir(p)
    pend = []
    for f in apr:
        it = ler_json(f) or {}
        try: q = quando_item(it)[0]
        except Exception: continue
        if q is None: continue
        if (agora - q).total_seconds() >= lim * 60: pend.append((f, it))
    if not pend: return mov
    m = _metricas.get(p.get("prefixo", p["pasta"]))
    if not m or time.time() - m.get("_t", 0) > 180: m = metricas(p, forcar=True)
    for f, it in pend:
        if _no_instagram(titulo(it.get("legenda")), it.get("capa"), m) != "sim": continue
        r = next((r for r in m["reels"] if r.get("titulo") and re.sub(r"\W+", " ", r["titulo"].lower()).strip() == re.sub(r"\W+", " ", titulo(it.get("legenda")).lower()).strip()), {})
        it.update({"postado_manual": True, "conferido_em": dt.datetime.now(BR).isoformat(timespec="seconds"), "conferido_por": "painel (titulo + capa no Instagram)", "permalink": r.get("link")})
        dest = base / "posts" / "05-publicado"; dest.mkdir(parents=True, exist_ok=True)
        (dest / f.name).write_text(json.dumps(it, ensure_ascii=False, indent=2), encoding="utf-8"); f.unlink(); mov.append(it.get("id"))
    return mov

def laco_conferir():
    while True:
        for p in cfg()["perfis"]:
            if p.get("status") == "ativo" and p.get("post_manual") and p.get("token_env"):
                try: conferir_postagem_manual(p)
                except Exception: pass
        time.sleep(60)

def rotina(p):
    """Produção por rotina externa (perfil.yaml → producao_rotina {hora, txt}): só mostra o texto; o painel não lê agendadores de terceiros."""
    r = p.get("producao_rotina")
    if not r: return None
    return {"txt": r.get("txt") or (f'rotina {r.get("hora")}' if r.get("hora") else "rotina externa"), "on": True, "alerta": None, "ultima": None}

def esperando():
    """Quadro 'quem está esperando você': desligado no kit (não lê conversas nem sessões de nenhum app)."""
    return []

def estado():
    c = cfg(); pad = c.get("padrao", {}); alvo = pad.get("fila_alvo", 3)
    agora = dt.datetime.now(BR); dms, dm_env = dm_ultimas()
    ts = tarefas(); ev = env_valores(); cross_fila, cross_no_ar = [], []
    post_ligado = next((t.get("ligada") for t in ts if t.get("nome") == "Post"), False)
    prod_ligada = next((t.get("ligada") for t in ts if t.get("nome") == "Producao"), False)
    perfis, producao, fila, no_ar, falhas, diario = [], [], [], [], [], []
    for p in c["perfis"]:
        pref = re.sub(r"\W", "", str(p.get("prefixo") or p["pasta"])); base = ROOT / p["pasta"]; posts = base / "posts"
        ativo = p.get("status") == "ativo"
        em = jsons(posts / "02-em-producao") if ativo else []; apr = jsons(posts / "04-aprovado") if ativo else []
        pub = jsons(posts / "05-publicado") if ativo else []; fal = jsons(base / "reviews" / "falhas") if ativo else []
        auto = ativo and bool(p.get("producao_auto")) and prod_ligada  # perfil.yaml → producao_auto + tarefa de produção ligada
        ids_fila = {(ler_json(f) or {}).get("id") for f in apr}
        vivo = False
        for f in em:
            it = ler_json(f) or {}; ed = it.get("id", f.stem); pasta = base / "out" / ed
            lg = logs_do(ed); ultimo = lg[-1] if lg else None; mexido = ultimo.stat().st_mtime if ultimo else 0
            try: inicio = _data(it.get("inicio"))  # "manual" ou texto qualquer não derruba o painel
            except (ValueError, TypeError): inicio = None  # edição aberta à mão ("inicio": "manual") não tem hora
            v = bool(ultimo) and time.time() - mexido < VIVO_S; vivo = vivo or v
            etapas = []
            for nome, arq in ETAPAS:
                ok = (nome == "voz" and p.get("voz") is None) or (nome == "fila" and ed in ids_fila) or (bool(arq) and (pasta / arq).exists())
                etapas.append({"nome": nome, "ok": ok})
            producao.append({"perfil": p["handle"], "pref": pref, "id": ed, "tema": it.get("tema", ""), "vivo": v,
                             "inicio": hora(inicio) if inicio else None,
                             "minutos": round((agora - inicio).total_seconds() / 60) if inicio else None,
                             "parado_min": round((time.time() - mexido) / 60) if ultimo else None,
                             "log": ultimo.name if ultimo else None, "etapas": etapas})
        for f in apr:
            it = ler_json(f) or {}; quando, nota_h = quando_item(it)
            fila.append({"perfil": p["handle"], "pref": pref, "arq": f.stem, "id": it.get("id"), "titulo": titulo(it.get("legenda")) + (f"  ✍ {nota_h}" if nota_h else ""), "qa": it.get("qa"),
                         "quando": hora(quando) if quando else None, "capa": it.get("capa"),
                         "falta_min": round((quando - agora).total_seconds() / 60) if quando else None})
            q = ler_json(base / "out" / str(it.get("id")) / "qa.json") or {}
            diario.append({"t": de_mtime(f).timestamp(), "quando": hora(de_mtime(f)), "pref": pref, "tipo": "fila",
                           "texto": f'{it.get("id")} aprovado no QA ({q.get("media_ponderada", it.get("qa"))}) e entrou na fila para {hora(quando)["br"] if quando else "?"}'})
        # no ar: a verdade é o Instagram; sem métricas carregadas, usa os registros locais
        m = _metricas.get(pref) if ativo else None
        if m and m.get("reels") is not None:
            for r in m["reels"]:
                no_ar.append({"perfil": p["handle"], "pref": pref, **r})
            links = {r["link"] for r in m["reels"]}
            for f in pub:
                it = ler_json(f) or {}; pj = ler_json(base / "out" / str(it.get("id")) / "post.json") or {}
                if pj.get("permalink") and pj["permalink"] not in links:
                    no_ar.append({"perfil": p["handle"], "pref": pref, "id": it.get("id"), "titulo": titulo(it.get("legenda")),
                                  "capa": it.get("capa"), "qa": it.get("qa"), "link": pj["permalink"], "removido": True,
                                  "quando": hora(dt.datetime.strptime(pj["timestamp"], "%Y-%m-%dT%H:%M:%S%z")) if pj.get("timestamp") else None})
        else:
            for f in pub:
                it = ler_json(f) or {}; pj = ler_json(base / "out" / str(it.get("id")) / "post.json") or {}
                ts_ = dt.datetime.strptime(pj["timestamp"], "%Y-%m-%dT%H:%M:%S%z") if pj.get("timestamp") else (_data(it.get("conferido_em")) if it.get("conferido_em") else None)
                no_ar.append({"perfil": p["handle"], "pref": pref, "id": it.get("id"), "titulo": titulo(it.get("legenda")),
                              "capa": it.get("capa"), "qa": it.get("qa"), "link": pj.get("permalink") or it.get("permalink"), "quando": hora(ts_) if ts_ else None})
        for r in [x for x in no_ar if x["pref"] == pref and x.get("quando") and not x.get("removido")]:
            diario.append({"t": r["quando"]["t"], "quando": r["quando"], "pref": pref, "tipo": "post",
                           "texto": f'Publicado: "{r["titulo"]}"' + (f' ({r["id"]})' if r.get("id") else ""), "link": r.get("link")})
        # edição reprovada que depois foi salva (refeita e aprovada, na reserva, na fila ou no ar) não conta como reprovação
        salvas = {(ler_json(f) or {}).get("id") for f in apr + pub + (jsons(posts / "03-reserva") if ativo else [])}
        f24, vistos = 0, set()
        for f in fal:
            it = ler_json(f) or {}; ed = it.get("id", f.stem); fj = ler_json(base / "out" / ed / "fail.json") or {}
            if not it.get("fail") or ed in vistos: continue  # item de fila antigo guardado ali ou edição repetida: não é reprovação
            vistos.add(ed)
            lg = (it.get("log") or "").replace("\\", "/"); q = de_mtime(f)
            manual = bool(fj.get("descarte_manual")) or "descarte manual" in str(fj.get("motivo", "")).lower()  # descarte pedido pela pessoa, não reprovação do sistema
            if time.time() - q.timestamp() < 86400 and not manual and ed not in salvas: f24 += 1
            falhas.append({"perfil": p["handle"], "pref": pref, "id": ed, "etapa": fj.get("etapa"), "motivo": fj.get("motivo") or "sem fail.json",
                           "minutos": it.get("minutos"), "log": Path(lg).name if lg else None, "quando": hora(q)})
            diario.append({"t": q.timestamp(), "quando": hora(q), "pref": pref, "tipo": "falha",
                           "texto": f'{ed} reprovado na etapa {fj.get("etapa") or "?"}: saiu da fila', "log": Path(lg).name if lg else None})
        # perfil de postagem manual: o arquivo fica em 04-aprovado depois que a pessoa posta; só sai da fila quando o Instagram tem um reel com o mesmo título E a mesma capa
        if p.get("post_manual"):
            for x in [x for x in fila if x["pref"] == pref]:
                r = _no_instagram(x.get("titulo"), x.get("capa"), m)
                if r == "sim": fila.remove(x)
                elif r == "capa": x["titulo"] = f'{x["titulo"]}  ⚠ título já está no Instagram, mas a capa não bate: confira'
                elif x.get("falta_min") is not None and x["falta_min"] < -_min_conferir(p):
                    x["titulo"] = f'{x["titulo"]}  ⏳ a conferir: passou do horário e não achei no Instagram' if m and m.get("reels") is not None else f'{x["titulo"]}  ⏳ a conferir: não consegui ler o Instagram'
        # o que está de fato agendado (arquivos de 04-aprovado) e a última publicação real (post.json); os horários fixos do perfil.yaml são só o padrão
        mine = [x for x in fila if x["pref"] == pref and x["quando"]]
        agend = sorted(mine, key=lambda x: x["quando"]["t"])
        ult_t = max([r["quando"]["t"] for r in no_ar if r["pref"] == pref and r.get("quando") and not r.get("removido")] +
                    [dt.datetime.strptime(pj_["timestamp"], "%Y-%m-%dT%H:%M:%S%z").timestamp() for pj_ in
                     (ler_json(base / "out" / str((ler_json(f) or {}).get("id")) / "post.json") or {} for f in pub) if pj_.get("timestamp")] or [0]) if ativo else 0
        # horários (hoje em NY) e o próximo
        prox = None; hoje = dt.datetime.now(NY).date()
        for dia in (0, 1):
            d = hoje + dt.timedelta(days=dia)
            for h in p.get("horarios", []):
                t = dt.datetime.combine(d, dt.time.fromisoformat(h), NY)
                if t > agora and (prox is None or t < prox): prox = t
        cod, rotulo, motivo, motivos = situacao(p, pad, apr, vivo, f24, auto, post_ligado, bool(p.get("producao_auto")) and not prod_ligada)
        dm = dms.get(p["handle"], {}); ofe = p.get("oferta") or {}
        mt = _metricas.get(pref) or {}
        cx = cross_perfil(p, ev); cross_fila += cx["fila"]; cross_no_ar += cx["no_ar"]; diario += cx["diario"]
        qd = quadro(p, cod, apr, vivo, auto, post_ligado, prod_ligada, pad, motivos, cx) if ativo else {"agora": motivo, "depois": "", "voce": []}
        perfis.append({"handle": p.get("handle", p["pasta"]), "pref": pref, "pasta": p["pasta"], "nicho": p.get("nicho", ""), "cores": cores_do(p),
                       "ativo": ativo, "situacao": cod, "rotulo": rotulo, "motivo": motivo, "chaves": chaves(p, post_ligado, prod_ligada, cx, bool(pad.get("pausado")), rotina(p)) if ativo else [], "agora": qd["agora"], "depois": qd["depois"], "voce": qd["voce"],
                       "modo": dict(zip(("cod", "texto"), modo(cod, auto, post_ligado))),
                       "revisar": [t for n, t in motivos if n in ("crit", "warn")] + cross_revisar(cx) + ([rotina(p)["alerta"]] if rotina(p) and rotina(p)["alerta"] else []),  # o que depende de alguém
                       "motivos": [{"nivel": n, "texto": t} for n, t in motivos], "marcos": marcos(p, apr, auto) if ativo else [],
                       "fila": len(apr), "alvo": p.get("fila_alvo", alvo), "em_producao": len(em), "publicados": len(pub), "falhas": len(fal), "falhas_24h": f24,
                       "producao_auto": auto,
                       "post_manual": bool(p.get("post_manual")),
                       "horarios": [hora(dt.datetime.combine(hoje, dt.time.fromisoformat(h), NY)) for h in p.get("horarios", [])],
                       "proximo": hora(prox) if prox and ativo else None,   # próximo horário FIXO do perfil (padrão)
                       "proximo_fila": {"id": agend[0]["id"], "quando": agend[0]["quando"], "falta_min": agend[0]["falta_min"]} if agend else None,   # próximo vídeo agendado de verdade
                       "agendados": [{"id": x["id"], "quando": x["quando"], "falta_min": x["falta_min"]} for x in agend],
                       "ultimo_post": hora(dt.datetime.fromtimestamp(ult_t).astimezone()) if ult_t else None,
                       "seguidores": (mt.get("conta") or {}).get("followers_count"), "views7d": (mt.get("conta7d") or {}).get("views"),
                       "tem_meta": bool(p.get("token_env")) and ativo and not meta.credenciais(p)[2], "cross": cx["plats"],
                       "ref_img": next((f.relative_to(ROOT).as_posix() for f in sorted((base / "assets" / "reference").glob("*")) if f.suffix.lower() in (".jpg", ".jpeg", ".png")), None),
                       "dm": {"ativa": bool(ofe.get("dm_ativa")), "palavra": ofe.get("palavra"), "motivo": dm.get("motivo_sem_envio"),
                              "ultima": hora(dt.datetime.fromisoformat(dm["em"])) if dm.get("em") else None}})
    # sessões de produção (início de cada log) e DMs enviadas
    for f in sorted(LOGS.glob("*_*.log")) if LOGS.exists() else []:
        m = re.match(r"([a-z]+)-(\d+[\w-]*)_(\d{8})_(\d{4})\.log", f.name)
        if not m: continue
        ini = dt.datetime.strptime(m.group(3) + m.group(4), "%Y%m%d%H%M").replace(tzinfo=BR)
        diario.append({"t": ini.timestamp(), "quando": hora(ini), "pref": m.group(1), "tipo": "sessao",
                       "texto": f'Sessão de produção aberta para {m.group(1)}-{m.group(2).split("_")[0]}', "log": f.name})
    for ev, cm in dm_env:
        q = dt.datetime.fromisoformat(ev["em"])
        diario.append({"t": q.timestamp(), "quando": hora(q), "pref": next((p["pref"] for p in perfis if p["handle"] == ev["perfil"]), ""),
                       "tipo": "dm", "texto": f'DM enviada para quem comentou {ev.get("palavra")}'})
    limite = time.time() - DIARIO_H * 3600
    diario = sorted([d for d in diario if d["t"] >= limite], key=lambda d: -d["t"])
    recentes = [{"nome": f.name, "quando": hora(de_mtime(f))} for f in sorted(LOGS.glob("*_*.log"), key=lambda f: -f.stat().st_mtime)[:12]] if LOGS.exists() else []
    fila.sort(key=lambda x: (x["quando"] or {}).get("t", 0))
    no_ar.sort(key=lambda x: (x.get("quando") or {}).get("t", 0), reverse=True)
    cross_fila.sort(key=lambda x: x["devido"]["t"]); cross_no_ar.sort(key=lambda x: x["quando"]["t"], reverse=True)
    return {"agora": hora(agora), "pausado": bool(pad.get("pausado")), "producao_hora": pad.get("producao"),
            "max_noite": pad.get("producao_max_por_noite"), "alvo": alvo, "perfis": perfis, "producao": producao, "fila": fila,
            "no_ar": no_ar, "falhas": falhas, "tarefas": ts, "logs": recentes, "diario": diario[:60],
            "cross_fila": cross_fila, "cross_no_ar": cross_no_ar, "esperando": esperando()}

# ---------- alertas: notificação do Windows quando um perfil para ou uma edição reprova ----------
APP_TOAST = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"  # AppID do PowerShell, já registrado no Windows
PARADOS, RODANDO = ("parado", "pausado"), ("rodando", "atencao", "produzindo")

def notificar(titulo_, texto, pagina="agora"):
    """toast do Windows; clicar abre o painel na página indicada"""
    esc = lambda s: html.escape(str(s), quote=True)
    xml = (f'<toast activationType="protocol" launch="http://127.0.0.1:{PORTA}/#{pagina}" scenario="reminder">'
           f'<visual><binding template="ToastGeneric"><text>{esc(titulo_)}</text><text>{esc(texto)}</text>'
           f'<text placement="attribution">Painel de Produção</text></binding></visual>'
           f'<actions><action content="Abrir o painel" activationType="protocol" arguments="http://127.0.0.1:{PORTA}/#{pagina}"/>'
           f'<action content="Fechar" activationType="system" arguments="dismiss"/></actions></toast>')
    ps = ("$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"
          "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
          "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
          f"$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml(@'\n{xml}\n'@);"
          f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{APP_TOAST}').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    cod = base64.b64encode(ps.encode("utf-16-le")).decode()
    r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", cod], capture_output=True, text=True, timeout=30, creationflags=SEM_JANELA)
    return r.returncode == 0

def conferir_alertas(e, visto):
    """compara o estado com o que já foi avisado; devolve [(título, texto, página)] e atualiza `visto`"""
    novos = []
    for p in e["perfis"]:
        if not p["ativo"]: continue
        antes = visto["situacao"].get(p["pref"])
        if p["situacao"] in PARADOS and antes in RODANDO:  # só quem estava rodando; perfil montando não "para"
            novos.append((f'{p["handle"]} parou', p["motivo"], "agora"))
        visto["situacao"][p["pref"]] = p["situacao"]
    for f in e["falhas"]:
        chave = f'{f["pref"]}/{f["id"]}'
        if chave in visto["falhas"]: continue
        visto["falhas"].append(chave)
        novos.append((f'{f["perfil"]}: {f["id"]} reprovado',
                      f'Etapa {f["etapa"] or "?"}: {f["motivo"]}'[:200], "historico"))
    # cross-post: token que caiu, envio que falhou ou atrasou, Short que ficou privado/removido (cada um avisa uma vez)
    cr = visto.setdefault("cross", [])
    def uma_vez(chave):
        if chave in cr: return False
        cr.append(chave); return True
    for p in e["perfis"]:
        for pl, d in (p.get("cross") or {}).items():
            chave = f'token:{p["pref"]}:{pl}'
            if d.get("estado") == "erro":
                if uma_vez(chave): novos.append((f'{PLAT_NOME[pl]} do {p["handle"]}: token caiu', (d.get("erro") or d.get("texto") or "")[:200] + " Rode crosspost.py auth-youtube.", "agora"))
            elif chave in cr: cr.remove(chave)  # voltou a funcionar: se cair de novo, avisa de novo
    for x in e.get("cross_fila", []):
        if x["estado"] == "falhou" and uma_vez(f'falha:{x["pref"]}:{x["id"]}:{x["plataforma"]}'):
            novos.append((f'{x["perfil"]}: cross-post de {x["id"]} falhou', f'{PLAT_NOME[x["plataforma"]]}: {x.get("erro") or "sem detalhe"}'[:200], "videos"))
        elif x["estado"] == "atrasado" and uma_vez(f'atraso:{x["pref"]}:{x["id"]}:{x["plataforma"]}'):
            novos.append((f'{x["perfil"]}: cross-post de {x["id"]} atrasado', f'{PLAT_NOME[x["plataforma"]]} devia sair às {x["devido"]["br"][-5:]} e nada foi enviado nem registrado como erro.', "videos"))
    for x in e.get("cross_no_ar", []):
        if x.get("problema") and uma_vez(f'short:{x["pref"]}:{x.get("video_id") or x["id"]}:{x["situacao"]}'):
            novos.append((f'{x["perfil"]}: Short {x["situacao"].replace("_", " ")}', f'{x["titulo"]}: {x["problema"]}'[:200], "videos"))
    return novos

def laco_alertas():
    primeira = not ALERTAS_F.exists()  # 1ª vez: só registra o que já existe, sem avisar o passado
    visto = ler_json(ALERTAS_F) or {"situacao": {}, "falhas": []}
    while True:
        try:
            novos = conferir_alertas(estado(), visto)
            if not primeira:
                for t, x, pg in novos[:5]: notificar(t, x, pg)        # limite para não inundar a tela
                if len(novos) > 5: notificar(f"+{len(novos) - 5} alertas", "Veja o Histórico no painel", "historico")
            primeira = False
            LOGS.mkdir(exist_ok=True)
            ALERTAS_F.write_text(json.dumps(visto, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception: pass
        time.sleep(ALERTAS_S)

def ler_log(nome, tail):
    if not re.fullmatch(r"[\w.\-]+\.log", nome or ""): return None
    f = LOGS / nome
    if not f.exists(): return None
    linhas = f.read_text(encoding="utf-8", errors="replace").splitlines()
    m = re.search(r"sessão ([0-9a-f-]{36})", linhas[0]) if linhas else None
    return {"nome": nome, "linhas": linhas[-tail:], "total": len(linhas), "sessao": m.group(1) if m else None,
            "fim": any(l.startswith("=== FIM") for l in linhas[-60:]),
            "vivo": time.time() - f.stat().st_mtime < VIVO_S, "mexido": hora(de_mtime(f))}

class Painel(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def enviar(self, corpo, tipo, codigo=200):
        self.send_response(codigo); self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(corpo)

    def json(self, d, codigo=200):
        self.enviar(json.dumps(d, ensure_ascii=False).encode(), "application/json; charset=utf-8", codigo)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        try:
            estaticos = {"/": "index.html", "/index.html": "index.html"}
            if u.path in estaticos:
                f = AQUI / estaticos[u.path]
                tipo = {".html": "text/html", ".css": "text/css", ".svg": "image/svg+xml", ".js": "text/javascript"}[f.suffix] + "; charset=utf-8"
                return self.enviar(f.read_bytes(), tipo)
            if u.path == "/api/estado": return self.json(estado())
            if u.path == "/api/log":
                d = ler_log(q.get("nome", [""])[0], min(int(q.get("tail", ["300"])[0]), 2000))
                return self.json(d, 200 if d else 404)
            if u.path == "/api/metricas":
                pref = q.get("perfil", [""])[0]
                p = next((x for x in cfg()["perfis"] if x.get("prefixo") == pref), None)
                if not p: return self.json({"erro": "perfil não encontrado"}, 404)
                if p.get("status") != "ativo" or not p.get("token_env"): return self.json({"perfil": p["handle"], "sem_meta": True, "fora": True})
                d = metricas(p, forcar=q.get("forcar", ["0"])[0] == "1")
                return self.json({k: v for k, v in d.items() if k != "_t"} | {"idade_min": round((time.time() - d["_t"]) / 60)})
            if u.path == "/api/youtube":
                pref = q.get("perfil", [""])[0]
                p = next((x for x in cfg()["perfis"] if x.get("prefixo") == pref), None)
                if not p: return self.json({"erro": "perfil não encontrado"}, 404)
                if p.get("status") != "ativo" or not (p.get("crosspost") or {}).get("youtube"): return self.json({"perfil": p["handle"], "sem_youtube": True})
                d = youtube(p, forcar=q.get("forcar", ["0"])[0] == "1")
                return self.json({k: v for k, v in d.items() if k != "_t"} | {"idade_min": round((time.time() - d["_t"]) / 60)})
            if u.path == "/video":  # só out/<id>/video.mp4 de dentro do projeto, com Range (o iPhone exige para tocar)
                f = (ROOT / q.get("p", [""])[0]).resolve()
                if ROOT in f.parents and f.name == "video.mp4" and f.exists():
                    tam = f.stat().st_size; ini, fim = 0, tam - 1
                    m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
                    if m:
                        if m.group(1): ini = int(m.group(1))
                        if m.group(2): fim = min(int(m.group(2)), tam - 1)
                        if not m.group(1) and m.group(2): ini, fim = max(0, tam - int(m.group(2))), tam - 1
                    self.send_response(206 if m else 200)
                    self.send_header("Content-Type", "video/mp4"); self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(fim - ini + 1))
                    if m: self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
                    self.end_headers()
                    with open(f, "rb") as fh:
                        fh.seek(ini); resta = fim - ini + 1
                        while resta > 0:
                            b = fh.read(min(1 << 20, resta))
                            if not b: break
                            self.wfile.write(b); resta -= len(b)
                    return
            if u.path == "/midia":  # só imagens de dentro do projeto (capas)
                f = (ROOT / q.get("p", [""])[0]).resolve()
                if ROOT in f.parents and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.exists():
                    return self.enviar(f.read_bytes(), mimetypes.guess_type(f.name)[0] or "image/jpeg")
            self.enviar(b"nao encontrado", "text/plain", 404)
        except Exception as e:
            self.json({"erro": str(e)}, 500)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sem-abrir", action="store_true"); ap.add_argument("--porta", type=int, default=PORTA); ap.add_argument("--so-local", action="store_true", help="só este PC (por padrão aceita outros aparelhos da mesma rede, ex.: outro computador/celular)"); ap.add_argument("--rede", action="store_true", help="(padrão)")
    a = ap.parse_args()
    try: srv = ThreadingHTTPServer(("127.0.0.1" if a.so_local else "0.0.0.0", a.porta), Painel)
    except OSError:  # já está rodando: só abre
        if not a.sem_abrir: webbrowser.open(f"http://127.0.0.1:{a.porta}")
        sys.exit(f"painel já está no ar em http://127.0.0.1:{a.porta}")
    print(f"Painel de Produção: http://127.0.0.1:{a.porta}  (Ctrl+C para fechar)")
    threading.Thread(target=tarefas, daemon=True).start()
    threading.Thread(target=laco_metricas, daemon=True).start()
    threading.Thread(target=laco_cross, daemon=True).start()
    threading.Thread(target=laco_drive, daemon=True).start()
    threading.Thread(target=laco_conferir, daemon=True).start()
    threading.Thread(target=laco_alertas, daemon=True).start()
    if not a.sem_abrir: threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{a.porta}")).start()
    srv.serve_forever()
