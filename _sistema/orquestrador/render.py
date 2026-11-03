"""Etapa 05 · render: Remotion (sem áudio) → mux com a mix → video.mp4, cover.jpg, sheet.jpg, render_check.json.
Uso (na raiz do projeto):  python _sistema/orquestrador/render.py <pasta_da_edicao> [--composicao X] [--so-capa] [--rascunho]
Lê da pasta: script.json, words.json, mix.wav (rodar mix.py antes). Gate: _sistema/contratos/05_render.md.
A composição (vídeo e capa) vem de <perfil>/perfil.yaml → composicao {edicao, capa, pos?, capa_sujeito?}; sem ela o render para.
Projeto Remotion do perfil: <perfil>/remotion (src/index.ts registra as composições)."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, json, pathlib, re, shutil, subprocess, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]

def porta_livre():
    """Porta livre para o servidor do Remotion: com várias sessões renderizando ao mesmo tempo (perfis diferentes), todas
    disputavam a 3000 e uma renderizava a composição da outra ("Could not find composition"). O sistema escolhe uma porta vaga."""
    import os, socket
    faixa = os.environ.get("REMOTION_PORTAS")   # opcional (28/10/2026): "3700-3799" = só portas dessa faixa (testes paralelos combinados por faixa)
    if faixa:
        a, b = map(int, faixa.split("-"))
        for porta in range(a, b + 1):
            with socket.socket() as s:
                try: s.bind(("127.0.0.1", porta)); return porta
                except OSError: continue
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode: sys.exit(f"falhou: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r

def probe(arq):
    return json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(arq)]).stdout)

def comp_do_perfil(perfil):
    p = next((x for x in carrega(ROOT)["perfis"] if x.get("pasta") == perfil), {})
    c = p.get("composicao")
    if not isinstance(c, dict) or not c.get("edicao"):
        sys.exit(f"render.py: o perfil '{perfil}' não tem composicao.edicao no perfil.yaml (ex.: composicao: {{edicao: Edicao, capa: Capa}}); declare as composições do Remotion do perfil")
    return {"capa": c.get("edicao"), **c}

def cor_da_grade(perfil, pasta, script):
    """Grade do perfil (regras-gerais §1): perfil.yaml → grade.ciclo dá as cores de fundo da capa em ordem; a edição pega
    a cor pela posição dela na grade (publicados + fila + ela). Grava em script.capa.fundo; uma cor já escolhida não muda."""
    p = next((x for x in carrega(ROOT)["perfis"] if x.get("pasta") == perfil), {})
    ciclo = (p.get("grade") or {}).get("ciclo")
    if not ciclo or not script.get("capa") or script["capa"].get("fundo"): return
    if (p.get("qualidade") or {}).get("grade_por_ordem"):  # pela ordem real de publicação (grade.py); o fila.py reconfere ao entrar na fila
        import grade
        script["capa"]["fundo"] = grade.cor(perfil, ignorar=pasta.name)
        original = json.loads((pasta / "script.json").read_text(encoding="utf-8")); original.setdefault("capa", {})["fundo"] = script["capa"]["fundo"]
        (pasta / "script.json").write_text(json.dumps(original, ensure_ascii=False, indent=1), encoding="utf-8"); return
    # posição = edições numeradas (<prefixo>-NNN) que já têm cor, em produção ou na fila (contar só publicadas/aprovadas repete a cor
    # quando 2–3 edições são produzidas ao mesmo tempo)
    n = 0
    for d in (ROOT / perfil / "out").iterdir():
        if d == pasta or not re.fullmatch(r"[a-z]+-\d{3}", d.name) or not (d / "script.json").exists(): continue
        if (json.loads((d / "script.json").read_text(encoding="utf-8")).get("capa") or {}).get("fundo"): n += 1
    script["capa"]["fundo"] = ciclo[n % len(ciclo)]
    original = json.loads((pasta / "script.json").read_text(encoding="utf-8"))
    original.setdefault("capa", {})["fundo"] = script["capa"]["fundo"]
    (pasta / "script.json").write_text(json.dumps(original, ensure_ascii=False, indent=1), encoding="utf-8")

def gerar_capa(pasta, script, words, remotion, composicao, capa_comp, comp_cfg=None):
    """Capa do post. Com script.capa e composição de capa própria: arte da capa (composicao.capa). Com script.capa e capa = edição: o quadro
    capa.t da própria edição com o texto por cima (prop capa: true). Sem script.capa: o frame scene.capa_t do vídeo."""
    if script.get("capa") and capa_comp == composicao:
        props, comp, frame = {"script": script, "words": words, "capa": True}, composicao, round(script["capa"].get("t", 1.0) * 30)
    elif script.get("capa"):
        props, comp, frame = {"script": script, "words": words}, capa_comp, 0
    else:
        props, comp, frame = {"script": script, "words": words, "capa": True}, composicao, round(script.get("scene", {}).get("capa_t", 1.0) * 30)
    (pasta / "props_capa.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    sh(["npx", "remotion", "still", "src/index.ts", comp, str(pasta / "cover.png"), f"--props={pasta / 'props_capa.json'}", f"--frame={frame}", "--log=error", f"--port={porta_livre()}"],
       cwd=remotion, shell=sys.platform == "win32")
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(pasta / "cover.png"), "-q:v", "2", str(pasta / "cover.jpg")])
    (pasta / "cover.png").unlink(); (pasta / "props_capa.json").unlink()
    # simula a grade do Instagram por cima (ícone de reel e views): capa_grade.jpg, que o qa.py entrega ao avaliador
    import capa_grade
    capa_grade.simula(pasta / "cover.jpg", pasta / "capa_grade.jpg")
    print("capa_grade: texto nas zonas do Instagram:", capa_grade.zonas_livres(pasta / "cover.jpg"))
    chk = pasta.parent.parent / "capa_check.py"
    if (comp_cfg or {}).get("capa_sujeito") and chk.exists():
        # plugin do perfil: renderiza a capa só com o sujeito (prop soSujeito) e mede com <perfil>/capa_check.py → checar(png, pasta) -> {ok, problemas, avisos};
        # grava capa_check.json (o qa.py não abre rodada com a capa reprovada)
        import importlib.util
        props["soSujeito"] = True; (pasta / "props_capa.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        sh(["npx", "remotion", "still", "src/index.ts", comp, str(pasta / "capa_sujeito.png"), f"--props={pasta / 'props_capa.json'}", f"--frame={frame}",
            "--image-format=png", "--log=error", f"--port={porta_livre()}"], cwd=remotion, shell=sys.platform == "win32")
        spec = importlib.util.spec_from_file_location("capa_check_perfil", chk); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        r = mod.checar(pasta / "capa_sujeito.png", pasta)
        (pasta / "capa_check.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        (pasta / "capa_sujeito.png").unlink(); (pasta / "props_capa.json").unlink()
        print("capa_check:", ("ok" if r.get("ok") else "REPROVADA antes do QA → " + " | ".join(r.get("problemas", []))) + ("" if not r.get("avisos") else " · avisos: " + " | ".join(r["avisos"])))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pasta"); ap.add_argument("--composicao"); ap.add_argument("--so-capa", action="store_true"); ap.add_argument("--rascunho", action="store_true"); a = ap.parse_args()
    pasta = pathlib.Path(a.pasta).resolve(); perfil = pasta.relative_to(ROOT).parts[0]
    remotion = ROOT / perfil / "remotion"
    comp = comp_do_perfil(perfil); a.composicao = a.composicao or comp["edicao"]
    script = json.loads((pasta / "script.json").read_text(encoding="utf-8"))
    words = json.loads((pasta / "words.json").read_text(encoding="utf-8"))
    cor_da_grade(perfil, pasta, script)
    of = next((x for x in carrega(ROOT)["perfis"] if x.get("pasta") == perfil), {}).get("oferta") or {}
    sec = (of.get("secoes") or {}).get((script.get("cta") or {}).get("secao") or "") if isinstance(script.get("cta"), dict) else None
    if script.get("cta") and sec:  # palavra por vídeo (oferta.secoes): card final com a seção do produto, entra quando a voz diz "Comment" (cta_video.py)
        import cta_video
        pal = script["cta"]["palavra"]
        script["oferta"] = {"palavra": pal, "t0": round(cta_video.inicio_da_chamada(words, pal) + 0.05, 2),
                            "card": {"tag": of.get("card_tag", ""), "titulo": sec["card"]["titulo"], "sub": sec["card"]["sub"], "dm": of.get("card_dm", "and I'll send it to your DMs")}}
    elif script.get("cta"): script["oferta"] = {**(script.get("oferta") or {}), "palavra": (script["cta"] or {}).get("palavra") if isinstance(script["cta"], dict) else None}
    elif script.get("sem_cta") or script.get("cta") is False: pass   # edição SEM chamada: o vídeo acaba no fechamento (ou no card de seguir)
    elif of.get("card") and not script.get("oferta"): script["oferta"] = {"palavra": of.get("palavra"), "card": of["card"]}  # card final no hold (perfil.yaml → oferta.card)
    if a.so_capa: gerar_capa(pasta, script, words, remotion, a.composicao, comp["capa"], comp); print("capa:", pasta / "cover.jpg"); return
    (pasta / "props.json").write_text(json.dumps({"script": script, "words": words}, ensure_ascii=False), encoding="utf-8")
    if not (pasta / "mix_check.json").exists() or not json.loads((pasta / "mix_check.json").read_text(encoding="utf-8")).get("passou"):
        sys.exit("mix.wav ausente ou reprovada: rode mix.py antes")

    if a.rascunho:   # metade da resolução, sem grão/áudio/capa/gates, só para conferir layout e ritmo; NÃO vale para QA nem fila
        rasc = pasta / "video_rascunho.mp4"
        sh(["npx", "remotion", "render", "src/index.ts", a.composicao, str(rasc), f"--props={pasta / 'props.json'}", "--codec=h264", "--crf=28", "--scale=0.5",
            "--muted", "--log=error", f"--port={porta_livre()}"], cwd=remotion, shell=sys.platform == "win32")
        print("rascunho:", rasc); return

    # 1. vídeo sem áudio
    mudo = pasta / "video_mudo.mp4"
    sh(["npx", "remotion", "render", "src/index.ts", a.composicao, str(mudo), f"--props={pasta / 'props.json'}",
        "--codec=h264", "--crf=16", "--muted", "--log=error", f"--port={porta_livre()}"], cwd=remotion, shell=sys.platform == "win32")

    # 1b. pós-processamento opcional do perfil (perfil.yaml → composicao.pos: filtro do ffmpeg; {remotion} = pasta remotion do perfil).
    # Ex.: textura de papel + grão por quadro aqui, porque no navegador o render fica muito mais lento.
    if comp.get("pos"):
        tratado = pasta / "video_mudo_pos.mp4"
        sh(["ffmpeg", "-v", "error", "-y", "-i", str(mudo), "-filter_complex", comp["pos"].replace("{remotion}", f"{perfil}/remotion"),   # caminho relativo à raiz (sem ":" do drive, que quebra o filtro)
            "-c:v", "libx264", "-crf", "22", "-maxrate", "11M", "-bufsize", "22M", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", str(tratado)], cwd=ROOT)   # teto de bitrate: grão vivo explode o tamanho do arquivo
        tratado.replace(mudo)

    # 2. mux com a mix (AAC 48 kHz 192k, +faststart); vídeo copiado sem reencodar
    video = pasta / "video.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(mudo), "-i", str(pasta / "mix.wav"), "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(video)])

    # 3. capa e folha de contato (12 quadros)
    gerar_capa(pasta, script, words, remotion, a.composicao, comp["capa"], comp)
    dur = float(probe(video)["format"]["duration"])
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps=12/{dur:.3f},scale=270:-1,tile=6x2:padding=6:color=black",
        "-frames:v", "1", "-q:v", "3", str(pasta / "sheet.jpg")])

    # 4. gate
    info = probe(video); v = next(s for s in info["streams"] if s["codec_type"] == "video"); au = next(s for s in info["streams"] if s["codec_type"] == "audio")
    num, den = map(int, v["r_frame_rate"].split("/"))
    preto = sh(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=0.2:pix_th=0.08", "-an", "-f", "null", "-"]).stderr
    fmt = json.loads((ROOT / perfil / "format.json").read_text(encoding="utf-8"))
    check = {"arquivo": str(video.relative_to(ROOT)), "resolucao": f'{v["width"]}x{v["height"]}', "fps": num / den, "codec": [v["codec_name"], au["codec_name"]],
             "audio_hz": int(au["sample_rate"]), "duracao_s": round(dur, 2), "faixa_formato_s": fmt["duration_s"],
             "frames_pretos": re.findall(r"black_start:([\d.]+)", preto), "planos": len(script["shots"]),
             "planos_de_camera": len({s["camera"]["plane"] for s in script["shots"]})}
    # piscadas: textos/HUD/inserts renderizados sozinhos e analisados quadro a quadro (piscadas.py)
    pisc = subprocess.run([sys.executable, str(ROOT / "_sistema" / "orquestrador" / "piscadas.py"), str(pasta), "--composicao", a.composicao], capture_output=True, text=True)
    pj = pasta / "piscadas.json"
    check["piscadas"] = json.loads(pj.read_text(encoding="utf-8"))["eventos"] if pj.exists() else [f"checagem falhou: {pisc.stderr[-300:]}"]
    check["fora_da_area"] = json.loads(pj.read_text(encoding="utf-8")).get("fora_da_area", []) if pj.exists() else []  # área segura do feed (corte 4:5)
    check["gate"] = {"resolucao_ok": check["resolucao"] == "1080x1920", "fps_ok": check["fps"] == 30, "codec_ok": check["codec"] == ["h264", "aac"] and check["audio_hz"] == 48000,
                     "duracao_ok": fmt["duration_s"][0] <= dur <= fmt["duration_s"][1], "sem_preto_ok": not check["frames_pretos"],
                     "camera_ok": check["planos_de_camera"] >= fmt.get("min_camera_planes", 3), "sem_piscada_ok": not check["piscadas"]}
    pf = next((x for x in carrega(ROOT)["perfis"] if x.get("pasta") == perfil), {})
    if (pf.get("qualidade") or {}).get("area_feed"): check["gate"]["area_segura_ok"] = not check["fora_da_area"]  # perfil.yaml → qualidade.area_feed liga por perfil (checagem por pixel do piscadas.py)
    if script.get("oferta") or script.get("cta"):  # card final (oferta) no hold: precisa de ≥ 1,6 s depois da última palavra
        check["card_final_s"] = round(dur - (words[-1]["end"] if words else dur), 2); check["gate"]["card_final_ok"] = check["card_final_s"] >= 1.6
    elif script.get("seguir") and float((script["seguir"] or {}).get("t", 0)) + float((script["seguir"] or {}).get("dur", 0)) >= dur - 0.3:  # card de seguir no hold depois da voz: ≥ 1,6 s depois da última palavra
        check["card_final_s"] = round(dur - (words[-1]["end"] if words else dur), 2); check["gate"]["card_final_ok"] = check["card_final_s"] >= 1.6
    elif script.get("sem_cta") or script.get("cta") is False:  # sem CTA: o fechamento respira ≥ 1,2 s depois da última palavra, sem card
        check["hold_final_s"] = round(dur - (words[-1]["end"] if words else dur), 2); check["gate"]["hold_final_ok"] = check["hold_final_s"] >= 1.2
    check["passou"] = all(check["gate"].values())
    (pasta / "render_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=1), encoding="utf-8")
    mudo.unlink(missing_ok=True)
    check["versao"] = str(guarda_versao(perfil, pasta).relative_to(ROOT))
    print(json.dumps(check, ensure_ascii=False, indent=1))

def guarda_versao(perfil, pasta):
    """Toda versão renderizada fica guardada, numerada, em <perfil>/versoes/<id>/ (o video.mp4 da edição é sobrescrito a cada render).
    Nome: <id>_v<N>_<AAAA-MM-DD_HHMM>.mp4 (+ a capa da mesma versão)."""
    import datetime as dt
    d = ROOT / perfil / "versoes" / pasta.name; d.mkdir(parents=True, exist_ok=True)
    n = 1 + max([int(m.group(1)) for f in d.glob(f"{pasta.name}_v*.mp4") if (m := re.match(rf"{re.escape(pasta.name)}_v(\d+)_", f.name))] or [0])
    nome = f"{pasta.name}_v{n}_{dt.datetime.now():%Y-%m-%d_%H%M}"
    shutil.copy2(pasta / "video.mp4", d / f"{nome}.mp4")
    if (pasta / "cover.jpg").exists(): shutil.copy2(pasta / "cover.jpg", d / f"{nome}_capa.jpg")
    return d / f"{nome}.mp4"

if __name__ == "__main__":
    main()
