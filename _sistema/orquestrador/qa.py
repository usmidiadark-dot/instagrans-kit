"""Etapa 06 · QA visual (_sistema/contratos/06_qa.md).
  python _sistema/orquestrador/qa.py preparar <pasta>   → qa/ com frames por plano (tempo marcado), folha, capa e prompt.md
  python _sistema/orquestrador/qa.py julgar <pasta>     → lê qa/notas.json (do subagente), valida, recalcula a média e grava qa.json
A nota é dada por um subagente que não viu a produção (review-checklist.md); o veredito é calculado aqui, pelas regras."""
import json, pathlib, re, shutil, subprocess, sys
import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from perfis_cfg import carrega
ITENS = {  # chave: (peso, descrição). Texto próprio do perfil: <perfil>/qa_itens.json; da edição: script.json → qa_itens
    "assunto_reconhecivel": (2, "Assunto reconhecível de cara: sem som e sem legenda, dá pra dizer o que é em 1 segundo"),
    "fundo_vivo": (2, "Fundo bonito e vivo: colorido na paleta do perfil, com luz e algo em movimento; nunca escuro chapado (salvo se o guia do perfil pede)"),
    "estilo_guia": (1, "Estilo do guia do perfil: traço, paleta e tipografia como no style-guide.md e nas referências"),
    "camera_profundidade": (1, "Profundidade de câmera (camadas, paralaxe) e planos variados"),
    "capa": (1, "Capa: quadro do MOMENTO DA AÇÃO do título, nunca quadro neutro; texto da capa nunca contradiz a imagem; nada solto voando por cima; assunto grande e claro + texto legível; SEM defeito de montagem: borda/faixa vazia ou escura dentro de moldura, imagem que não preenche o quadro, recorte errado, texto cortado ou fora do corte 3:4 (abra os 4 zooms capa_zoom_*.jpg e a capa_grade.jpg)"),
    "texto_legivel": (1, "Texto legível e dentro da área segura do feed: corte 4:5 (y 285–1635 no quadro 1080×1920), fora da coluna de botões (x > 950 abaixo de y 1000); sem cobrir rosto ou assunto; sem amontoar (além da HUD e da legenda, no máximo 2 inserts juntos)"),
    "apoiado_na_cena": (1, "Personagem/objeto apoiado na cena (nada flutuando sem motivo)"),
    "ritmo": (1, "Ritmo: algo muda a cada 1,5–3 s"),
    "acao_insert": (1, "Ação → reforço na tela: cada gesto/ação/dado da narração tem um insert, card ou movimento no mesmo trecho, grande e integrado à cena (adesivo pequeno voando = nota ≤ 5); há peças novas ligadas ao roteiro; o fundo tem algo se mexendo. Nota ≤ 6 se uma ação passa sem reforço ou a cena parece parada"),
}
ITEM_HUD = (1, "HUD do perfil presente e no estilo do vídeo, com dados que mudam junto com a narração; inserts de dado legíveis; legenda dinâmica e limpa; animação sem piscadas (nada que aparece e some rápido ou some e volta)")
CORTE_PADRAO = 6.8   # nota de corte da média e de cada item com gate (perfil.yaml → qa.corte; padrão em perfis.yaml → padrao.qa.corte)


def opc_qa(perfil, chave, padrao=None):
    """Valor pontilhado do perfil.yaml do perfil (pasta); senão de perfis.yaml → padrao; senão `padrao`."""
    cfg = carrega(ROOT); p = next((x for x in cfg["perfis"] if x.get("pasta") == perfil), {})
    for fonte in (p, cfg.get("padrao") or {}):
        v = fonte
        for k in chave.split("."):
            v = v.get(k) if isinstance(v, dict) else None
            if v is None: break
        if v is not None: return v
    return padrao

SEGUIR_QA = (chr(10) + "4. Esta edição tem a PAUSA/CARD DE SEGUIR (script.seguir): um card pedindo para SEGUIR o perfil. Ele É previsto e correto. "
              "NÃO há palavra para comentar nem 'comment' no lugar dele: desconte se aparecer; não desconte o card de seguir.")
SEM_CTA_QA = (chr(10) + "4. Esta edição sai SEM CTA de propósito: NÃO há palavra para comentar nem 'comment'. "
              "Não desconte card de comentário ausente; desconte se o vídeo parece terminar do nada ou se aparece alguma chamada para comentar.")
def itens_do_perfil(perfil):
    """Textos de avaliação próprios do perfil: <perfil>/qa_itens.json ({item: descrição}). Sem o arquivo = só os itens comuns."""
    f = ROOT / perfil / "qa_itens.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-1500:])

# item opcional por edição (script.json → qa_variacao: true): a edição não pode repetir as anteriores da série
ITEM_VARIACAO = (1, "Variação em relação às 3 edições anteriores (veja comparativo.jpg: esta edição na 1ª linha, as 3 anteriores abaixo): gancho, fundo, HUD, layout do texto, acabamento, câmera e transições têm de parecer OUTRO vídeo do mesmo estilo, não o mesmo vídeo com um detalhe trocado. 10 = quase tudo muda, mantendo a identidade do perfil; ≤ 6 se o gancho, o fundo ou a HUD repetem o do comparativo")

def itens_do(script, perfil=None):
    it = dict(ITENS)
    if perfil is None or opc_qa(perfil, "qualidade.hud", False): it["hud_interativa"] = ITEM_HUD   # HUD só é cobrada no perfil com qualidade.hud: true
    if script.get("qa_variacao"): it["variacao"] = ITEM_VARIACAO
    return it

PASSO_QA = 0.5   # segundos entre os frames do QA
N_AVALIACOES = 3   # avaliações independentes por rodada (valem a MEDIANA por item)

def bloco_recorrentes(pasta, perfil):
    """Defeitos recorrentes + gate comum no prompt dos avaliadores (quando os mesmos defeitos voltam a cada vídeo).
    Plugin opcional do perfil: <perfil>/reviews/licoes_recorrentes.md (linhas numeradas) e/ou <perfil>/gate_comum.py <pasta> (grava gate_comum.json
    {ok, criticos[], avisos[]}); sem eles devolve "".
    Roda o gate comum se o gate_comum.json não existir ou for mais velho que o video.mp4 (não reprova aqui: o resultado vai para o avaliador conferir)."""
    partes = []
    lic = ROOT / perfil / "reviews" / "licoes_recorrentes.md"
    if lic.exists():
        linhas = [l.strip() for l in lic.read_text(encoding="utf-8").splitlines() if l.strip()[:1].isdigit()]
        if linhas:
            partes.append("A. DEFEITOS RECORRENTES deste perfil (já voltaram em vídeos anteriores; procure CADA um nos frames e cite o frame se achar; "
                          "CRÔNICA = voltou 3+ vezes):\n" + "\n".join("   - " + re.sub(r" · chave: [\w-]+", "", l.split("] ", 1)[-1]) for l in linhas))
    gate = ROOT / perfil / "gate_comum.py"; gj = pasta / "gate_comum.json"
    fontes = [pasta / n for n in ("video.mp4", "video_sem_audio.mp4", "cover.jpg", "sfx.json", "gate_comum_excecoes.json") if (pasta / n).exists()]
    novo = max((f.stat().st_mtime for f in fontes), default=0)
    if gate.exists() and (not gj.exists() or gj.stat().st_mtime < novo):   # resultado velho (vídeo/capa/som refeitos) = roda de novo
        try: subprocess.run([sys.executable, str(gate), str(pasta)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        except subprocess.TimeoutExpired: print("aviso: gate_comum.py passou de 10 min; prompt sai com o resultado anterior (se houver)", file=sys.stderr)
    if gj.exists():
        g = json.loads(gj.read_text(encoding="utf-8"))
        achados = [f"CRÍTICO: {c}" for c in g.get("criticos", [])] + [f"aviso: {c}" for c in g.get("avisos", [])]
        partes.append("B. O GATE AUTOMÁTICO (gate_comum.py, por pixel, " + ("APROVOU" if g.get("ok") else "REPROVOU") + ") achou: "
                      + ("\n" + "\n".join("   - " + a for a in achados) if achados else "nada.")
                      + "\n   Verifique CADA ponto nos frames do tempo indicado (abra também `" + (pasta / "gate_comum_folha.jpg").as_posix() + "` se existir) e diga nas "
                      "evidências se confirma ou se é falso positivo. O gate NÃO mede andar, queda/escorregão nem gesto final: esses são com você.")
    return ("\n" + "\n".join(partes)) if partes else ""

def preparar(pasta):
    # capa medida pelo render.py (capa_check.py): reprovada aqui não abre rodada de QA (conserta antes, sem gastar nenhuma das 5)
    cc = pasta / "capa_check.json"
    if cc.exists() and not json.loads(cc.read_text(encoding="utf-8")).get("ok", True):
        sys.exit("capa reprovada na checagem antes do QA (capa_check.json):\n- " + "\n- ".join(json.loads(cc.read_text(encoding="utf-8"))["problemas"])
                 + "\nConserte script.capa e rode de novo: python _sistema/orquestrador/render.py <pasta> --so-capa")
    perfil = pasta.relative_to(ROOT).parts[0]
    if opc_qa(perfil, "qa.cronicos", False):   # plugin <perfil>/cronicos.py → checar(pasta) -> {ok, graves[], avisos[]}: itens crônicos conferidos antes da rodada
        arq = ROOT / perfil / "cronicos.py"
        if not arq.exists(): sys.exit(f"qa.cronicos: true, mas falta {arq.relative_to(ROOT)} (função checar(pasta) -> {{ok, graves, avisos}})")
        import importlib.util
        spec = importlib.util.spec_from_file_location("cronicos_" + perfil.replace("-", "_"), arq); cronicos = importlib.util.module_from_spec(spec); spec.loader.exec_module(cronicos)
        cr = cronicos.checar(pasta)
        for a_ in cr.get("avisos", []): print("aviso (cronicos):", a_, file=sys.stderr)
        if not cr.get("ok"): sys.exit("itens crônicos reprovados antes do QA:" + chr(10) + "- " + (chr(10) + "- ").join(cr.get("graves", [])) + chr(10) + "Conserte e rode render.py de novo.")
    qa = pasta / "qa"; shutil.rmtree(qa, ignore_errors=True); (qa / "frames").mkdir(parents=True)
    script = json.loads((pasta / "script.json").read_text(encoding="utf-8"))
    lista = []
    dur_video = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(pasta / "video.mp4")],
                                     capture_output=True, text=True).stdout)
    # frames em pontos FIXOS (25/10/2026): 1 a cada 0,5 s do vídeo todo (não mais 3 por plano, que caíam em pontos diferentes a cada render
    # e faziam o avaliador ver momentos diferentes da mesma animação); cada frame leva o plano em que cai.
    shots = script["shots"]
    def plano_de(t):
        for s_ in shots:
            if s_["t_start"] <= t < s_["t_end"]: return s_
        return shots[-1] if t >= shots[-1]["t_start"] else shots[0]
    passo = float(script.get("qa_passo", PASSO_QA))   # opcional (26/10/2026): vídeo longo = passo maior; o padrão continua 0,5 s
    n = int((dur_video - 0.15) / passo)
    tempos = [round(passo * k, 2) for k in range(1, n + 1)]
    if dur_video - 0.15 - tempos[-1] > 0.2: tempos.append(round(dur_video - 0.15, 2))
    for t in tempos:
        s = plano_de(t); nome = f'p{s["n"]}_{t:05.2f}s.jpg'
        sh("ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(pasta / "video.mp4"), "-frames:v", "1", "-vf", "scale=540:-1", "-q:v", "3", str(qa / "frames" / nome))
        lista.append({"arquivo": f"frames/{nome}", "plano": s["n"], "t": round(t, 2), "cena": s.get("cena"), "vo": s.get("vo"),
                      "previsto": s.get("layers", []), "camera": s["camera"]["plane"]})
    for s in shots:
        # momentos-chave do plano (insert, tarja, card): 1 frame no meio de cada um (opcional: script.json → shots[].momentos)
        for m in s.get("momentos", []):
            t = min(m["t"], dur_video - 0.15); nome = f'p{s["n"]}_{t:05.2f}s_m.jpg'
            sh("ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(pasta / "video.mp4"), "-frames:v", "1", "-vf", "scale=540:-1", "-q:v", "3", str(qa / "frames" / nome))
            lista.append({"arquivo": f"frames/{nome}", "plano": s["n"], "t": round(t, 2), "cena": s.get("cena"), "vo": s.get("vo"),
                          "previsto": s.get("layers", []), "momento": m.get("o_que"), "camera": s["camera"]["plane"]})
    shutil.copy(pasta / "cover.jpg", qa / "cover.jpg"); shutil.copy(pasta / "sheet.jpg", qa / "sheet.jpg")
    if (pasta / "comparativo.jpg").exists(): shutil.copy(pasta / "comparativo.jpg", qa / "comparativo.jpg")   # variação: esta edição x as 3 anteriores da série
    if (pasta / "capa_grade.jpg").exists(): shutil.copy(pasta / "capa_grade.jpg", qa / "capa_grade.jpg")  # a capa como aparece na grade do Instagram (ícone de reel e views por cima)
    # capa em 4 zooms na resolução cheia (defeito pequeno de montagem passa despercebido na capa inteira)
    for k, (x, y) in enumerate([(0, 0), (540, 0), (0, 960), (540, 960)], 1):
        sh("ffmpeg", "-v", "error", "-y", "-i", str(pasta / "cover.jpg"), "-vf", f"crop=540:960:{x}:{y}", "-q:v", "2", str(qa / f"capa_zoom_{k}.jpg"))
    (qa / "frames.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    ITENS_A = itens_do(script, perfil)
    desc = {k: d for k, (_, d) in ITENS_A.items()}
    desc.update(itens_do_perfil(perfil))
    desc.update(script.get("qa_itens", {}))   # opcional: descrição própria por edição/estilo
    itens = "\n".join(f'- `{k}` (peso {p}): {desc[k]}' for k, (p, _) in ITENS_A.items())
    prompt = f"""Você é o QA visual do perfil {script.get("profile", perfil)}. Avalie o vídeo "{script["title"]}" só pelas imagens, com rigor: este vídeo vai ser postado sem revisão humana.

Leia nesta ordem:
1. Regras: `{(ROOT / script["qa_guia"]).as_posix() if script.get("qa_guia") else (ROOT / perfil / "style-guide.md").as_posix()}` (seção "Regras do estúdio" vale acima do resto; leia a lista "Nunca").
2. Imagens em `{qa.as_posix()}/`: `cover.jpg` (capa) `capa_grade.jpg` (a capa na grade do Instagram, com o ícone de reel e as views por cima), `capa_zoom_1..4.jpg` (os 4 quartos da capa em tamanho real: procure bordas, faixas escuras ou vazias dentro de molduras, partes que não preenchem, cortes), `sheet.jpg` (12 quadros do vídeo inteiro, em ordem) {"o comparativo da variação `comparativo.jpg` (esta edição na 1ª linha, as 3 anteriores da série abaixo), " if script.get("qa_variacao") else ""}e os frames em `frames/` (lista com plano, tempo e narração em `frames.json`). Abra TODOS os frames.
3. Elenco do roteiro: {json.dumps(script.get("cast", []), ensure_ascii=False)}{SEGUIR_QA if script.get("seguir") else (SEM_CTA_QA if (script.get("sem_cta") or script.get("cta") is False) else "")}
{bloco_recorrentes(pasta, perfil)}

Precisão (este vídeo tem no máximo 5 rodadas de QA; cada apontamento errado custa uma rodada):
- `frames.json` traz, para cada frame, o que o roteiro prevê ("previsto"). Elementos previstos são intencionais: avalie se ficaram CLAROS, não se deveriam existir. Ex.: personagem levando um copo à boca é ação prevista, não "glitch".
- Movimento existe entre frames (porta deslizando, objeto voando, texto entrando letra por letra): um frame no meio de uma animação não é defeito; compare com o frame seguinte do mesmo plano.
- Só aponte o que um espectador perceberia em velocidade normal no celular. Para cada problema, diga a correção exata.

Dê nota de 0 a 10 a cada item, citando como evidência o arquivo do frame (ex.: p3_05.00s.jpg):
{itens}

Liste também cada item da lista "Nunca" do style-guide que o vídeo viola (texto curto + frame). Lista vazia se nenhum.

Grave SOMENTE este JSON em `{(qa / "notas.json").as_posix()}`:
{{"scores": {{{", ".join(f'"{k}": 0' for k in ITENS_A)}}},
 "evidencias": {{"<item>": "frame + o que você viu"}},
 "never_violations": [],
 "melhorias": ["o que mais subiria a nota, em ordem de impacto"],
 "frames_abertos": ["todos os arquivos de frames/ que você abriu"],
 "notes": "resumo em 2 frases"}}
Não edite nenhum outro arquivo. Responda no fim só com as notas em uma linha."""
    (qa / "prompt.md").write_text(prompt, encoding="utf-8")
    alvo = (qa / "notas.json").as_posix()
    for k in range(2, N_AVALIACOES + 1):   # mesmos frames, avaliadores independentes (1 subagente por prompt, sem ver as notas dos outros)
        (qa / f"prompt_{k}.md").write_text(prompt.replace(alvo, (qa / f"notas_{k}.json").as_posix()), encoding="utf-8")
    print(f"pacote pronto: {qa} ({len(lista)} frames). Rode {N_AVALIACOES} subagentes de QA independentes, um por prompt: prompt.md -> notas.json, " + ", ".join(f"prompt_{k}.md -> notas_{k}.json" for k in range(2, N_AVALIACOES + 1)) + "; depois qa.py julgar (vale a mediana por item).")

def registra_rodada(pasta, ev, qa, tokens=None):
    """Registro de cada rodada de QA válida (28/10/2026; antes só ficava a última e o custo nunca foi medido): <perfil>/reviews/qa_rodadas.jsonl
    (edição, rodada, notas, média, gates que falharam, nº de apontamentos, tokens quando informados) e cópia das notas em qa/historico/rodada-NN/.
    A mesma nota julgada de novo não cria rodada nova (só atualiza os tokens)."""
    import datetime, hashlib
    arq = pasta.parent.parent / "reviews" / "qa_rodadas.jsonl"; arq.parent.mkdir(exist_ok=True)
    linhas = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()] if arq.exists() else []
    h = hashlib.sha1(json.dumps([e["scores"] for e in ev], sort_keys=True).encode()).hexdigest()[:12]
    mesmas = [i for i, l in enumerate(linhas) if l["edicao"] == pasta.name and l["hash"] == h]
    if mesmas:
        if tokens:
            linhas[mesmas[-1]]["tokens"] = tokens
            arq.write_text("".join(json.dumps(l, ensure_ascii=False) + chr(10) for l in linhas), encoding="utf-8")
        return
    n = sum(l["edicao"] == pasta.name for l in linhas) + 1
    try: frames = len(json.loads((pasta / "qa" / "frames.json").read_text(encoding="utf-8")))
    except Exception: frames = None
    rec = {"edicao": pasta.name, "rodada": n, "quando": datetime.datetime.now().isoformat(timespec="seconds"), "avaliacoes": len(ev), "frames": frames,
           "scores": qa["scores"], "media": qa["media_ponderada"], "verdict": qa["verdict"], "gates_falhos": [k for k, v in qa["gate"].items() if not v],
           "apontamentos": len(qa.get("melhorias", [])), "tokens": tokens, "hash": h}
    with arq.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + chr(10))
    hist = pasta / "qa_historico" / f"rodada-{n:02d}"; hist.mkdir(parents=True, exist_ok=True)
    for f_ in (pasta / "qa").glob("notas*.json"): shutil.copy2(f_, hist / f_.name)

def le_json(p):
    """Lê o JSON de notas de um revisor. Subagentes no Windows às vezes gravam em cp1252 (acento vira byte solto): tenta UTF-8 e cai para cp1252 (28/10/2026)."""
    raw = pathlib.Path(p).read_bytes()
    try: return json.loads(raw.decode("utf-8-sig"))
    except UnicodeDecodeError: return json.loads(raw.decode("cp1252"))

def julgar(pasta, tokens=None):
    notas = le_json(pasta / "qa" / "notas.json")
    perfil = pasta.relative_to(ROOT).parts[0]
    ITENS_A = itens_do(json.loads((pasta / "script.json").read_text(encoding="utf-8")), perfil)
    sc = notas["scores"]
    # mediana por item (25/10/2026): o avaliador oscila ~±0,3 entre rodadas do MESMO vídeo; N avaliações independentes (notas.json, notas_2.json, notas_3.json,
    # mesmos frames fixos) valem a MEDIANA por item (com 2 = média). Violações "Nunca" só contam se ≥ metade das avaliações apontarem.
    import statistics
    ev = [notas]
    for k in range(2, N_AVALIACOES + 1):
        f_ = pasta / "qa" / f"notas_{k}.json"
        if f_.exists():
            b_ = le_json(f_)
            if all(i in b_["scores"] for i in ITENS_A): ev.append(b_)
    if len(ev) > 1:
        sc = {k: round(statistics.median(e["scores"][k] for e in ev), 2) for k in ITENS_A}; notas["scores"] = sc
        todas = [v for e in ev for v in e.get("never_violations", [])]
        notas["never_violations"] = [v for v in dict.fromkeys(todas) if sum(v in e.get("never_violations", []) for e in ev) >= len(ev) / 2]
        notas["notes"] = (notas.get("notes", "") + f" | mediana de {len(ev)} avaliações: " + " / ".join(e.get("notes", "") for e in ev[1:])).strip()
        notas["melhorias"] = list(dict.fromkeys(m for e in ev for m in e.get("melhorias", [])))
        notas["evidencias"] = {**{k: v for e in ev[1:] for k, v in e.get("evidencias", {}).items()}, **notas.get("evidencias", {})}
    elif N_AVALIACOES > 1:
        print(f"AVISO: só 1 avaliação (esperadas {N_AVALIACOES}); a nota oscila ±0,3 — rode os prompt_2/3.md", file=sys.stderr)
    falta = [k for k in ITENS_A if k not in sc]
    if falta: sys.exit(f"notas sem os itens: {falta}")
    previstos = {f["arquivo"].split("/")[-1] for f in json.loads((pasta / "qa" / "frames.json").read_text(encoding="utf-8"))}
    abertos = {pathlib.Path(a).name for e in ev for a in e.get("frames_abertos", [])} if len(ev) > 1 else {pathlib.Path(a).name for a in notas.get("frames_abertos", [])}
    for i_, e in enumerate(ev, 1):
        fa = {pathlib.Path(a).name for a in e.get("frames_abertos", [])}
        if previstos - fa: sys.exit(f"QA incompleto: a avaliação {i_} não abriu {len(previstos - fa)} de {len(previstos)} frames; rode o subagente dela de novo")
    if previstos - abertos:  # avaliação incompleta não vale como rodada
        sys.exit(f"QA incompleto: o avaliador não abriu {len(previstos - abertos)} de {len(previstos)} frames; rode o subagente de novo")
    media = sum(sc[k] * p for k, (p, _) in ITENS_A.items()) / sum(p for p, _ in ITENS_A.values())
    # NOTA DE CORTE: a mesma para a média e para cada item com gate (perfil.yaml → qa.corte; padrão 6,8). A lista "nunca" vale sem nota.
    CORTE = float(opc_qa(perfil, "qa.corte", CORTE_PADRAO))
    gate = {"media_ok": media >= CORTE, "assunto_ok": sc["assunto_reconhecivel"] >= CORTE, "fundo_ok": sc["fundo_vivo"] >= CORTE, "acao_ok": sc.get("acao_insert", 10) >= CORTE,
            "capa_ok": sc["capa"] >= CORTE, "nunca_ok": not notas.get("never_violations"),
            **({"hud_ok": sc["hud_interativa"] >= CORTE} if "hud_interativa" in ITENS_A else {}), **({"variacao_ok": sc["variacao"] >= CORTE} if "variacao" in ITENS_A else {})}
    qa = {"scores": {k: sc[k] for k in ITENS_A}, "never_violations": notas.get("never_violations", []),
          "verdict": "pass" if all(gate.values()) else "fail",
          "notes": notas.get("notes", ""), "media_ponderada": round(media, 2), "gate": gate,
          "evidencias": notas.get("evidencias", {}), "melhorias": notas.get("melhorias", [])}
    jsonschema.validate(qa, json.loads((ROOT / "_sistema" / "schemas" / "qa.schema.json").read_text(encoding="utf-8")))
    (pasta / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: qa[k] for k in ("scores", "media_ponderada", "gate", "verdict", "never_violations")}, ensure_ascii=False, indent=1))

    try: registra_rodada(pasta, ev, qa, tokens)
    except Exception as e_: print(f"AVISO: rodada não registrada ({e_})", file=sys.stderr)

if __name__ == "__main__":
    # python qa.py julgar <pasta> [--tokens N]   N = soma dos tokens dos subagentes revisores (some os relatórios deles) → custo no registro
    cmd, pasta = sys.argv[1], pathlib.Path(sys.argv[2]).resolve()
    tk = int(sys.argv[sys.argv.index("--tokens") + 1]) if "--tokens" in sys.argv else None
    if cmd == "julgar": julgar(pasta, tk)
    else: {"preparar": preparar}[cmd](pasta)
