"""Etapa 3 · Voz: words.json e conferência com o Whisper (faster-whisper).
Uso:  python _sistema/orquestrador/voz_words.py <voice.mp3> <texto.txt> <pasta_saida> [--modelo small.en]
O texto é a narração enviada ao ElevenLabs; tags entre [colchetes] são ignoradas.
Grava words.json (palavras do roteiro com tempos do Whisper) e voz_check.json (WER, duração, silêncios)."""
import argparse, json, pathlib, re, subprocess, difflib
import numpy as np
from faster_whisper import WhisperModel

def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower().replace(",", ""))

NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
NUM.update({w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)})
ESCALA = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}

def junta_numeros(hyp):
    """'three thousand' do Whisper vira um item '3000' com o tempo das palavras somadas."""
    # o Whisper às vezes parte "2,000" em "2" + ",000" : junta de volta antes de tudo
    colado = []
    for h in hyp:
        if colado and re.fullmatch(r",\d{3}[.,?!]*", h[0]) and re.fullmatch(r"\d{1,3}(,\d{3})*", colado[-1][0]):
            colado[-1] = (colado[-1][0] + h[0], colado[-1][1], h[2])
        else: colado.append(h)
    hyp = colado
    out, i = [], 0
    while i < len(hyp):
        j, total, atual = i, 0, 0
        while j < len(hyp) and (norm(hyp[j][0]) in NUM or norm(hyp[j][0]) in ESCALA):
            n = norm(hyp[j][0])
            if n in NUM: atual += NUM[n]
            elif n == "hundred": atual *= 100
            else: total += max(atual, 1) * ESCALA[n]; atual = 0
            j += 1
        so_escala = all(norm(h[0]) in ESCALA for h in hyp[i:j]) and i > 0 and re.fullmatch(r"[\d,.]+", hyp[i - 1][0])
        if j > i and any(norm(h[0]) in ESCALA for h in hyp[i:j]) and not so_escala:  # "150 million": o Whisper já deu os dígitos, "million" fica palavra
            out.append((str(total + atual), hyp[i][1], hyp[j - 1][2])); i = j
        else:
            out.append(hyp[i]); i += 1
    return out

def encaixa_silencios(words, sil):
    """Bordas das palavras presas aos silêncios reais: palavra que atravessa uma pausa fica do lado onde tem mais fala;
    sem pausa entre duas palavras, uma termina onde a outra começa."""
    for w in words:
        for s0, s1 in sil:
            if w["start"] < s0 and s1 < w["end"]:
                if s0 - w["start"] >= w["end"] - s1: w["end"] = s0
                else: w["start"] = s1
            elif s0 <= w["start"] < s1: w["start"] = s1
            elif s0 < w["end"] <= s1: w["end"] = s0
    for a, b in zip(words, words[1:]):
        pausa = next(((s0, s1) for s0, s1 in sil if a["end"] - 0.05 <= s0 and s1 <= b["start"] + 0.05), None)
        if pausa: a["end"], b["start"] = max(a["end"], pausa[0]), min(b["start"], pausa[1])
        else: a["end"] = b["start"] = round((a["end"] + b["start"]) / 2, 3) if a["end"] > b["start"] else b["start"]
    for w in words:
        w["start"], w["end"] = round(w["start"], 3), round(max(w["end"], w["start"] + 0.06), 3)
    return words

def pausas(audio, minimo=0.2):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", f"silencedetect=n=-38dB:d={minimo}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    ini = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    fim = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(ini, fim))

def palavras_roteiro(texto):
    texto = re.sub(r"\[[^\]]*\]", " ", texto).replace("—", " ").replace("...", " ").replace("…", " ")
    return [w for w in texto.split() if norm(w)]

def mesma_palavra(r, h):
    """Igual, ou só grafia diferente da mesma palavra (archaeologists × archeologists)."""
    return r == h or (min(len(r), len(h)) >= 6 and difflib.SequenceMatcher(None, r, h).ratio() >= 0.9)

def wer(ref, hyp):
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (not mesma_palavra(r, h)))
    return d[-1] / max(len(ref), 1)

def silencios(audio, limite=2.0):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", f"silencedetect=n=-40dB:d={limite}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", out)]

def pcm16k(audio):
    # decodifica pelo ffmpeg (não depende da versão do PyAV usada pelo faster-whisper)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def duracao(audio):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                                capture_output=True, text=True).stdout)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("audio"); ap.add_argument("texto"); ap.add_argument("saida")
    ap.add_argument("--modelo", default="small.en"); a = ap.parse_args()
    saida = pathlib.Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    ref = palavras_roteiro(pathlib.Path(a.texto).read_text(encoding="utf-8"))

    modelo = WhisperModel(a.modelo, device="cpu", compute_type="int8")
    segs, _ = modelo.transcribe(pcm16k(a.audio), language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    hyp = junta_numeros([(w.word.strip(), round(w.start, 3), round(w.end, 3)) for s in segs for w in s.words])

    # alinha as palavras do roteiro às do Whisper (grafia do roteiro, tempo do Whisper)
    # "10 %" do Whisper: o "%" solto não é palavra (norm vazio) e inflava o WER
    hyp = [h for h in hyp if norm(h[0])]
    rn, hn = [norm(w) for w in ref], [norm(w) for w, _, _ in hyp]
    # "Thank you" alucinado pelo Whisper depois da última palavra do roteiro não é erro da voz
    if rn and rn[-1] in hn:
        corte = len(hn) - hn[::-1].index(rn[-1])
        hyp, hn = hyp[:corte], hn[:corte]
    tempos = [None] * len(ref)
    for bloco in difflib.SequenceMatcher(None, rn, hn, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            tempos[bloco.a + k] = hyp[bloco.b + k][1:]
    # palavras sem par (ex.: número dito por extenso) ficam entre os vizinhos
    for i, t in enumerate(tempos):
        if t is None:
            ini = next((tempos[j][1] for j in range(i - 1, -1, -1) if tempos[j]), 0.0)
            fim = next((tempos[j][0] for j in range(i + 1, len(tempos)) if tempos[j]), ini + 0.3)
            tempos[i] = (ini, fim)
    words = encaixa_silencios([{"w": w, "start": s, "end": e} for w, (s, e) in zip(ref, tempos)], pausas(a.audio))
    (saida / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")

    taxa = wer(rn, hn)
    sil = silencios(a.audio)
    ordem_ok = all(words[i]["start"] <= words[i + 1]["start"] and words[i]["end"] <= words[i + 1]["start"] + 0.05 for i in range(len(words) - 1))
    check = {"duracao_s": round(duracao(a.audio), 2), "palavras_roteiro": len(ref), "palavras_whisper": len(hyp),
             "wer": round(taxa, 4), "wer_ok": taxa < 0.05, "silencios_maiores_2s": sil, "silencio_ok": not sil,
             "tempos_em_ordem": ordem_ok, "sem_par_no_whisper": sum(1 for b in rn if b not in hn),
             "transcricao_whisper": " ".join(w for w, _, _ in hyp)}
    (saida / "voz_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
