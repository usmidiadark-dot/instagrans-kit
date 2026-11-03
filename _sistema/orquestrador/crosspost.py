"""Cross-post (automacao.md §10): o reel do Instagram também vai para YouTube Shorts e TikTok, em modo de teste (perfil.yaml → crosspost).
Uso (na raiz do projeto):
  python _sistema/orquestrador/crosspost.py preparar <id|item.json> [--perfil X]   corta o vídeo sem a chamada para comentar e monta títulos/legendas (cross/)
  python _sistema/orquestrador/crosspost.py publicar <id> [--perfil X] [--so youtube|tiktok] [--dry-run]
  python _sistema/orquestrador/crosspost.py proximo  [--perfil X] [--dry-run]      posta o que já saiu no Instagram há ≥ 30 min e ainda não foi para as outras redes
  python _sistema/orquestrador/crosspost.py checar   [--perfil X]                   confere credenciais (só leitura)
  python _sistema/orquestrador/crosspost.py refazer-thumbs [<id>] [--perfil X]       gera a thumb 16:9 e aplica nos Shorts já enviados
  python _sistema/orquestrador/crosspost.py auth-youtube [--perfil X]               consentimento OAuth no navegador; imprime o refresh token para o .env
  python _sistema/orquestrador/crosspost.py auth-tiktok  [--perfil X] [--url-retorno URL]   idem, com o código colado
Por que um vídeo à parte: o vídeo do Instagram termina com a chamada falada "Comment PALAVRA and I'll send you…" + card (DM automática só existe lá) ou com o card de SEGUIR (script.seguir); aqui o corte tira os dois.
Aqui o vídeo é CORTADO logo depois da última palavra da narração (words_sem_cta.json quando existe), sem re-renderizar.
Config: perfil.yaml → crosspost: {desde, youtube: {ativo, ...}, tiktok: {ativo, ...}}. Segredos só no .env."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, datetime as dt, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo
import requests, yaml
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[2]
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
load_dotenv(ROOT / ".env")
CFG = carrega(ROOT)
TZ = ZoneInfo(CFG["padrao"].get("fuso", "America/New_York"))
ATRASO_MIN = 30          # depois do Instagram (§10: até 1 h de diferença)
HOLD_S = 0.7             # respiro depois da última palavra da narração
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"

def perfis():
    return [p for p in CFG["perfis"] if p.get("status") == "ativo" and p.get("crosspost")]

def acha(chave):
    for p in CFG["perfis"]:
        if chave in (p.get("prefixo"), p.get("handle"), p.get("pasta")): return p
    sys.exit(f"perfil não encontrado: {chave}")

def env(nome): return os.getenv(nome, "").strip()

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode: raise RuntimeError(f"{cmd[0]} falhou: {r.stderr[-500:]}")
    return r.stdout

# ---------- preparar: vídeo sem chamada + textos ----------
def item_por_id(p, ident):
    for pasta in ("05-publicado", "04-aprovado"):
        for f in sorted((ROOT / p["pasta"] / "posts" / pasta).glob("*.json")):
            it = json.loads(f.read_text(encoding="utf-8"))
            if it.get("id") == ident: return f, it
    sys.exit(f"{ident}: sem item em 04-aprovado/05-publicado")

def duracao(video):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)).strip())

def corte_s(saida, video):
    """Segundo do corte, sempre antes do card/chamada final. Dois casos, decididos pelo vídeo que está na fila:
    - render novo (duração = script.duration_s): a chamada falada "Comment PALAVRA…" vem depois da narração; corta HOLD_S depois da
      última palavra original (words_sem_cta.json), nunca depois de 0,3 s antes do "Comment";
    - render antigo (duração menor que a do script): o vídeo só tem o card fixo, que entra 0,12 s
      depois da última palavra; corta 0,1 s depois dela, com fade curto."""
    sem = saida / "words_sem_cta.json"; script = json.loads((saida / "script.json").read_text(encoding="utf-8"))
    novo = abs(duracao(video) - float(script["duration_s"])) < 0.5
    ref = sem if sem.exists() else saida / "words.json"
    if not novo and sem.exists(): ref = sem
    words = json.loads(ref.read_text(encoding="utf-8")); fim = words[-1]["end"]
    if script.get("seguir"):   # words_sem_cta.json é anterior aos cortes/ajustes da voz (018: 32,8 s contra 33,0 s): vale o words.json atual, que já termina no fato
        fim = json.loads((saida / "words.json").read_text(encoding="utf-8"))[-1]["end"]
        return round(fim + 0.1, 2), 0.1
    if not novo: return round(fim + 0.1, 2), 0.1
    corte = fim + HOLD_S
    if sem.exists():
        cta = [w for w in json.loads((saida / "words.json").read_text(encoding="utf-8")) if w["w"].lower().startswith("comment")]
        if cta: corte = min(corte, cta[-1]["start"] - 0.3)
    return round(corte, 2), 0.45

def limpa_legenda(leg):
    linhas = [l for l in leg.strip().split("\n") if not re.search(r'(?i:comment)\s+"[A-Z]{3,7}"', l) and not re.match(r"^\W*comment\b", l, re.I)]  # tira a chamada do IG onde estiver (26/10/2026: no corpo, frase variada)
    return [l for l in linhas if not re.search(r"the long one gets stranger|more like this in|link in bio", l, re.I)]

def _tags6(p, item, tags):
    """6 hashtags (3 fixas do perfil + 3 variáveis) para o YouTube, mesmo quando a legenda do Instagram é antiga (com menos hashtags)."""
    import hashtags as H
    cfg = H.config(p)
    if not cfg or (len(tags) == 6 and [t.lower() for t in tags[:3]] == [f.lower() for f in cfg["fixas"]]): return tags
    return H.separa(H.aplica("x", p, item["id"], item.get("horario")))[1] or tags

def _licao_yt(p, item, titulo, linhas):
    """Corpo da descrição no molde 'lição rápida' (_sistema/legenda.md): exatamente 3 linhas '1. 2. 3.'. Legenda antiga em parágrafos corridos é reescrita com `claude -p`
    só com os fatos que já estão no texto (guardado em out/<id>/cross/licao_yt.json, não gasta de novo). Se não der, devolve as linhas como estão e o confere_yt reprova o envio."""
    if len(linhas) == 3 and all(l.startswith(f"{i}. ") for i, l in enumerate(linhas, 1)): return linhas
    cross = ROOT / p["pasta"] / "out" / item["id"] / "cross"; f = cross / "licao_yt.json"; chave = json.dumps([titulo, linhas], ensure_ascii=False)
    try:
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("chave") == chave: return d["linhas"]
        pedido = ("Reescreva esta legenda de YouTube Short no molde 'lição rápida': EXATAMENTE 3 linhas numeradas, cada uma começando com '1. ', '2. ', '3. '.\n"
                  "1 = a situação; 2 = o fato ou número; 3 = o que levar/fazer. Cada linha até ~90 caracteres, 1 frase curta, mesmo idioma e mesmo tom (minúsculas se o original for). "
                  "A linha 1 NÃO pode repetir nem parafrasear o título (o título já está no topo): comece direto pela situação/causa. Mantenha os NÚMEROS e termos do texto (ex.: valores, unidades, nomes). Use SÓ fatos, números e nomes que já estão no texto; não invente nada; tire pontes como 'o que não coube no vídeo'. No máximo 3 emojis no total.\n"
                  'Responda SÓ com JSON: {"linhas": ["1. ...", "2. ...", "3. ..."]}.\n\nTÍTULO: ' + titulo + "\nTEXTO:\n" + "\n".join(linhas))
        r = subprocess.run([shutil.which("claude") or "claude", "-p", "--model", "sonnet"], input=pedido, capture_output=True, text=True, encoding="utf-8", timeout=300)
        out = [str(x).strip() for x in json.loads(r.stdout[r.stdout.index("{"): r.stdout.rindex("}") + 1])["linhas"]]
        assert len(out) == 3 and all(l.startswith(f"{i}. ") and len(l) <= 120 for i, l in enumerate(out, 1)), out
        cross.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps({"chave": chave, "linhas": out}, ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    except Exception as e:
        print(f"{item['id']}: descrição do YouTube não reescrita no molde ({str(e)[:140]})"); return linhas

def textos(p, item):
    linhas = limpa_legenda(item["legenda"])
    tags = [t for l in linhas for t in re.findall(r"#\w+", l)]
    corpo = [l for l in linhas if not re.fullmatch(r"(\s*#\w+)+\s*", l)]
    titulo = corpo[0].strip() if corpo else item["id"]
    link = (p.get("oferta") or {}).get("link_bio", "")
    yt_titulo = titulo if len(titulo) <= 100 else titulo[:99].rstrip() + "…"  # sem " #Shorts" no título (28/10/2026): o YouTube já detecta Short; a hashtag vai no fim da descrição
    yt_corpo = [l for l in corpo if not re.match(r"(?i)^\W*the part we cut", l)]  # "the part we cut" aponta para a versão longa do Instagram: no YouTube ninguém viu essa versão
    # gancho no topo, parágrafos separados (formato aprovado) + hashtags no fim (antes um comentário engolia hashtags e link). Sem link: o canal só mostra o Instagram
    # 29/10/2026: sem a linha do título repetida e sem linhas em branco a mais (a legenda do IG já tem linha vazia entre os itens)
    yt_corpo = [l.strip() for l in yt_corpo[1:] if l.strip()]
    # o molde do YouTube é do sistema, igual para todo perfil, venha a legenda do Instagram como vier
    yt_corpo = _licao_yt(p, item, titulo, yt_corpo); tags_yt = _tags6(p, item, tags)
    descr = "\n\n".join(yt_corpo) + ("\n\n" if yt_corpo else "") + " ".join(dict.fromkeys(tags_yt + ["#Shorts"]))
    tt = "\n".join(corpo) + (f"\n\nmore: {link}" if link else "") + "\n" + " ".join(dict.fromkeys(tags + ["#fyp"]))
    return {"youtube": {"title": yt_titulo, "description": descr[:4900], "tags": [t.lstrip("#") for t in tags_yt][:15]},
            "tiktok": {"caption": tt[:2200], "title_curto": titulo[:150]}}

def preparar(p, ident):
    fonte, item = item_por_id(p, ident)
    saida = ROOT / p["pasta"] / "out" / ident; cross = saida / "cross"; cross.mkdir(exist_ok=True)
    video = ROOT / item["video"]; corte, fade = corte_s(saida, video)
    alvo = cross / "video.mp4"
    sh("ffmpeg", "-v", "error", "-y", "-i", str(video), "-t", str(corte), "-af", f"afade=t=out:st={corte - fade}:d={fade}",
       "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(alvo))
    capa = ROOT / item["capa"] if item.get("capa") else None
    t = textos(p, item)
    try: gerar_thumb(p, ident)
    except Exception as e: print(f"{ident}: thumb 16:9 não gerada ({str(e)[-200:]}); usa a capa do reel")
    (cross / "textos.json").write_text(json.dumps({**t, "id": ident, "corte_s": corte, "capa": str(capa) if capa and capa.exists() else None}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ident}: vídeo sem chamada ({corte:.1f} s) em {alvo.relative_to(ROOT)}\n  YouTube: {t['youtube']['title']}\n  TikTok: {t['tiktok']['caption'][:90]!r}…")
    return cross

# ---------- YouTube Shorts ----------
def gerar_thumb(p, ident):
    """Thumb 16:9 (1280×720) do YouTube, no mesmo padrão da capa do reel (perfil.yaml → crosspost.youtube.thumb: {composicao, remotion}).
    A arte vem do cover.jpg da edição (remotion/src/<perfil>/ThumbYT.tsx); sai em out/<id>/cross/thumb.jpg (< 2 MB, limite do YouTube). Devolve o caminho ou None."""
    cfg = yt_conf(p).get("thumb")
    if not cfg: return None
    saida = ROOT / p["pasta"] / "out" / ident; capa = saida / "cover.jpg"; script = json.loads((saida / "script.json").read_text(encoding="utf-8")).get("capa") or {}
    if not capa.exists(): return None
    from PIL import Image
    im = Image.open(capa).convert("RGB"); fundo = "rgb(%d,%d,%d)" % im.getpixel((30, 1800))  # cor do fundo da capa (faixa sem texto)
    rem = ROOT / cfg["remotion"]; (rem / "public" / "yt").mkdir(parents=True, exist_ok=True)
    shutil.copy(capa, rem / "public" / "yt" / f"{ident}.jpg")
    props = {"capa": f"yt/{ident}.jpg", "fundo": fundo, "titulo": script.get("titulo") or script.get("linha1"), "linha2": script.get("linha2"), "selo": script.get("selo"), "apoio": script.get("apoio")}
    cross = saida / "cross"; cross.mkdir(exist_ok=True); pj = cross / "thumb_props.json"; pj.write_text(json.dumps({k: v for k, v in props.items() if v}, ensure_ascii=False), encoding="utf-8")
    png = cross / "thumb.png"; npx = shutil.which("npx") or "npx"
    subprocess.run([npx, "remotion", "still", "src/index.ts", cfg["composicao"], str(png), f"--props={pj}", "--log=error", f"--port={3200 + sum(map(ord, ident)) % 600}"],
                   cwd=rem, check=True, shell=(sys.platform == "win32"), capture_output=True, text=True)
    jpg = cross / "thumb.jpg"; Image.open(png).convert("RGB").save(jpg, quality=92); png.unlink(missing_ok=True)
    return jpg

def yt_conf(p): return p["crosspost"].get("youtube") or {}
NOMES_IDIOMA = {"pt-BR": "português do Brasil", "en": "inglês", "es": "espanhol neutro", "id": "indonésio", "de": "alemão", "hi": "hindi em devanágari", "fr": "francês"}
def yt_idiomas_alvo(p):
    """Idiomas das traduções do título/descrição (perfil.yaml → crosspost.youtube.traduzir: false | true | [lista]). true = padrão: idioma en → pt-BR, es, id, de, hi, fr; outro idioma → en, es."""
    z = yt_conf(p).get("traduzir", True)
    if isinstance(z, list): return [l for l in z if l.lower()[:2] != yt_idioma(p).lower()[:2]]
    if not z: return []
    return list(IDIOMAS_YT) if yt_idioma(p).lower().startswith("en") else [l for l in ("en", "es") if l != yt_idioma(p)]
def yt_projeto(p): return ((p.get("crosspost") or {}).get("youtube") or {}).get("projeto_google", "padrao")  # cota da API é por projeto do Google Cloud: um perfil pode ter projeto próprio
def yt_idioma(p): return yt_conf(p).get("idioma") or p.get("idioma_conteudo") or "en"  # perfil.yaml → idioma_conteudo (ex.: pt-BR); padrão "en"

def yt_token(p):
    c = yt_conf(p); r = requests.post(GOOGLE_TOKEN, data={"client_id": env(c["client_id_env"]), "client_secret": env(c["client_secret_env"]),
                                                        "refresh_token": env(c["refresh_token_env"]), "grant_type": "refresh_token"}, timeout=60)
    if not r.ok: raise RuntimeError(f"token do YouTube → {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]

def formato_da_edicao(p, ident):
    """Formato da edição (padrao, quiz, e_se…), lido do pautas.csv do perfil pela coluna usado_em."""
    import csv
    f = ROOT / p["pasta"] / "pautas.csv"
    if not f.exists(): return None
    for linha in csv.DictReader(f.open(encoding="utf-8")):
        if (linha.get("usado_em") or "").strip() == ident: return (linha.get("formato") or "").strip() or None

IDIOMAS_YT = ["pt-BR", "es", "id", "de", "hi", "fr"]  # títulos/descrições traduzidos (público de outros países)

def traduzir_yt(t, cross, alvo=None, origem="en"):
    """Traduz título e descrição do YouTube (t = textos.json["youtube"]) com `claude -p` (o sistema não tem chave de API). Guarda em textos.json → youtube.localizations
    (não gasta de novo no reenvio). Devolve {} se falhar: a tradução nunca derruba o envio."""
    alvo = alvo or list(IDIOMAS_YT)
    if t.get("localizations"): return t["localizations"]
    src = {"title": t["title"], "description": t["description"]}
    minus = t["title"][:1].islower()
    exemplo = "{" + ", ".join(f'"{l}": {{"title": "", "description": ""}}' for l in alvo) + "}"
    pedido = (f"Traduza o título e a descrição deste YouTube Short ({NOMES_IDIOMA.get(origem, origem)}) para: " + ", ".join(f"{l} ({NOMES_IDIOMA.get(l, l)})" for l in alvo) + ".\n"
              "Regras: tom direto e calmo, natural como um nativo escreveria. " + ("Frases em minúscula no começo (estilo da marca; em alemão mantenha a maiúscula dos substantivos). " if minus else "") + "Título com no máximo 100 caracteres, mantendo a pergunta. "
              "Descrição: mesma estrutura de parágrafos do original; NÃO acrescente o título na descrição (a 1ª linha da tradução = a 1ª linha do original traduzida), ÚLTIMA linha (hashtags) copiada sem alterar. Números, anos e nomes corretos. Avisos de saúde mantêm o sentido. Não acrescente nada.\n"
              "Responda SÓ com JSON válido: " + exemplo + ".\n\nTEXTO:\n" + json.dumps(src, ensure_ascii=False))
    try:
        r = subprocess.run([shutil.which("claude") or "claude", "-p", "--model", "sonnet"], input=pedido, capture_output=True, text=True, encoding="utf-8", timeout=420)
        txt = r.stdout; d = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        ult = src["description"].strip().split("\n")[-1].strip(); out = {}
        for L in alvo:
            x = d[L]; ti, de = str(x["title"]).strip(), str(x["description"]).strip()
            assert ti and len(ti) <= 100 and de and de.split("\n")[-1].strip() == ult and de.split("\n")[0].strip().lower() != ti.lower(), L
            out[L] = {"title": ti, "description": de}
        t["localizations"] = out
        try:
            f = cross / "textos.json"; dd = json.loads(f.read_text(encoding="utf-8")); dd["youtube"]["localizations"] = out; f.write_text(json.dumps(dd, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception: pass
        return out
    except Exception as e:
        print(f"tradução do YouTube não feita ({str(e)[:160]}); o vídeo sobe só no idioma original"); return {}

def yt_playlist(p, ident, video_id, tok):
    """Coloca o vídeo na playlist do formato (perfil.yaml → crosspost.youtube.playlists: {formato: título}). A playlist é criada na 1ª vez que um vídeo do
    formato sobe; o id fica em <pasta>/crosspost_playlists.json (renomear no Studio não quebra). Falha aqui nunca derruba o envio."""
    mapa = yt_conf(p).get("playlists") or {}
    fmt = formato_da_edicao(p, ident)
    if not mapa or not fmt or fmt not in mapa: return {"playlist": "sem formato mapeado"}
    H = {"Authorization": f"Bearer {tok}"}; reg = ROOT / p["pasta"] / "crosspost_playlists.json"
    ids = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    if fmt not in ids:
        titulo = mapa[fmt]
        lista = requests.get("https://www.googleapis.com/youtube/v3/playlists", params={"part": "snippet", "mine": "true", "maxResults": 50}, headers=H, timeout=60).json().get("items", [])
        achou = next((i["id"] for i in lista if i["snippet"]["title"].strip().lower() == titulo.lower()), None)
        if not achou:
            r = requests.post("https://www.googleapis.com/youtube/v3/playlists?part=snippet,status", headers=H, timeout=60,
                              json={"snippet": {"title": titulo, "description": (yt_conf(p).get("playlists_descricao") or {}).get(fmt, "")}, "status": {"privacyStatus": "public"}})
            if not r.ok: raise RuntimeError(f"criar playlist → {r.status_code}: {r.text[:300]}")
            achou = r.json()["id"]
        ids[fmt] = achou; reg.write_text(json.dumps(ids, ensure_ascii=False, indent=1), encoding="utf-8")
    r = requests.post("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet", headers=H, timeout=60,
                      json={"snippet": {"playlistId": ids[fmt], "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
    if not r.ok: raise RuntimeError(f"adicionar à playlist → {r.status_code}: {r.text[:300]}")
    return {"playlist": mapa[fmt], "playlist_id": ids[fmt]}

def _limpa_descr(desc, titulo):
    """Tira da descrição a 1ª linha quando ela só repete o título e junta linhas em branco a mais (regra §3). Usado para consertar o que já está no ar sem traduzir de novo."""
    L = desc.strip().split("\n")
    if L and L[0].strip().lower() == titulo.strip().lower(): L = L[1:]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(L).strip())

def conferir_no_ar(p, vid, t, loc=None, corrigir=True, out=None):
    """Lê o vídeo no ar (videos.list, 1 un.) e compara com o que foi mandado: título, descrição, idioma, categoria, privacidade, traduções, playlist.
    Se divergir e `corrigir`, grava de novo (videos.update, 50 un.) e devolve o que fez. Capa personalizada a API não mostra: vale o registro `capa` do envio.
    Dublagem automática NÃO tem API (GUIA.md parte 8): fica manual no YouTube Studio. Nunca levanta erro: devolve {"ok": False, "erro": ...}."""
    try:
        tok = yt_token(p); H = {"Authorization": f"Bearer {tok}"}; y = t["youtube"]; idi = yt_idioma(p)
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"part": "snippet,status,localizations,contentDetails", "id": vid}, headers=H, timeout=60)
        if not r.ok or not r.json().get("items"): return {"ok": False, "erro": f"videos.list → {r.status_code}: {r.text[:200]}"}
        it = r.json()["items"][0]; sn, st, lc = it["snippet"], it["status"], it.get("localizations") or {}; dif = []
        if sn.get("title") != y["title"]: dif.append("título")
        if (sn.get("description") or "").strip() != y["description"].strip(): dif.append("descrição")
        if sn.get("defaultLanguage") != idi: dif.append(f"idioma do vídeo ({sn.get('defaultLanguage')} → {idi})")
        if sn.get("defaultAudioLanguage") != idi: dif.append(f"idioma do áudio ({sn.get('defaultAudioLanguage')} → {idi})")
        if sn.get("categoryId") != "27": dif.append(f"categoria ({sn.get('categoryId')} → 27)")
        for lg, v in (loc or {}).items():
            if lg not in lc or lc[lg].get("title") != v["title"] or (not v.get("_so_titulo") and (lc[lg].get("description") or "").strip() != v["description"].strip()): dif.append(f"tradução {lg}")
        priv = yt_conf(p).get("privacidade", "public"); aviso = []
        dur = (it.get("contentDetails") or {}).get("duration") or ""   # 01/11/2026 (aviso 29/10): envio que falha deixava vídeo privado, "uploaded", duração zero
        if st.get("uploadStatus") in ("failed", "rejected") or dur in ("PT0S", "P0D") or (st.get("uploadStatus") == "uploaded" and not dur):
            aviso.append(f"VÍDEO VAZIO/SEM PROCESSAR no canal (uploadStatus {st.get('uploadStatus')}, duração {dur or 'vazia'}, privacidade {st.get('privacyStatus')}): conferir no Studio e apagar com o OK do dono do canal")
        if st.get("privacyStatus") != priv: aviso.append(f"privacidade {st.get('privacyStatus')} (esperado {priv}); não corrigida por aqui")
        pl = (out or {}).get("playlist_id")
        if pl:
            q = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params={"part": "id", "playlistId": pl, "videoId": vid}, headers=H, timeout=60)
            if q.ok and not q.json().get("items"): dif.append("playlist")
        res = {"ok": not dif and not aviso, "divergencias": dif, "avisos": aviso, "corrigido": False, "idioma_dublagem": "manual (sem API)"}
        if dif and corrigir:
            if any(d.split(" ")[0] in ("título", "descrição", "idioma", "categoria", "tradução") for d in dif):
                corpo = {"id": vid, "snippet": {"title": y["title"], "description": y["description"], "tags": y.get("tags", []), "categoryId": "27", "defaultLanguage": idi, "defaultAudioLanguage": idi}}
                if loc and not any(v.get("_so_titulo") for v in loc.values()): corpo["localizations"] = {yt_idioma(p): {"title": y["title"], "description": y["description"]}, **loc}
                elif lc:  # traduções guardadas podem estar velhas: conserta o texto que está no ar, sem traduzir de novo
                    novas = {lg: {"title": v["title"], "description": _limpa_descr(v.get("description") or "", v["title"])} for lg, v in lc.items()}
                    if any(novas[lg]["description"] != (lc[lg].get("description") or "").strip() for lg in lc): corpo["localizations"] = {**novas, yt_idioma(p): {"title": y["title"], "description": y["description"]}}
                u = requests.put("https://www.googleapis.com/youtube/v3/videos?part=snippet" + (",localizations" if "localizations" in corpo else ""), headers=H, json=corpo, timeout=60)
                res["corrigido"] = u.ok; res["update"] = "ok" if u.ok else f"{u.status_code}: {u.text[:200]}"
            if "playlist" in dif and out is not None:
                try: yt_playlist(p, (out or {}).get("_ident") or "", vid, tok); res["playlist_corrigida"] = True
                except Exception as e: res["playlist_erro"] = str(e)[:200]
        res["quando"] = dt.datetime.now().isoformat(timespec="seconds")
        return res
    except Exception as e: return {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:300]}"}

def conferir_cli(p, ident, corrigir=False):
    """CLI: confere no YouTube um vídeo já enviado (out/<id>/cross_youtube.json). Sem --corrigir só lê (1 un. de cota)."""
    m = ROOT / p["pasta"] / "out" / ident / "cross_youtube.json"; reg = json.loads(m.read_text(encoding="utf-8")); vid = reg.get("video_id")
    if not vid: print(f"{ident}: sem video_id"); return
    _, item = item_por_id(p, ident); t = textos(p, item)
    try: loc = json.loads((m.parent / "cross" / "textos.json").read_text(encoding="utf-8"))["youtube"].get("localizations") or {}
    except Exception: loc = {}
    if corrigir and (m.parent / "cross" / "textos.json").exists():  # molde novo: o textos.json velho e as traduções dele saem; traduz de novo do texto certo
        t = {**t, "youtube": atualiza_textos_yt(p, m.parent / "cross", ident)["youtube"]}
        alvo_tr = yt_idiomas_alvo(p); loc = traduzir_yt(t["youtube"], m.parent / "cross", alvo_tr, yt_idioma(p)) if alvo_tr else {}
        loc = {k: {**v} for k, v in loc.items()}
    else: loc = {k: {"title": v["title"], "description": "", "_so_titulo": True} for k, v in loc.items()}  # textos.json antigo pode estar desatualizado (descrições corrigidas no ar em 29/10/2026): só presença e título
    res = conferir_no_ar(p, vid, t, loc, corrigir, {"playlist_id": reg.get("playlist_id"), "_ident": ident})
    if corrigir: reg["conferencia"] = res; m.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"id": ident, "video": vid, **res}, ensure_ascii=False, indent=1))

ZONA_TITULO = {}  # {"<nome da composição>": (x0, y0, x1, y1)}: onde fica o título na capa 16:9; o normal é perfil.yaml → crosspost.youtube.thumb.zona_titulo
def confere_yt(p, cross, t=None, loc=None):
    """Checagem ANTES de enviar ao YouTube (29/10/2026, pedido do chat do YouTube). Devolve a lista de defeitos; vazia = pode enviar.
    Textos: título ≤ 100 e sem #Shorts; descrição sem a linha do título repetida, sem 3 quebras seguidas, sem link, hashtags no fim; idioma do perfil definido;
    traduções com a mesma linha de hashtags. Capa 16:9: existe, 1280×720, < 2 MB, título não sai pela borda direita, legível em 320 px de largura."""
    t = t or json.loads((cross / "textos.json").read_text(encoding="utf-8")); y = t["youtube"]; er = []
    tit, des = y["title"], y["description"]
    if len(tit) > 100: er.append(f"título com {len(tit)} caracteres (máx. 100)")
    if re.search(r"#shorts", tit, re.I): er.append("título com #Shorts")
    if des.split("\n")[0].strip().lower() == tit.strip().lower(): er.append("descrição repete o título na 1ª linha")
    if "\n\n\n" in des: er.append("descrição com 3 quebras de linha seguidas")
    if re.search(r"https?://|link in bio", des, re.I): er.append("descrição com link")
    ult = des.strip().split("\n")[-1]
    if not ult.startswith("#"): er.append("hashtags não estão no fim da descrição")
    else:  # molde único (29/10/2026): título + 3 linhas numeradas + 6 hashtags (3 fixas do perfil + 3 variáveis) + #Shorts; tags do vídeo = as 6 hashtags
        corpo_d = [l for l in des.strip().split("\n")[:-1] if l.strip()]
        if len(corpo_d) != 3 or not all(l.startswith(f"{i}. ") for i, l in enumerate(corpo_d, 1)): er.append("descrição fora do molde: precisa de 3 linhas numeradas '1. 2. 3.' (não parágrafos corridos)")
        elif any(l.split(". ", 1)[1].strip().lower() == tit.strip().lower() for l in corpo_d): er.append("descrição repete o título dentro das linhas numeradas")
        elif not 120 <= sum(len(l) for l in corpo_d) <= 450: er.append(f"descrição com {sum(len(l) for l in corpo_d)} caracteres no corpo (molde: 120 a 450)")
        tg = re.findall(r"#\w+", ult)
        if len(tg) != 7 or tg[-1].lower() != "#shorts": er.append(f"hashtags: precisam ser 6 + #Shorts, a descrição tem {len(tg)}")
        else:
            import hashtags as Hh
            cfgh = Hh.config(p)
            if cfgh and [x.lower() for x in tg[:3]] != [x.lower() for x in cfgh["fixas"]]: er.append(f"hashtags: as 3 primeiras precisam ser as fixas do perfil {cfgh['fixas']}")
            if sorted(x.lower() for x in (y.get("tags") or [])) != sorted(x.lstrip("#").lower() for x in tg[:6]): er.append("tags do vídeo diferentes das 6 hashtags da descrição")
    if (p.get("idioma_conteudo") or "en").lower()[:2] != yt_idioma(p).lower()[:2]: er.append(f"idioma do YouTube ({yt_idioma(p)}) diferente do idioma do perfil ({p.get('idioma_conteudo')})")
    for lg, v in (loc or {}).items():
        if (v.get("description") or "").strip().split("\n")[-1] != ult: er.append(f"tradução {lg}: última linha (hashtags) diferente da original")
    th = cross / "thumb.jpg"
    if yt_conf(p).get("thumb") and not th.exists(): er.append("capa 16:9 não existe")
    if th.exists():
        from PIL import Image
        im = Image.open(th).convert("RGB")
        if im.size != (1280, 720): er.append(f"capa 16:9 com {im.size}, esperado 1280×720")
        if th.stat().st_size > 2_000_000: er.append("capa 16:9 com mais de 2 MB")
        px = im.load(); creme = lambda c: abs(c[0] - 255) + abs(c[1] - 246) + abs(c[2] - 228) < 60
        if any(creme(px[x, y2]) for x in range(1268, 1280) for y2 in range(120, 470, 2)): er.append("capa 16:9: título encosta/sai pela borda direita")
        cfgt = yt_conf(p).get("thumb") or {}; zona = cfgt.get("zona_titulo") or next((z for k2, z in ZONA_TITULO.items() if k2 in str(cfgt.get("composicao"))), None)
        if zona:  # (x0, y0, x1, y1) em px de 1280×720; cor do título = creme em todos os perfis até hoje
            pq = im.resize((320, 180)).load(); x0, y0, x1, y1 = [v // 4 for v in zona]; n = sum(creme(pq[x, y2]) for x in range(x0, x1) for y2 in range(y0, y1))
            if n < 0.05 * (x1 - x0) * (y1 - y0): er.append("capa 16:9: título quase não aparece em 320 px de largura")
    return er

def _enviar_resumivel(url, dados, tentativas=4):
    """PUT do vídeo na sessão resumível. Se a rede cair/der timeout no meio (29/10/2026, REGRAS §7), pergunta ao YouTube quantos bytes chegaram
    (Content-Range: bytes */total) e continua dali; 200/201 = vídeo criado. O YouTube só cria o vídeo quando o envio termina: sem resposta final, não fica rascunho."""
    tam = len(dados); ultimo = None
    for i in range(tentativas):
        try:
            if i == 0: r = requests.put(url, data=dados, headers={"Content-Type": "video/mp4"}, timeout=1800)
            else:
                st = requests.put(url, headers={"Content-Length": "0", "Content-Range": f"bytes */{tam}"}, timeout=60)
                if st.status_code in (200, 201): return st
                if st.status_code == 308:
                    rg = st.headers.get("Range"); ja = int(rg.split("-")[1]) + 1 if rg else 0
                    r = requests.put(url, data=dados[ja:], headers={"Content-Type": "video/mp4", "Content-Range": f"bytes {ja}-{tam - 1}/{tam}"}, timeout=1800)
                else: r = st
            if r.ok or r.status_code in (400, 401, 403, 404): return r
            ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as e: ultimo = repr(e)[:160]; time.sleep(5 * (i + 1))
    raise RuntimeError(f"upload interrompido depois de {tentativas} tentativas ({ultimo}); sem resposta final do YouTube não fica vídeo no canal (se travar de novo, conferir em Studio → Conteúdo)")

def atualiza_textos_yt(p, cross, ident=None):
    """Põe o textos.json (preparado antes do molde de 29/10/2026) no molde atual. Se a descrição mudou, as traduções guardadas saem (são de outro texto) e voltam a ser feitas."""
    ident = ident or cross.parent.name; f = cross / "textos.json"; d = json.loads(f.read_text(encoding="utf-8"))
    _, item = item_por_id(p, ident); novo = textos(p, item)["youtube"]
    if d["youtube"].get("description") != novo["description"] or d["youtube"].get("title") != novo["title"] or d["youtube"].get("tags") != novo["tags"]:
        d["youtube"] = {**novo}; f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); print(f"{ident}: textos do YouTube atualizados ao molde atual")
    return d

def yt_publicar(p, cross):
    t = atualiza_textos_yt(p, cross); tok = yt_token(p); H = {"Authorization": f"Bearer {tok}"}
    alvo_tr = yt_idiomas_alvo(p); loc = traduzir_yt(t["youtube"], cross, alvo_tr, yt_idioma(p)) if alvo_tr else {}
    erros = confere_yt(p, cross, t, loc)
    if erros: raise RuntimeError("checagem do YouTube reprovou, nada foi enviado: " + "; ".join(erros))
    meta = {"snippet": {"title": t["youtube"]["title"], "description": t["youtube"]["description"], "tags": t["youtube"]["tags"], "categoryId": "27",
                        "defaultLanguage": yt_idioma(p), "defaultAudioLanguage": yt_idioma(p)},  # idioma dito ao YouTube (28/10/2026: 99,9% das views vinham com idioma "não especificado")  # 27 = Education
            "status": {"privacyStatus": yt_conf(p).get("privacidade", "public"), "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    if loc: meta["localizations"] = {yt_idioma(p): {"title": t["youtube"]["title"], "description": t["youtube"]["description"]}, **loc}
    dados = (cross / "video.mp4").read_bytes()
    def _iniciar(m):
        return requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status" + (",localizations" if "localizations" in m else ""),
                             headers={**H, "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(dados))}, json=m, timeout=60)
    ini = _iniciar(meta); loc_pos = None
    if not ini.ok and "localizations" in meta:  # se o YouTube recusar as traduções no envio, sobe só em inglês e tenta gravá-las depois do envio
        loc_pos = meta.pop("localizations"); ini = _iniciar(meta)
    if not ini.ok: raise RuntimeError(f"YouTube iniciar → {ini.status_code}: {ini.text[:400]}")
    up = _enviar_resumivel(ini.headers["Location"], dados)
    if not up.ok: raise RuntimeError(f"YouTube enviar → {up.status_code}: {up.text[:400]}")
    vid = up.json()["id"]; out = {"plataforma": "youtube", "video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}
    try:  # 29/10/2026: depois que o vídeo existe, nenhuma falha pode perder o video_id (o reenvio criaria um vídeo repetido)
        if loc_pos:  # o envio recusou as traduções: grava depois do envio (50 unidades de cota)
            r = requests.put("https://www.googleapis.com/youtube/v3/videos?part=snippet,localizations", headers=H, json={"id": vid, "snippet": meta["snippet"], "localizations": {yt_idioma(p): {"title": t["youtube"]["title"], "description": t["youtube"]["description"]}, **loc_pos}}, timeout=60)
            out["traducao"] = "ok (depois do envio)" if r.ok else f"não gravada ({r.status_code})"
        elif loc: out["traducao"] = "ok"
        thumb = cross / "thumb.jpg"; arq = thumb if thumb.exists() else (pathlib.Path(t["capa"]) if t.get("capa") else None)  # thumb 16:9 do padrão do perfil; sem ela, a capa do reel
        if arq and yt_conf(p).get("capa", False):  # capa própria exige canal verificado; falha não derruba o post
            r = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", headers={**H, "Content-Type": "image/jpeg"}, data=arq.read_bytes(), timeout=120)
            out["capa"] = "ok" if r.ok else f"não aplicada ({r.status_code})"
        try: out.update(yt_playlist(p, cross.parent.name, vid, tok))
        except Exception as e: out["playlist"] = f"falhou: {e}"
        out["conferencia"] = conferir_no_ar(p, vid, t, loc, True, {**out, "_ident": cross.parent.name})  # lê o vídeo no ar e corrige o que divergir (REGRAS-POSTS-YOUTUBE §7)
    except Exception as e: out["erro_pos_envio"] = f"{type(e).__name__}: {str(e)[:300]}"
    return out

# ---------- TikTok ----------
def tt_conf(p): return p["crosspost"].get("tiktok") or {}

def tt_token(p):
    c = tt_conf(p); r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={"client_key": env(c["client_key_env"]), "client_secret": env(c["client_secret_env"]),
                                      "grant_type": "refresh_token", "refresh_token": env(c["refresh_token_env"])}, timeout=60)
    j = r.json() if r.ok else {}
    if "access_token" not in j: raise RuntimeError(f"token do TikTok → {r.status_code}: {r.text[:300]}")
    if j.get("refresh_token") and j["refresh_token"] != env(c["refresh_token_env"]):  # o TikTok troca o refresh token: guarda o novo no .env
        envf = ROOT / ".env"; txt = envf.read_text(encoding="utf-8")
        envf.write_text(re.sub(rf"^{c['refresh_token_env']}=.*$", f"{c['refresh_token_env']}={j['refresh_token']}", txt, flags=re.M), encoding="utf-8"); os.environ[c["refresh_token_env"]] = j["refresh_token"]
    return j["access_token"]

def tt_publicar(p, cross):
    t = json.loads((cross / "textos.json").read_text(encoding="utf-8")); tok = tt_token(p); H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    info = requests.post("https://open.tiktokapis.com/v2/post/publish/creator_info/query/", headers=H, timeout=60).json()
    opcoes = (info.get("data") or {}).get("privacy_level_options") or ["SELF_ONLY"]
    privacidade = tt_conf(p).get("privacidade", "PUBLIC_TO_EVERYONE")
    if privacidade not in opcoes: privacidade = "SELF_ONLY" if "SELF_ONLY" in opcoes else opcoes[0]  # app sem auditoria só posta privado
    dados = (cross / "video.mp4").read_bytes(); n = len(dados); pedaco = n if n <= 64 * 2**20 else 32 * 2**20; partes = max(1, -(-n // pedaco))
    corpo = {"post_info": {"title": t["tiktok"]["caption"], "privacy_level": privacidade, "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                           "is_aigc": True}, "source_info": {"source": "FILE_UPLOAD", "video_size": n, "chunk_size": pedaco, "total_chunk_count": partes}}
    r = requests.post("https://open.tiktokapis.com/v2/post/publish/video/init/", headers=H, json=corpo, timeout=60).json()
    if (r.get("error") or {}).get("code") != "ok": raise RuntimeError(f"TikTok iniciar → {r}")
    pid, url = r["data"]["publish_id"], r["data"]["upload_url"]
    for i in range(partes):
        a, b = i * pedaco, min(n, (i + 1) * pedaco) if i < partes - 1 else n
        u = requests.put(url, data=dados[a:b], headers={"Content-Type": "video/mp4", "Content-Length": str(b - a), "Content-Range": f"bytes {a}-{b - 1}/{n}"}, timeout=900)
        if u.status_code not in (200, 201, 206): raise RuntimeError(f"TikTok enviar parte {i + 1} → {u.status_code}: {u.text[:300]}")
    for _ in range(30):
        s = requests.post("https://open.tiktokapis.com/v2/post/publish/status/fetch/", headers=H, json={"publish_id": pid}, timeout=60).json().get("data", {})
        if s.get("status") in ("PUBLISH_COMPLETE", "FAILED"): break
        time.sleep(10)
    if s.get("status") != "PUBLISH_COMPLETE": raise RuntimeError(f"TikTok não concluiu: {s}")
    return {"plataforma": "tiktok", "publish_id": pid, "privacidade": privacidade, "status": s.get("status"), "post_ids": s.get("publicaly_available_post_id") or s.get("publicly_available_post_id")}

# ---------- via Zernio (28/10/2026): perfis sem a cota do Google / sem app do TikTok ----------
def zr_conf(p, plat): return PLATAFORMAS[plat][2](p)

def zr_publicar(p, cross, plat):
    """Sobe o vídeo cortado para a Zernio e publica na conta ligada (perfil.yaml → crosspost.<plat>.zernio_account_id, via: zernio)."""
    import zernio, urllib.request
    c = zr_conf(p, plat); t = json.loads((cross / "textos.json").read_text(encoding="utf-8"))
    pre = zernio.chamar("POST", "/media/presign", {"filename": f"{cross.parent.name}.mp4", "contentType": "video/mp4"})
    up = urllib.request.Request(pre["uploadUrl"], data=(cross / "video.mp4").read_bytes(), method="PUT", headers={"Content-Type": "video/mp4"})
    urllib.request.urlopen(up, timeout=1800)
    alvo = {"platform": plat, "accountId": c["zernio_account_id"]}
    if plat == "youtube":
        yt = t["youtube"]; vis = c.get("privacidade", "public")
        alvo["platformSpecificData"] = {"categoryId": "27", "containsSyntheticMedia": True, "madeForKids": False, "visibility": vis}
        if c.get("playlist_id"): alvo["platformSpecificData"]["playlistId"] = c["playlist_id"]
        corpo = {"content": yt["description"], "title": yt["title"][:100], "tags": yt["tags"], "visibility": vis}
    else:
        alvo["platformSpecificData"] = {"allowComment": True, "allowDuet": True, "allowStitch": True}
        corpo = {"content": t["tiktok"]["caption"]}
    corpo.update({"platforms": [alvo], "mediaItems": [{"type": "video", "url": pre["publicUrl"], "mimeType": "video/mp4"}]})
    corpo.update({"publishNow": True} if not c.get("rascunho") else {})  # rascunho: true = fica como rascunho na Zernio (teste)
    r = zernio.chamar("POST", "/posts", corpo); post = r.get("post", r)
    return {"plataforma": plat, "via": "zernio", "post_id": post.get("_id"), "status": post.get("status")}

# ---------- fluxo ----------
PLATAFORMAS = {"youtube": (yt_publicar, ("client_id_env", "client_secret_env", "refresh_token_env"), yt_conf),
               "tiktok": (tt_publicar, ("client_key_env", "client_secret_env", "refresh_token_env"), tt_conf)}

def faltas(p, plat):
    c = PLATAFORMAS[plat][2](p)
    if c.get("via") == "zernio": return [k for k, ok in (("ZERNIO_API_KEY", env("ZERNIO_API_KEY")), ("zernio_account_id", c.get("zernio_account_id"))) if not ok]
    return [c.get(k, k) for k in PLATAFORMAS[plat][1] if not env(c.get(k, ""))]

def registrar_erro(saida, plat, msg):
    """out/<id>/cross_<plataforma>_erro.json: o Painel lê para avisar a falha (some quando o envio dá certo)"""
    f = saida / f"cross_{plat}_erro.json"
    try: n = int(json.loads(f.read_text(encoding="utf-8")).get("tentativas", 0)) + 1 if f.exists() else 1
    except Exception: n = 1
    f.write_text(json.dumps({"plataforma": plat, "status": "falhou", "erro": msg[:500], "tentativas": n, "quando": dt.datetime.now(TZ).isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")

def publicar(p, ident, so=None, dry=False):
    cross = ROOT / p["pasta"] / "out" / ident / "cross"
    if not (cross / "video.mp4").exists() or not (cross / "textos.json").exists():
        try: cross = preparar(p, ident)
        except Exception as e:  # o corte do vídeo falhou: registra para todas as plataformas ligadas e segue (a próxima rodada tenta de novo)
            for plat, (_, _, conf) in PLATAFORMAS.items():
                if conf(p).get("ativo") and (not so or plat == so) and not (cross.parent / f"cross_{plat}.json").exists(): registrar_erro(cross.parent, plat, f"preparar o vídeo: {e}")
            print(json.dumps({"id": ident, "resultado": {"erro": f"preparar: {e}"}}, ensure_ascii=False)); return {}
    res = {}
    for plat, (fn, _, conf) in PLATAFORMAS.items():
        if so and plat != so: continue
        if not conf(p).get("ativo"): continue
        marca = cross.parent / f"cross_{plat}.json"
        if marca.exists(): res[plat] = {"status": "já publicado"}; continue
        f = faltas(p, plat)
        if f: res[plat] = {"status": "bloqueado", "faltam_no_env": f}; continue
        if dry: res[plat] = {"status": "dry-run"}; continue
        try:
            r = zr_publicar(p, cross, plat) if conf(p).get("via") == "zernio" else fn(p, cross); r.setdefault("enviado_em", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")); marca.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8"); res[plat] = {"status": "publicado", **r}
            (cross.parent / f"cross_{plat}_erro.json").unlink(missing_ok=True)
        except Exception as e:
            res[plat] = {"status": "falhou", "erro": str(e)}; registrar_erro(cross.parent, plat, str(e))
    print(json.dumps({"id": ident, "resultado": res}, ensure_ascii=False, indent=1)); return res

# Cota da YouTube Data API: 10.000 unidades/dia por projeto (um upload + capa ≈ 1.650), compartilhada por TODOS os canais. Teto global por dia;
# os posts novos têm prioridade e o acervo (o que já estava no ar antes de `desde`) só usa o que sobrar, até MAX_ACERVO_DIA.
MAX_DIA, MAX_ACERVO_DIA = 5, 2
# Ritmo por canal (uploads colados rendem pouco): no máximo 3 por dia e 4 h entre um envio e o próximo.
MAX_DIA_CANAL, INTERVALO_H = 3, 4

def _quando_envio(m, tz):
    """Instante do envio: `enviado_em` do cross_youtube.json (gravado no envio); sem ele, a data do arquivo. Conferir/corrigir um vídeo regrava o arquivo e NÃO conta como envio novo."""
    try:
        e = json.loads(m.read_text(encoding="utf-8")).get("enviado_em")
        if e: return dt.datetime.fromisoformat(e).astimezone(tz)
    except Exception: pass
    return dt.datetime.fromtimestamp(m.stat().st_mtime, tz)

def envios_do_canal(perfil):
    """(enviados hoje no dia do Pacífico, instante do último envio) deste perfil ao YouTube, lidos de out/*/cross_youtube.json."""
    PT = ZoneInfo("America/Los_Angeles"); hoje = dt.datetime.now(PT).date(); n = 0; ult = None
    for m in (ROOT / perfil["pasta"] / "out").glob("*/cross_youtube.json"):
        try:
            if json.loads(m.read_text(encoding="utf-8")).get("via") == "zernio": continue
        except Exception: pass
        t = _quando_envio(m, PT)
        if t.date() == hoje: n += 1
        if ult is None or t > ult: ult = t
    return n, ult

def enviados_hoje(perfil=None):
    """(total, acervo) de envios ao YouTube feitos hoje (dia do Pacífico, que é o da cota), somando todos os perfis, lidos de out/*/cross_youtube.json."""
    PT = ZoneInfo("America/Los_Angeles")  # a cota da API zera à meia-noite do Pacífico
    hoje = dt.datetime.now(PT).date(); total = acervo = 0
    for p in CFG["perfis"]:
        if not p.get("pasta"): continue
        if perfil and yt_projeto(p) != yt_projeto(perfil): continue  # a cota é por projeto do Google
        for m in (ROOT / p["pasta"] / "out").glob("*/cross_youtube.json"):
            if _quando_envio(m, PT).date() != hoje: continue
            try:
                if json.loads(m.read_text(encoding="utf-8")).get("via") == "zernio": continue  # não gasta a cota do Google
            except Exception: pass
            total += 1
            try: acervo += bool(json.loads(m.read_text(encoding="utf-8")).get("acervo")) and (not perfil or p["pasta"] == perfil["pasta"])  # o teto do acervo é por perfil
            except Exception: pass
    return total, acervo

def candidatos(p):
    """Itens já postados no Instagram (post.json ok) ainda sem cross-post nas plataformas ligadas e com credenciais: (novo?, horario, id)."""
    desde = str(p["crosspost"].get("desde", "")); agora = dt.datetime.now(TZ); out = []
    for f in sorted((ROOT / p["pasta"] / "posts" / "05-publicado").glob("*.json")):
        it = json.loads(f.read_text(encoding="utf-8")); ident = it.get("id"); saida = ROOT / p["pasta"] / "out" / str(ident)
        if not (saida / "post.json").exists() or not (ROOT / it.get("video", "x")).exists(): continue
        post = json.loads((saida / "post.json").read_text(encoding="utf-8"))
        if post.get("status") != "publicado": continue
        novo = str(it["horario"]) >= desde
        if not novo and not p["crosspost"].get("acervo"): continue
        if not novo and str(p["crosspost"].get("acervo_pausado_ate", "")) > agora.strftime("%Y-%m-%d %H:%M"): continue  # pausa do acervo com hora para voltar (horário de NY)
        ts = post.get("timestamp")
        if ts and agora - dt.datetime.fromisoformat(ts.replace("+0000", "+00:00")).astimezone(TZ) < dt.timedelta(minutes=ATRASO_MIN): continue
        pend = [pl for pl in PLATAFORMAS if p["crosspost"].get(pl, {}).get("ativo") and not (saida / f"cross_{pl}.json").exists() and not faltas(p, pl)]
        if pend: out.append((novo, str(it["horario"]), ident))
    return out

def reserva_novos(projeto=None, so=None):
    """Posts novos (depois de `desde`) que ainda vão precisar de envio hoje: já no ar sem cross-post + os da fila de hoje (04-aprovado). O acervo só usa o que sobrar disso."""
    hoje = dt.datetime.now(TZ).strftime("%Y-%m-%d"); n = 0
    for q in perfis():
        if not (q["crosspost"].get("youtube") or {}).get("ativo"): continue
        if projeto and yt_projeto(q) != projeto: continue
        if so and q["pasta"] != so["pasta"]: continue
        n += sum(1 for c in candidatos(q) if c[0])
        for f in (ROOT / q["pasta"] / "posts" / "04-aprovado").glob(f"{hoje}_*.json"):
            if str(json.loads(f.read_text(encoding="utf-8")).get("horario", "")) >= str(q["crosspost"].get("desde", "")): n += 1
    return n

MAX_FALHAS = 6
def _travado(p, ident):
    f = ROOT / p["pasta"] / "out" / ident / "cross_youtube_erro.json"
    try: n = int(json.loads(f.read_text(encoding="utf-8")).get("tentativas", 0))
    except Exception: return False
    if n >= MAX_FALHAS: print(f'{p["handle"]}: {ident} falhou {n} vezes no YouTube; fora da vez até alguém resolver (ver {f.name})')
    return n >= MAX_FALHAS

def proximo(p, dry=False):
    """Um envio por rodada e por perfil: primeiro o post novo mais antigo; sem novo, o acervo do mais recente para o mais antigo (se a cota do dia deixar)."""
    cand = candidatos(p); total, acervo = enviados_hoje(p)
    cand = [c for c in cand if not _travado(p, c[2])]  # vídeo que já falhou MAX_FALHAS vezes seguidas sai da vez (avisa) para não travar a fila inteira
    novos = sorted(c for c in cand if c[0]); velhos = sorted((c for c in cand if not c[0]), reverse=True)
    if total >= MAX_DIA and (p['crosspost'].get('youtube') or {}).get('via') != 'zernio': print(f'{p["handle"]}: teto de {MAX_DIA} envios/dia ao YouTube atingido ({total}); volta amanhã'); return None
    if (p['crosspost'].get('youtube') or {}).get('via') != 'zernio':
        n_canal, ult = envios_do_canal(p)
        if n_canal >= MAX_DIA_CANAL: print(f'{p["handle"]}: teto de {MAX_DIA_CANAL} envios/dia neste canal atingido ({n_canal}); volta amanhã'); return None
        if ult and dt.datetime.now(ult.tzinfo) - ult < dt.timedelta(hours=INTERVALO_H): print(f'{p["handle"]}: último envio às {ult:%H:%M} (Pacífico); só envia de novo com {INTERVALO_H} h de intervalo'); return None
    folga = total + reserva_novos(yt_projeto(p)) < MAX_DIA and envios_do_canal(p)[0] + reserva_novos(yt_projeto(p), p) < MAX_DIA_CANAL  # o acervo só entra se sobrar cota (projeto) e vaga no canal (3/dia) depois dos posts novos do dia
    alvo = novos[0] if novos else (velhos[0] if velhos and acervo < MAX_ACERVO_DIA and folga else None)
    if not alvo: print(f'{p["handle"]}: nada para cross-postar' + (f" (acervo: {len(velhos)} na fila, teto do dia {acervo}/{MAX_ACERVO_DIA})" if velhos else "")); return None
    publicar(p, alvo[2], None, dry)
    if not alvo[0] and not dry:
        m = ROOT / p["pasta"] / "out" / alvo[2] / "cross_youtube.json"
        if m.exists(): d = json.loads(m.read_text(encoding="utf-8")); d["acervo"] = True; m.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return alvo[2]

def refazer_thumbs(p, so_id=None):
    """Gera de novo a thumb 16:9 e aplica nos vídeos do YouTube já enviados (out/<id>/cross_youtube.json → video_id)."""
    tok = yt_token(p)
    for m in sorted((ROOT / p["pasta"] / "out").glob("*/cross_youtube.json")):
        ident = m.parent.name
        if so_id and ident != so_id: continue
        vid = json.loads(m.read_text(encoding="utf-8")).get("video_id")
        try: jpg = gerar_thumb(p, ident)
        except Exception as e: print(f"{ident}: thumb falhou: {str(e)[-200:]}"); continue
        if not jpg or not vid: print(f"{ident}: sem thumb ou sem video_id"); continue
        r = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", headers={"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}, data=jpg.read_bytes(), timeout=120)
        print(f"{ident}: thumb 16:9 {'aplicada' if r.ok else 'recusada ' + str(r.status_code) + ' ' + r.text[:150]} ({vid})")

def checar(p):
    out = {"perfil": p["handle"]}
    for plat, (_, _, conf) in PLATAFORMAS.items():
        c = conf(p); out[plat] = {"ativo": bool(c.get("ativo")), "faltam_no_env": faltas(p, plat)}
        if c.get("ativo") and not out[plat]["faltam_no_env"]:
            try:
                if c.get("via") == "zernio":
                    import zernio; ids = [a["_id"] for a in zernio.contas()["accounts"]]
                    out[plat]["token"] = "ok (Zernio)" if c["zernio_account_id"] in ids else "conta não encontrada na Zernio"
                else: (yt_token if plat == "youtube" else tt_token)(p); out[plat]["token"] = "ok"
            except Exception as e: out[plat]["token"] = str(e)
    print(json.dumps(out, ensure_ascii=False, indent=1))

# ---------- autorização (uma vez por conta) ----------
def auth_youtube(p):
    c = yt_conf(p); cid, sec = env(c["client_id_env"]), env(c["client_secret_env"])
    if not cid or not sec: sys.exit(f"coloque {c['client_id_env']} e {c['client_secret_env']} no .env (Google Cloud → Credenciais → ID do cliente OAuth, tipo Desktop)")
    cod = {}
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            cod["code"] = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [""])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write("Pronto, pode fechar esta aba.".encode())
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", 0), H); redir = f"http://127.0.0.1:{srv.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({"client_id": cid, "redirect_uri": redir, "response_type": "code", "access_type": "offline",
          "prompt": "select_account consent", "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"})
    print("Abrindo o navegador. Entre com a conta do canal certo.\n", url); webbrowser.open(url); srv.handle_request()
    r = requests.post(GOOGLE_TOKEN, data={"code": cod.get("code", ""), "client_id": cid, "client_secret": sec, "redirect_uri": redir, "grant_type": "authorization_code"}, timeout=60)
    if "refresh_token" not in r.json(): sys.exit(f"sem refresh token: {r.text[:300]}")
    print(f"\nAdicione ao .env:\n{c['refresh_token_env']}={r.json()['refresh_token']}")

def auth_tiktok(p, url_retorno=None):
    c = tt_conf(p); key, sec, redir = env(c["client_key_env"]), env(c["client_secret_env"]), c.get("redirect_uri", "")
    if not key or not sec or not redir: sys.exit("precisa de client_key e client_secret no .env e crosspost.tiktok.redirect_uri no perfil.yaml (o mesmo cadastrado no app do TikTok)")
    if not url_retorno:
        print("Abra, entre na conta do TikTok e autorize; depois copie a URL final da barra de endereço e rode de novo com --url-retorno '<URL>':\n" +
              "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({"client_key": key, "scope": "user.info.basic,video.upload,video.publish", "response_type": "code", "redirect_uri": redir, "state": "ig"})); return
    code = urllib.parse.parse_qs(urllib.parse.urlparse(url_retorno).query).get("code", [""])[0]
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={"client_key": key, "client_secret": sec, "code": code, "grant_type": "authorization_code", "redirect_uri": redir}, timeout=60).json()
    if "refresh_token" not in r: sys.exit(f"sem refresh token: {r}")
    print(f"\nAdicione ao .env:\n{c['refresh_token_env']}={r['refresh_token']}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["preparar", "publicar", "proximo", "checar", "refazer-thumbs", "conferir-no-ar", "auth-youtube", "auth-tiktok"]); ap.add_argument("id", nargs="?")
    ap.add_argument("--perfil"); ap.add_argument("--so", choices=list(PLATAFORMAS)); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--url-retorno"); ap.add_argument("--corrigir", action="store_true")
    a = ap.parse_args(); alvo = [acha(a.perfil)] if a.perfil else perfis()
    for p in alvo:
        if a.cmd == "preparar": preparar(p, a.id)
        elif a.cmd == "publicar": publicar(p, a.id, a.so, a.dry_run)
        elif a.cmd == "proximo": proximo(p, a.dry_run)
        elif a.cmd == "checar": checar(p)
        elif a.cmd == "refazer-thumbs": refazer_thumbs(p, a.id)
        elif a.cmd == "conferir-no-ar": conferir_cli(p, a.id, a.corrigir)
        elif a.cmd == "auth-youtube": auth_youtube(p)
        else: auth_tiktok(p, a.url_retorno)
