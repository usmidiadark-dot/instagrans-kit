"""Mix de áudio de uma edição, pelas regras de _sistema/audio-mix.md (voz na frente, trilha com ducking, SFX ajustados).
Uso (na raiz do projeto):  python _sistema/orquestrador/mix.py <pasta_da_edicao>
Lê da pasta: voice.mp3, words.json, narracao.txt, sfx.json.  Grava: mix.wav, mix_preview.mp3, stems/{voz,trilha,sfx}.wav, mix_check.json."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import json, pathlib, re, subprocess, sys
import numpy as np
import pyloudnorm as pyln
import yaml
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import lfilter, resample_poly

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from voz_words import pcm16k, palavras_roteiro, junta_numeros, norm, wer, NUM  # noqa: E402

SR = 48000
ROOT = pathlib.Path(__file__).resolve().parents[2]
REGRA = {"voz_lufs": -16, "voz_tp": -3, "trilha_lufs": -24, "sfx_pico": -8, "sfx_cauda_s": 1.5, "duck_db": 10,
         "ataque_s": 0.08, "release_s": 0.4, "sfx_chave_db": -4, "final_lufs": -14, "limiter_tp": -1.5,
         "trilha_fade_in_s": 0.0, "trilha_fade_out_s": 0.03,
         # cadeia da voz e metas voz × trilha também podem vir do perfil (ex.: voz mais quente, trilha mais presente)
         "voz_filtros": "highpass=f=80,deesser=i=0.3,acompressor=ratio=3:threshold=-22dB:attack=8:release=120:makeup=1",
         "voz_trilha_p10": 12, "voz_trilha_mediana": 15,
         "duck_juntar_s": 0.35}  # pausas de fala menores que isso não deixam a trilha subir (perfil calmo: 1,2 s, sem "bombear"); fades da trilha: perfil.yaml → audio
db = lambda x: 10 ** (x / 20)

def le(caminho, filtros=None):
    """Decodifica qualquer áudio para float32 estéreo 48 kHz (filtros ffmpeg opcionais)."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(caminho)] + (["-af", filtros] if filtros else []) + ["-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32).reshape(-1, 2).copy()

def grava(caminho, x):
    caminho.parent.mkdir(parents=True, exist_ok=True); wavfile.write(caminho, SR, x.astype(np.float32))

meter = pyln.Meter(SR)
def lufs(x): return meter.integrated_loudness(x)
def true_peak(x): return 20 * np.log10(np.max(np.abs(resample_poly(x, 4, 1, axis=0))) + 1e-12)
def no_tamanho(x, n): return x[:n] if len(x) >= n else np.vstack([x, np.zeros((n - len(x), 2), np.float32)])

def k_momentaneo(x, janela=0.4, passo=0.1):
    """Loudness momentânea (BS.1770, janelas de 400 ms) em LUFS por passo."""
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    k = lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)
    w, h = int(janela * SR), int(passo * SR)
    ms = np.array([np.mean(k[i:i + w] ** 2, axis=0).sum() for i in range(0, len(k) - w + 1, h)])
    return -0.691 + 10 * np.log10(ms + 1e-12)

def mascara_fala(words, n, juntar=0.35):
    """Trechos de fala (palavras com folga < 350 ms viram um trecho só)."""
    trechos = []
    for w in words:
        if trechos and w["start"] - trechos[-1][1] < juntar: trechos[-1][1] = w["end"]
        else: trechos.append([w["start"], w["end"]])
    m = np.zeros(n, bool)
    for s, e in trechos: m[int(s * SR):int(e * SR)] = True
    return m, trechos

def envelope_duck(fala, duck_db, ataque, release):
    """Ganho da trilha: cai duck_db durante a fala (ataque 80 ms, com antecipação igual ao ataque), volta em 400 ms."""
    ctrl = 1000; passo = SR // ctrl
    alvo = np.where(fala[::passo], -duck_db, 0.0)
    ant = int(ataque * ctrl); alvo = np.minimum(alvo, np.concatenate([alvo[ant:], np.zeros(ant)]))
    g = np.zeros_like(alvo); ca, cr = 1 - np.exp(-1 / (ataque * ctrl / 3)), 1 - np.exp(-1 / (release * ctrl / 3))
    for i in range(1, len(alvo)):
        g[i] = g[i - 1] + (ca if alvo[i] < g[i - 1] else cr) * (alvo[i] - g[i - 1])
    return db(np.interp(np.arange(len(fala)), np.arange(len(g)) * passo, g))[:, None]

def limita(x, tp_alvo, janela=0.008):
    """Limiter de true peak (oversampling 4x) com antecipação: o ganho já está baixo quando o pico chega.
    min-filter de 2L + média móvel de L garante ganho ≤ o necessário em cada amostra. (O alimiter do ffmpeg erra o teto.)"""
    teto = db(tp_alvo - 0.3)
    pico = np.abs(resample_poly(x, 4, 1, axis=0)).max(axis=1)[:len(x) * 4].reshape(-1, 4).max(axis=1)
    g = np.minimum(1.0, teto / (pico + 1e-12))
    L = int(janela * SR)
    g = uniform_filter1d(minimum_filter1d(g, 2 * L + 1), L + 1)
    return (x * g[:, None]).astype(np.float32)

def normaliza(x, alvo_lufs, tp):
    """Ganho até o LUFS alvo e limiter no teto; repete até os dois baterem."""
    for _ in range(4):
        x = limita(x * db(alvo_lufs - lufs(x)), tp)
        if abs(lufs(x) - alvo_lufs) < 0.2: break
    return x

def main(pasta):
    pasta = pathlib.Path(pasta); cfg = json.loads((pasta / "sfx.json").read_text(encoding="utf-8"))
    sem_voz = not (pasta / "voice.mp3").exists()  # perfil sem narração: voz = silêncio, sem gates de voz/Whisper; cfg["duracao_s"] manda
    words = [] if sem_voz else json.loads((pasta / "words.json").read_text(encoding="utf-8"))
    perfil = next((p for p in carrega(ROOT)["perfis"]
                   if p.get("pasta") and p["pasta"] in pasta.resolve().parts), {})
    REGRA.update(perfil.get("audio") or {})
    # teto de fundo (ruído de fundo alto demais): ambiente e sons contínuos nunca acima destes níveis (perfil.yaml → audio.ambiente_max_db / continuo_max_db)
    _am, _co = REGRA.get("ambiente_max_db"), REGRA.get("continuo_max_db")
    if _am is not None and cfg.get("ambiente"): cfg["ambiente"]["db"] = min(cfg["ambiente"].get("db", 0), _am)
    if _co is not None:
        for _e in cfg.get("eventos", []):
            if _e.get("som") in ("rumor_terra", "vento", "zumbido_vidro", "ar_escada", "grilos_loop", "quarto_loop", "sala_loop", "ar_sobe", "ofegante"): _e["db"] = min(_e.get("db", 0), _co)
    log = {"regra": REGRA, "perfil": perfil.get("handle")}

    # 1. faixas normalizadas
    if sem_voz:
        n = int(cfg["duracao_s"] * SR); voz = np.zeros((n, 2), np.float32); log["voz"] = "sem narração"
    else:
        voz = le(pasta / "voice.mp3", REGRA["voz_filtros"])
        voz = normaliza(voz, REGRA["voz_lufs"], REGRA["voz_tp"])
        n = max(len(voz), int((words[-1]["end"] + cfg["hold_final_s"]) * SR)); voz = no_tamanho(voz, n)
        log["voz"] = {"lufs": round(lufs(voz), 2), "tp": round(true_peak(voz), 2)}

    loop = le(ROOT / cfg["trilha"]); trilha = np.tile(loop, (n // len(loop) + 1, 1))[:n]
    trilha *= db(REGRA["trilha_lufs"] - lufs(loop))
    trilha *= db(cfg.get("trilha_db", 0))  # ajuste por edição (sfx.json → trilha_db)
    fi, fo = int(REGRA["trilha_fade_in_s"] * SR), max(int(REGRA["trilha_fade_out_s"] * SR), int(0.03 * SR))  # 0,03 s = corte seco sem clique
    if fi: trilha[:fi] *= (np.sin(np.linspace(0, np.pi / 2, fi)) ** 2)[:, None]
    trilha[-fo:] *= (np.cos(np.linspace(0, np.pi / 2, fo)) ** 2)[:, None] if fo > int(0.03 * SR) else np.linspace(1, 0, fo)[:, None]

    # 2. ducking
    fala, trechos = mascara_fala(words, n, REGRA["duck_juntar_s"])
    env = envelope_duck(fala, REGRA["duck_db"], REGRA["ataque_s"], REGRA["release_s"]); trilha *= env
    env_db = 20 * np.log10(env[::SR // 100, 0] + 1e-9); duck_db_s = float(np.max(np.abs(np.diff(env_db))) * 100) if len(env_db) > 1 else 0.0  # maior variação da trilha, dB/s

    sfx = np.zeros((n, 2), np.float32)
    chave = [w for w in words if norm(w["w"]) in {norm(c) for c in cfg["palavras_chave"]}]
    amb = cfg.get("ambiente")  # som de ambiente contínuo (quarto, mar, grilos), em loop e baixinho o vídeo todo (SFX ambientados)
    if amb:
        aa = ROOT / cfg["pasta_sons"] / f'{amb["som"]}.wav'
        a = le(aa if aa.exists() or not cfg.get("pasta_sons_base") else ROOT / cfg["pasta_sons_base"] / f'{amb["som"]}.wav'); a = np.tile(a, (n // len(a) + 1, 1))[:n]
        a *= db(amb.get("db", -14)) / (np.max(np.abs(a)) + 1e-9) * db(REGRA["sfx_pico"])
        fa = int(2.0 * SR); a[:fa] *= (np.sin(np.linspace(0, np.pi / 2, fa)) ** 2)[:, None]; a[-fa:] *= (np.cos(np.linspace(0, np.pi / 2, fa)) ** 2)[:, None]
        sfx += a
    for ev in cfg["eventos"]:
        arq = ROOT / cfg["pasta_sons"] / f'{ev["som"]}.wav'  # kit da edição (sfx/kits/<kit>); som que o kit não tem vem da pasta base
        if not arq.exists() and cfg.get("pasta_sons_base"): arq = ROOT / cfg["pasta_sons_base"] / f'{ev["som"]}.wav'
        s = le(arq); corte = int(ev.get("cauda_s", REGRA["sfx_cauda_s"]) * SR)  # cauda_s por evento (carro passando inteiro)
        if "ate" in ev:  # cama num trecho (ex.: chuva só nas cenas molhadas): o som repete em loop até "ate", com fade nas pontas
            m = int((ev["ate"] - ev["t"]) * SR); s = np.tile(s, (m // len(s) + 1, 1))[:m]; f = min(int(ev.get("fade_s", 1.0) * SR), m // 2)
            s[:f] *= (np.sin(np.linspace(0, np.pi / 2, f)) ** 2)[:, None]; s[-f:] *= (np.cos(np.linspace(0, np.pi / 2, f)) ** 2)[:, None]
        elif len(s) > corte: s = s[:corte]; f = int(0.25 * SR); s[-f:] *= np.linspace(1, 0, f)[:, None]  # cauda cortada sai em fade, nunca seca
        if REGRA.get("sfx_rms_norm"):  # nível por LOUDNESS (rms da parte ativa), não por pico; o "db" do evento vale como antes
            ativo = np.abs(s).max(axis=1) > np.max(np.abs(s)) * 0.03; rms = np.sqrt(np.mean(s[ativo] ** 2)) if ativo.any() else 1e-9
            s *= db(REGRA["sfx_pico"] + ev.get("db", 0) - REGRA.get("sfx_crest_db", 12)) / (rms + 1e-9)
        else:
            s *= db(REGRA["sfx_pico"] + ev.get("db", 0)) / (np.max(np.abs(s)) + 1e-9)  # db por evento: SFX por baixo da voz quando cai em cima dela
        t0, t1 = ev["t"], ev["t"] + len(s) / SR
        if any(w["start"] < t1 and t0 < w["end"] for w in chave): s *= db(REGRA["sfx_chave_db"]); ev["em_palavra_chave"] = True
        i = int(t0 * SR); j = min(i + len(s), n); sfx[i:j] += s[:j - i]

    if REGRA.get("sfx_comp_thr") is not None:  # compressor no barramento dos efeitos: nenhum som "explode" acima do resto
        thr, rt = REGRA["sfx_comp_thr"], REGRA.get("sfx_comp_ratio", 4.0); B = 64
        nb = len(sfx) // B; pk = np.abs(sfx[:nb * B]).max(axis=1).reshape(nb, B).max(axis=1)
        gr = np.minimum(0.0, -(20 * np.log10(pk + 1e-9) - thr) * (1 - 1 / rt)); gr = np.where(pk > 0, gr, 0.0)
        ca, cr = np.exp(-1 / (0.004 * SR / B)), np.exp(-1 / (0.15 * SR / B)); sm = np.zeros(nb); g = 0.0
        for i in range(nb):
            x = gr[i]; g = x + (g - x) * (ca if x < g else cr); sm[i] = g
        # olha à frente: o ganho já desce 2 blocos antes do pico
        sm = np.minimum(sm, np.r_[sm[2:], 0, 0]) if nb > 2 else sm
        gfull = np.repeat(db(sm), B); gfull = np.r_[gfull, np.ones(len(sfx) - len(gfull))]; sfx = sfx * gfull[:, None].astype(np.float32)
    # 3. master: soma → limiter → −14 LUFS (mede, aplica, limita, confere)
    soma = voz + trilha + sfx
    soma = normaliza(soma, REGRA["final_lufs"], REGRA["limiter_tp"])
    g_total = 20 * np.log10(np.sqrt(np.mean(soma ** 2)) / np.sqrt(np.mean((voz + trilha + sfx) ** 2)))
    stems = {k: v * db(g_total) for k, v in (("voz", voz), ("trilha", trilha), ("sfx", sfx))}
    for k, v in stems.items(): grava(pasta / "stems" / f"{k}.wav", v)
    grava(pasta / "mix.wav", soma)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pasta / "mix.wav"), "-c:a", "libmp3lame", "-b:a", "256k", str(pasta / "mix_preview.mp3")], check=True)

    # 4. gate
    if sem_voz:
        dif = np.array([99.0]); sfx_acima_ms = 0; taxa = 0.0; hyp = []
    else:
        Lv, Lt = k_momentaneo(stems["voz"]), k_momentaneo(stems["trilha"])  # janelas de 400 ms, passo 100 ms
        fala_gate = mascara_fala(words, n)[0]  # o gate mede só onde há palavra (a máscara do ducking pode juntar pausas longas)
        jan_fala = np.array([fala_gate[int(i * 0.1 * SR):int(i * 0.1 * SR + 0.4 * SR)].mean() >= 0.8 for i in range(len(Lv))])
        voz_soando = Lv > lufs(stems["voz"]) - 15  # tira os respiros entre palavras dentro de um trecho
        dif = (Lv - Lt)[jan_fala & voz_soando]
        # SFX × voz em janelas curtas de 100 ms, só onde há fala
        Lv1, Ls1 = k_momentaneo(stems["voz"], 0.1, 0.1), k_momentaneo(stems["sfx"], 0.1, 0.1)
        fala1 = np.array([fala_gate[int(i * 0.1 * SR):int((i + 1) * 0.1 * SR)].any() for i in range(len(Lv1))])  # só onde há palavra (a máscara do ducking junta pausas)
        seq = pior = 0
        for a in (Ls1 > Lv1) & fala1:
            seq = seq + 1 if a else 0; pior = max(pior, seq)
        sfx_acima_ms = pior * 100

        from faster_whisper import WhisperModel
        segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(pcm16k(pasta / "mix.wav"), language="en", beam_size=5)
        hyp = [w for s in segs for w in re.split(r"\s+|\.\.\.|…", s.text) if norm(w)]
        hyp = [h[0] for h in junta_numeros([(w, 0, 0) for w in hyp])]
        alin = pasta / "narracao_alinhamento.txt"  # mesmo texto na grafia do Whisper ("T. rex" × "T-rex"), quando a edição precisou
        ref = palavras_roteiro((alin if alin.exists() else pasta / "narracao.txt").read_text(encoding="utf-8"))
        # número por extenso no roteiro x dígito do Whisper ("Day one" → "Day 1", "six-forty" → "640") não é erro de fala
        def numero(w):
            partes = [p for p in re.split(r"-", w.lower().strip(".,:;!?")) if p]
            if partes and all(p in NUM for p in partes):
                v = [NUM[p] for p in partes]
                return str(sum(v)) if len(v) == 2 and v[0] >= 20 and v[1] < 10 else "".join(map(str, v))
            return w
        # os dois lados passam pelo numero(): Whisper que escreve "One… Two… Three" por extenso não pode contar como erro
        taxa = wer([norm(numero(w)) for w in ref], [norm(numero(w)) for w in hyp])

    sil = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(pasta / "mix.wav"), "-af", "silencedetect=n=-50dB:d=2", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    final_lufs, final_tp = lufs(soma), true_peak(soma)
    log.update({
        "duracao_s": round(n / SR, 2), "trechos_de_fala": len(trechos), "ganho_master_db": round(g_total, 2),
        "final_lufs": round(final_lufs, 2), "final_tp_dbtp": round(final_tp, 2),
        "voz_menos_trilha_lu": {"min": round(float(dif.min()), 1), "p10": round(float(np.percentile(dif, 10)), 1), "mediana": round(float(np.median(dif)), 1)},
        "sfx_acima_da_voz_max_ms": sfx_acima_ms, "trilha_max_db_s": round(duck_db_s, 1), "wer_mix": round(taxa, 4),
        "silencios_maiores_2s": [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sil)],
        "transcricao_mix": " ".join(hyp), "eventos_sfx": cfg["eventos"]})
    log["gate"] = {
        "lufs_ok": REGRA["final_lufs"] - 1 <= final_lufs <= REGRA["final_lufs"] + 1, "pico_ok": final_tp <= -1.0, "voz_trilha_ok": float(np.percentile(dif, 10)) >= REGRA["voz_trilha_p10"] and float(np.median(dif)) >= REGRA["voz_trilha_mediana"],
        "sfx_ok": sfx_acima_ms <= 300,
        "ducking_suave_ok": duck_db_s <= REGRA.get("duck_max_db_s", 99),  # a música não pode subir/descer brusco
        "respiracao_com_som_ok": not REGRA.get("respiracao_sfx") or sum(1 for e in cfg["eventos"] if e["som"] in REGRA["respiracao_sfx"]) >= sum(1 for a_, b_ in zip(words, words[1:]) if norm(a_["w"]) == "breathe" and norm(b_["w"]) in ("in", "out")),
        "ambiente_ok": not REGRA.get("ambiente_obrigatorio") or bool(cfg.get("ambiente")),
        # sons proibidos do perfil (perfil.yaml → audio.sfx_proibidos)
        "sfx_proibidos_ok": not any(e["som"] in REGRA.get("sfx_proibidos", []) for e in cfg["eventos"]),
        # háptico pelo alto-falante (só perfil com audio.haptico_sfx)
        "haptico_ok": not REGRA.get("haptico_sfx") or sum(1 for e in cfg["eventos"] if e["som"] in REGRA["haptico_sfx"]) >= max(2, sum(1 for a_, b_ in zip(words, words[1:]) if norm(a_["w"]) == "breathe" and norm(b_["w"]) in ("in", "out"))),
        "som_por_plano_ok": all("sfx" in s for s in (json.loads((pasta / "script.json").read_text(encoding="utf-8")).get("shots") or [])) if REGRA.get("som_por_plano") else True, "whisper_ok": taxa < 0.05, "silencio_ok": not log["silencios_maiores_2s"]}
    log["passou"] = all(log["gate"].values())
    log = json.loads(json.dumps(log, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (pasta / "mix_check.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in log.items() if k not in ("eventos_sfx", "regra")}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main(sys.argv[1])
