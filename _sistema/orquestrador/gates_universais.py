"""Gates universais do fila.py: valem para TODO perfil, com os valores de <perfil>/perfil.yaml → ritmo / qualidade (padrão em perfis.yaml → padrao).
Cada gate recebe o `ctx` (o mesmo que o plugin <perfil>/gates.py recebe; contrato em CHAVES-PERFIL.md) e devolve uma lista de achados
{"nivel": "erro" | "aviso", "gate": "<nome>", "msg": "<texto>"}. "erro" barra a entrada na fila; "aviso" só é impresso.
Gates (ordem de execução):
  gancho        assunto e movimento nos primeiros `ritmo.gancho_ate_s` s (padrão 3); 1ª palavra da voz logo; nada de "olá"/vinheta.
  liga_ao_fato  cena de explicador / insert sorteado só vale com `liga_ao_fato` (1 frase que cita o assunto do vídeo).
  seguir        pausa/card pedindo para SEGUIR no momento `ritmo.seguir.momento` (meio | final | nenhum), com `ritmo.seguir.duracao_s`.
  card_final    card final com oferta ou seguir (`ritmo.card_final`: oferta | seguir | nenhum) e hold depois da última palavra.
  area_segura   texto/HUD/inserts entre y 285 e 1635 (1080x1920) e no máximo `qualidade.max_inserts_juntos` (2) inserts juntos.
  piscadas      nenhuma piscada (render_check.json → piscadas, medido por quadro no piscadas.py).
  audio         mix aprovada com voz na frente e ducking suave (mix_check.json).
  hud           HUD interativa (`qualidade.hud: true`): script.hud com valores que mudam junto com a narração.
  variacao      variar a execução entre edições (chaves opcionais de `qualidade`, ver CHAVES-PERFIL.md).
Uso avulso (só leitura, não mexe em nada):  python _sistema/orquestrador/gates_universais.py <pasta/out/edicao> [...]"""
import json, pathlib, re, subprocess, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
AREA_Y = (285, 1635)          # corte 4:5 do feed no quadro 1080x1920
AREA_X = (40, 1040)           # margem lateral; coluna de botões do Reels: x > 950 abaixo de y 1000
BOTOES = (950, 1000)
MOVIMENTO_MIN = 0.72          # média da diferença entre quadros (270x480 cinza, 30 fps) abaixo disso = abertura parada
ABRE_PROIBIDO = re.compile(r"^\W*(hi|hello|hey (guys|there|everyone)|welcome|ol[áa]|oi|e a[íi]|bem-vindos?|fala,? galera)\b", re.I)
SEGUIR_PROIBIDO = re.compile(r"comment|coment[ae]|pre[çc]o|gr[áa]tis|\bDMs?\b|send you|\blink\b|\bbio\b|\bfree\b|\$|price|course|curso", re.I)


def achado(gate, msg, nivel="erro"):
    return {"nivel": nivel, "gate": gate, "msg": msg}


def opc(ctx, chave, padrao=None):
    """Valor pontilhado ("ritmo.seguir.momento") do perfil.yaml; se o perfil não define, o de perfis.yaml → padrao; senão `padrao`."""
    for fonte in (ctx.get("perfil") or {}, ctx.get("padrao") or {}):
        v = fonte
        for k in chave.split("."):
            v = v.get(k) if isinstance(v, dict) else None
            if v is None: break
        if v is not None: return v
    return padrao


def _faixa(v, padrao):
    """Número = mínimo; [a, b] = faixa."""
    if v is None: return padrao
    if isinstance(v, (int, float)): return (float(v), float("inf"))
    return (float(v[0]), float(v[1]))


def duracao(ctx):
    s = ctx.get("script") or {}
    rc = ctx.get("render_check") or {}
    return float(rc.get("duracao_s") or s.get("duration_s") or 0)


def fim_da_voz(ctx):
    w = ctx.get("words") or []
    return float(w[-1]["end"]) if w else None


# ---------- 1. gancho ----------
def media_abertura(video, ate_s):
    """Movimento médio nos primeiros `ate_s` segundos do vídeo (diferença absoluta entre quadros consecutivos)."""
    import numpy as np
    import movimento as m
    cmd = [m._ffmpeg(), "-v", "error", "-t", f"{ate_s + 0.2:.2f}", "-i", str(video), "-vf", f"fps=30,scale={m.W}:{m.H}:flags=area,format=gray", "-f", "rawvideo", "-"]
    q = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.uint8).reshape(-1, m.H, m.W).astype(np.int16)
    if len(q) < 3: return None
    d = np.abs(np.diff(q, axis=0)).mean(axis=(1, 2))[:int(30 * ate_s)]
    return float(d.mean())


def gancho(ctx):
    s, pasta, out = ctx["script"], ctx["pasta"], []
    ate = float(opc(ctx, "ritmo.gancho_ate_s", 3))
    g = s.get("gancho")
    texto = (g.get("texto") if isinstance(g, dict) else g) or ""
    if not str(texto).strip():
        out.append(achado("gancho", "sem script.gancho.texto: o assunto tem de aparecer escrito/grande nos primeiros segundos (sem som e sem legenda, em 1 s dá para dizer o que é)"))
    elif isinstance(g, dict) and float(g.get("t", 0)) > min(1.0, ate):
        out.append(achado("gancho", f"o gancho entra em {g.get('t')} s (máx. 1 s: o assunto aparece no primeiro segundo)"))
    w = ctx.get("words") or []
    if w and float(w[0]["start"]) > 1.0:
        out.append(achado("gancho", f"a voz começa em {w[0]['start']:.1f} s (máx. 1 s: nada de vinheta antes do gancho)"))
    if w and ABRE_PROIBIDO.search(" ".join(x["w"] for x in w[:4])):
        out.append(achado("gancho", f'a 1ª frase abre com saudação ("{" ".join(x["w"] for x in w[:4])}"): abra com pergunta, número ou promessa concreta'))
    if opc(ctx, "ritmo.abertura_calma", False) or (pasta / "abertura_excecao.json").exists(): return out
    video = pasta / "video.mp4"
    if video.exists():
        minimo = float(opc(ctx, "ritmo.gancho_movimento_min", MOVIMENTO_MIN))
        try: v = media_abertura(video, ate)
        except Exception as e: out.append(achado("gancho", f"movimento da abertura não medido ({e})", "aviso")); v = None
        if v is not None and v < minimo:
            out.append(achado("gancho", f"primeiros {ate:g} s parados (movimento {v:.2f} < {minimo}): abra com câmera, zoom ou ação. "
                                        f"Abertura calma de propósito: ritmo.abertura_calma: true no perfil.yaml ou out/{pasta.name}/abertura_excecao.json com o motivo"))
    return out


# ---------- 2. liga ao fato ----------
def _palavras(t):
    t = unicodedata.normalize("NFD", str(t or "").lower()); t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return {w for w in re.findall(r"[a-z0-9]{4,}", t)}


def liga_ao_fato(ctx):
    if not opc(ctx, "qualidade.liga_ao_fato", True): return []
    s, b, out = ctx["script"], ctx.get("brief") or {}, []
    pecas = [("explicador", s.get("explicador"))] if isinstance(s.get("explicador"), dict) else []
    pecas += [(f'insert {i.get("id") or k + 1}', i) for k, i in enumerate(s.get("inserts") or []) if isinstance(i, dict) and i.get("sorteado")]
    assunto = _palavras(" ".join(str(x) for x in (b.get("topic"), b.get("angle"), s.get("tema"), s.get("title")) if x))
    for nome, peca in pecas:
        liga = str(peca.get("liga_ao_fato") or "").strip()
        if len(liga) < 20:
            out.append(achado("liga_ao_fato", f"{nome} sem liga_ao_fato (1 frase, >= 20 caracteres, dizendo por que a cena pertence a ESTE fato): omita a peça ou declare a ligação"))
        elif assunto and not (assunto & _palavras(liga)):
            out.append(achado("liga_ao_fato", f"{nome}: liga_ao_fato não cita o assunto do vídeo ({liga[:60]}…)"))
    return out


# ---------- 3. pausa / card para SEGUIR ----------
def seguir(ctx):
    momento = opc(ctx, "ritmo.seguir.momento", "final")
    if momento in (None, False, "nenhum"): return []
    s, out = ctx["script"], []
    sg = s.get("seguir")
    if not isinstance(sg, dict):
        return [achado("seguir", f"sem script.seguir {{t, dur, texto}}: o perfil pede uma pausa para SEGUIR ({momento}; perfil.yaml → ritmo.seguir)")]
    dmin, dmax = _faixa(opc(ctx, "ritmo.seguir.duracao_s"), (1.5, 2.5))
    t, d, total = float(sg.get("t", -1)), float(sg.get("dur", 0)), duracao(ctx)
    if t < 0: out.append(achado("seguir", "script.seguir.t ausente (segundo em que o card de seguir entra)"))
    if not dmin <= d <= dmax: out.append(achado("seguir", f"card de seguir com {d:g} s (perfil: {dmin:g}–{dmax:g} s)"))
    if total and t >= 0:
        if momento == "meio" and not 0.2 * total <= t <= 0.8 * total:
            out.append(achado("seguir", f"card de seguir em {t:g} s; o perfil pede no MEIO do vídeo (entre {0.2 * total:.1f} e {0.8 * total:.1f} s)"))
        if momento == "final" and t + d < total - 0.3:
            out.append(achado("seguir", f"card de seguir termina em {t + d:.1f} s; o perfil pede no FINAL (até {total:.1f} s)"))
        if t + d > total + 0.05: out.append(achado("seguir", f"card de seguir passa do fim do vídeo ({t + d:.1f} > {total:.1f} s)"))
    if SEGUIR_PROIBIDO.search(f'{sg.get("texto", "")} {sg.get("sub", "")}'):
        out.append(achado("seguir", "card de seguir com comentário/DM/link/preço no texto: ele só pede para seguir"))
    return out


# ---------- 4. card final ----------
def card_final(ctx):
    s, p, out = ctx["script"], ctx.get("perfil") or {}, []
    padrao = "oferta" if (s.get("oferta") or (p.get("oferta") or {}).get("card")) else "seguir"
    tipo = opc(ctx, "ritmo.card_final", padrao)
    if tipo in (None, False, "nenhum"): return []
    hold_min = float(opc(ctx, "ritmo.card_final_min_s", 1.6))
    total, fim = duracao(ctx), fim_da_voz(ctx)
    if tipo == "oferta":
        card = (s.get("oferta") or {}).get("card") or (p.get("oferta") or {}).get("card")
        if not card: out.append(achado("card_final", "card final de oferta sem conteúdo (script.oferta.card ou perfil.yaml → oferta.card)"))
    elif tipo == "seguir":
        sg = s.get("seguir") or {}; cf = s.get("card_final") or {}
        no_fim = sg and total and float(sg.get("t", 0)) + float(sg.get("dur", 0)) >= total - 0.3
        if not no_fim and cf.get("tipo") != "seguir":
            out.append(achado("card_final", "o vídeo não termina no card de SEGUIR (script.seguir no fim ou script.card_final.tipo = seguir)"))
    if total and fim is not None and total - fim < hold_min:
        out.append(achado("card_final", f"{total - fim:.1f} s de card depois da última palavra (mín. {hold_min:g} s; perfil.yaml → ritmo.card_final_min_s)"))
    return out


# ---------- 5. área segura do feed ----------
def _caixa(el):
    """[x0, y0, x1, y1] de um elemento do script: caixa [x, y, w, h] ou x/y (+ w/h)."""
    if not isinstance(el, dict): return None
    if el.get("caixa"):
        x, y, w, h = el["caixa"]; return [x, y, x + w, y + h]
    if el.get("y") is not None:
        x, y = el.get("x", 540), el["y"]; w, h = el.get("w", 0), el.get("h", 0)
        return [x - w / 2, y - h / 2, x + w / 2, y + h / 2]
    return None


def area_segura(ctx):
    s, out = ctx["script"], []
    y0, y1 = opc(ctx, "qualidade.area_segura", list(AREA_Y))[:2]
    rc = ctx.get("render_check") or {}
    for f in rc.get("fora_da_area") or []:
        out.append(achado("area_segura", f"fora da área segura do feed (medido por pixel): {f}"))
    elementos = [(f'dado "{d.get("valor", "")}"', d) for d in s.get("dados") or []] + [(f'insert {i.get("id") or i.get("img") or k + 1}', i) for k, i in enumerate(s.get("inserts") or [])]
    elementos += [("card de seguir", s.get("seguir")), ("HUD", s.get("hud"))]
    for nome, el in elementos:
        b = _caixa(el)
        if not b: continue
        if b[1] < y0 or b[3] > y1: out.append(achado("area_segura", f"{nome} fora do feed na vertical (y {b[1]:.0f}–{b[3]:.0f}; área {y0}–{y1})"))
        if b[0] < AREA_X[0] or b[2] > AREA_X[1]: out.append(achado("area_segura", f"{nome} encostado na lateral (x {b[0]:.0f}–{b[2]:.0f}; margem {AREA_X[0]}–{AREA_X[1]})"))
        if b[2] > BOTOES[0] and b[3] > BOTOES[1]: out.append(achado("area_segura", f"{nome} na coluna de botões do Reels (x > {BOTOES[0]} abaixo de y {BOTOES[1]})"))
    maximo = int(opc(ctx, "qualidade.max_inserts_juntos", 2))
    janelas = [(float(d["t"]), float(d.get("ate", d["t"] + 2)), nome) for nome, d in elementos[:len(s.get("dados") or []) + len(s.get("inserts") or [])] if isinstance(d, dict) and d.get("t") is not None]
    for t0, _, _ in sorted(janelas):
        juntos = [n for a, b, n in janelas if a <= t0 + 0.05 < b]
        if len(juntos) > maximo:
            out.append(achado("area_segura", f"amontoado em {t0:.1f} s: {len(juntos)} inserts juntos ({', '.join(juntos)}); máximo {maximo} além da HUD e da legenda")); break
    return out


# ---------- 6. piscadas ----------
def piscadas(ctx):
    rc = ctx.get("render_check")
    if rc is None: return [achado("piscadas", "render_check.json ausente: rode render.py (a checagem de piscadas sai dele)")]
    ev = rc.get("piscadas") or []
    return [achado("piscadas", f"{len(ev)} piscada(s) (algo que aparece e some rápido): {str(ev[:3])[:200]}")] if ev else []


# ---------- 7. áudio ----------
def audio(ctx):
    mc = ctx.get("mix_check")
    if mc is None: return [achado("audio", "mix_check.json ausente: rode mix.py")]
    g, out = mc.get("gate") or {}, []
    if not mc.get("passou"): out.append(achado("audio", "mix reprovada: " + ", ".join(k for k, v in g.items() if not v)))
    for k, txt in (("voz_trilha_ok", "voz não está na frente da trilha"), ("ducking_suave_ok", "ducking brusco (a trilha sobe/desce de repente)")):
        if k in g and not g[k] and mc.get("passou"): out.append(achado("audio", txt))
    return out


# ---------- 8. HUD interativa ----------
def hud(ctx):
    if not opc(ctx, "qualidade.hud", False): return []
    h = ctx["script"].get("hud")
    if not isinstance(h, dict): return [achado("hud", "o perfil pede HUD interativa (qualidade.hud: true) e o script.json não tem hud {rotulo, passos: [{t, v}]}")]
    passos = h.get("passos") or [x for c in h.get("contadores") or [] for x in c.get("passos") or []]
    valores = {str(x.get("v")) for x in passos}
    if len(valores) < 2: return [achado("hud", "HUD parada: hud.passos precisa de pelo menos 2 valores diferentes que mudam junto com a narração")]
    ts = [float(x.get("t", 0)) for x in passos]
    total = duracao(ctx)
    if total and any(t > total for t in ts): return [achado("hud", "hud.passos com tempo depois do fim do vídeo")]
    return []


# ---------- 9. variação entre edições (opcional por chave) ----------
def variacao(ctx):
    q, s, out = opc(ctx, "qualidade", {}) or {}, ctx["script"], []
    ant = ctx["anteriores"](4)
    if q.get("inserts_novos_min"):
        antes = {i.get("img") for _, o in ctx["anteriores"](50) for i in o.get("inserts") or [] if isinstance(i, dict)}
        novos = {i.get("img") for i in s.get("inserts") or [] if isinstance(i, dict) and i.get("img")} - antes
        if len(novos) < q["inserts_novos_min"]: out.append(achado("variacao", f'só {len(novos)} insert(s) novo(s) (mín. {q["inserts_novos_min"]} por edição)'))
    if q.get("cena_varia") and s.get("cena") and not s.get("cena_repetida_ok") and s.get("cena") in {o.get("cena") for _, o in ant[:2]}:
        out.append(achado("variacao", f'cenário "{s.get("cena")}" repetido das 2 últimas edições'))
    if q.get("variacoes"):
        cv = set(q["variacoes"].get("cenas", [])); mx = q["variacoes"].get("max_planos", 2)
        minhas = {x.get("cena") for x in s.get("shots") or []} & cv
        n = sum(1 for x in s.get("shots") or [] if x.get("cena") in cv)
        if n > mx: out.append(achado("variacao", f"{n} planos de variação (máx. {mx})"))
        if ant and minhas & ({x.get("cena") for x in ant[0][1].get("shots") or []} & cv):
            out.append(achado("variacao", f"variação repetida da edição anterior ({ant[0][0]})"))
    if q.get("gancho_banco"):
        try: banco = json.loads((ctx["ROOT"] / ctx["perfil"]["pasta"] / "format.json").read_text(encoding="utf-8")).get("gancho", {}).get("banco", [])
        except Exception: banco = []
        g = s.get("gancho"); g = g.get("texto") if isinstance(g, dict) else g
        if g not in banco: out.append(achado("variacao", f"gancho fora do banco do format.json ({g!r})"))
        elif any((o.get("gancho") if not isinstance(o.get("gancho"), dict) else o["gancho"].get("texto")) == g for _, o in ant[:3]):
            out.append(achado("variacao", "gancho repetido de uma das 3 últimas edições"))
    if q.get("fundo_vivo") and isinstance(s.get("vivo"), dict) and not any(v is not False for v in s["vivo"].values()):
        out.append(achado("variacao", "fundo vivo desligado (script.vivo)"))
    return out


GATES = [gancho, liga_ao_fato, seguir, card_final, area_segura, piscadas, audio, hud, variacao]


def roda(ctx):
    """Todos os gates universais; gate que quebra vira erro (falha fechada)."""
    out = []
    for g in GATES:
        try: out += g(ctx)
        except Exception as e: out.append(achado(g.__name__, f"gate não conferido ({type(e).__name__}: {e})"))
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import fila
    for a in sys.argv[1:]:
        pasta = (pathlib.Path(a) if pathlib.Path(a).is_absolute() else ROOT / a).resolve()
        ctx = fila.monta_ctx(pasta, fila.perfil_da_pasta(pasta))
        for x in roda(ctx) or [{"nivel": "ok", "gate": "-", "msg": "nada"}]: print(pasta.name, x["nivel"], x["gate"], x["msg"])
