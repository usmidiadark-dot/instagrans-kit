"""Chamada para comentar NO CORPO da legenda, variada por edição (vale para TODOS os perfis; contrato em _sistema/legenda.md).

Regra: a chamada nunca é sempre o mesmo padrão.
  - COM CTA: a legenda abre com o gancho do vídeo (discreto); a frase "comment "PALAVRA" and I'll send you <promessa>" desce para o corpo
    (3ª linha em diante, nunca entre o gancho e a resposta, sempre antes das hashtags), com a frase e o emoji sorteados por edição.
  - SEM CTA: a 1ª linha é uma frase discreta (observação/pergunta do tema), sem palavra de comentário, DM, "send you", link ou urgência.

Banco por perfil: perfil.yaml → legenda_cta = {frases: [...], emojis: [...]}. Cada frase tem `comment "{P}"`, `I'll send you {X}`
(a promessa exata do vídeo) e um `{E}` (emoji do pool). Histórico: as legendas reais da fila e do publicado (posts/04-aprovado + 05-publicado,
em ordem de horário; é o que vai ao ar) + registro em <perfil>/reviews/legendas.jsonl (uma linha por edição, a última vale).
Janelas (proposta, o dono pode mudar aqui): emoji fora das 3 últimas; frase fora das 6 últimas; par frase+emoji fora das 10 últimas.

EMOJI DO TEMA (o emoji referencia o vídeo: vídeo de crocodilo, emoji de crocodilo):
`tema` = o emoji do assunto do vídeo (script.json → cta.emoji_tema; o fila.py lê e passa). Com tema, o emoji da chamada É o do tema (fora da janela
N_EMOJI: o mesmo bicho volta se o tema voltar), a frase e a posição continuam sorteadas e as janelas de FRASE e de PAR valem. tema None (null ou
edição antiga sem o campo) = emoji sorteado do pool do perfil, como antes. O confere reprova emoji diferente do tema quando há tema.
1 A 3 EMOJIS (vários protagonistas no vídeo; dinâmico e bonito, sem ficar brega):
emoji_tema pode ser '🐊', '🐊🦈', '🐊 🦈 🐻' ou ['🐊','🦈']: os protagonistas do vídeo na ordem em que entram. Gate "bonito sem brega" em tema_erros
(máx. 3, nenhum repetido, nada de enfeite genérico/rosto/coração/mão/seta/forma geométrica/símbolo de palavra) e no confere (a linha de chamada tem
exatamente o grupo do tema, na ordem, sem pool junto); tema_no_roteiro (entrada da fila) confere que cada um de 2–3 é dito/mostrado no script.json.
Na legenda o grupo vai junto, sem espaço (tema_render), na vaga {E} do molde sorteado (início, meio ou fim da frase).

Quem usa: fila.py (com_palavra / confere_legenda), post.py (só confere a estrutura e nunca põe nada no topo), crosspost.py e painel.py (RE_CTA)."""
import json, pathlib, random, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
N_EMOJI, N_FRASE, N_PAR = 3, 6, 10
SOBREPOR = {}   # {id: legenda} para simular (reescrever a fila em ordem sem gravar): o histórico lê daqui antes do arquivo
RE_CTA = re.compile(r'(?i:\b(?:comment|comenta|comente|comentem))\s+"([A-Z]{3,7})"')          # a linha da chamada (toda frase do banco tem comment "PALAVRA")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⬛-⭕]")              # 1 caractere de emoji (legado; para contar use EMOJI_SEQ / conta_emojis)
# um emoji "inteiro": bandeira (2 indicadores regionais) ou base + variação (FE0F)/tom de pele + sequências ZWJ (🐻‍❄️, 👩‍🔬); ⌚–⏿ cobre ⏰ ⌛ ⏳
_BASE = "\U0001F300-\U0001FAFF☀-➿⬛-⭕⌚-⏿"
_MOD = "️\U0001F3FB-\U0001F3FF"
EMOJI_SEQ = re.compile(f"[\U0001F1E6-\U0001F1FF]{{2}}|[{_BASE}][{_MOD}]*(?:‍[{_BASE}][{_MOD}]*)*")


def conta_emojis(texto):
    """Quantos emojis a legenda tem (sequência ZWJ, tom de pele e FE0F contam como 1; o fila.py usa no limite de 3)."""
    return len(EMOJI_SEQ.findall(texto or ""))


def norm_emoji(e):
    """Compara emojis sem o seletor de variação (🕷️ == 🕷, ❄️ == ❄)."""
    return (e or "").replace("️", "").strip()


# ---- EMOJI DO TEMA com 1 a 3 emojis (vários protagonistas; dinâmico e bonito, sem ficar brega). Vale para as próximas gerações; o que já foi publicado/está na fila não muda.
# Regra "bonito sem brega" (gate; doc em _sistema/legenda.md): 1–3 emojis, nenhum repetido, só coisa CONCRETA que aparece/é dita no vídeo
# (animal, objeto, lugar, fenômeno), na ordem em que entram; nada de enfeite genérico, rosto/emoção, coração, mão/seta, forma geométrica (marca
# do perfil) ou símbolo de palavra (🆓 🆕); a linha de chamada só tem o grupo do tema (sem misturar com pool); total da legenda ≤ 3 (fila.py).
TEMA_MAX = 3
ENFEITE = set("✨🔥💯🚨🎉🥳🎊🎈⭐🌟💫💥💢💦💨💤‼⁉❗❕❓❔⚠✅☑✔❌❎➕➖➗✖〰➰➿💬💭🗨🗯📩📨📧📢📣📌📍🔗👀🏁🆗🆒🔞📈📉🔝🔜🔛🔚🔙"
              "♻⚜🔱〽✳✴❇©®™🔆🔅💠")
_FAIXAS_FORA = [  # (início, fim, motivo) — faixas EXATAS: 🦈 (1F988), 🫧 (1FAE7) e 🌬️ (1F32C) ficam fora delas de propósito
    (0x1F645, 0x1F647, "mão/gesto"), (0x1F64B, 0x1F64F, "mão/gesto"), (0x1F600, 0x1F64F, "rosto/emoção"), (0x1F910, 0x1F92F, "rosto/emoção ou mão"), (0x1F970, 0x1F97A, "rosto/emoção"), (0x1F9D0, 0x1F9D0, "rosto/emoção"),
    (0x1FAE0, 0x1FAE6, "rosto/emoção"), (0x1FAE8, 0x1FAE8, "rosto/emoção"), (0x2639, 0x263A, "rosto/emoção"), (0x1F47F, 0x1F47F, "rosto/emoção"),
    (0x1F446, 0x1F450, "mão/seta"), (0x261D, 0x261D, "mão/seta"), (0x270A, 0x270D, "mão/seta"), (0x1F4AA, 0x1F4AA, "mão/seta"),
    (0x1F590, 0x1F590, "mão/seta"), (0x1F595, 0x1F596, "mão/seta"), (0x1F90C, 0x1F90C, "mão/seta"), (0x1F90F, 0x1F90F, "mão/seta"),
    (0x1F918, 0x1F91F, "mão/seta"), (0x1FAF0, 0x1FAF8, "mão/seta"),
    (0x2190, 0x21FF, "mão/seta"), (0x2934, 0x2935, "mão/seta"), (0x27A1, 0x27A1, "mão/seta"), (0x2B05, 0x2B07, "mão/seta"), (0x25B6, 0x25B6, "mão/seta"),
    (0x25C0, 0x25C0, "mão/seta"), (0x23E9, 0x23EF, "mão/seta"), (0x1F500, 0x1F504, "mão/seta"), (0x1F53C, 0x1F53D, "mão/seta"), (0x2B06, 0x2B06, "mão/seta"),
    (0x2764, 0x2764, "coração"), (0x2763, 0x2763, "coração"), (0x1F493, 0x1F49F, "coração"), (0x1F5A4, 0x1F5A4, "coração"), (0x1F90D, 0x1F90E, "coração"),
    (0x1F9E1, 0x1F9E1, "coração"), (0x1FA75, 0x1FA77, "coração"), (0x1F48B, 0x1F48C, "coração"),
    (0x1F7E0, 0x1F7EB, "forma geométrica (marca do perfil, não é do vídeo)"), (0x26AA, 0x26AB, "forma geométrica (marca do perfil, não é do vídeo)"),
    (0x2B1B, 0x2B1C, "forma geométrica (marca do perfil, não é do vídeo)"), (0x25AA, 0x25AB, "forma geométrica (marca do perfil, não é do vídeo)"),
    (0x25FB, 0x25FE, "forma geométrica (marca do perfil, não é do vídeo)"), (0x1F532, 0x1F53B, "forma geométrica (marca do perfil, não é do vídeo)"),
    (0x1F518, 0x1F518, "forma geométrica (marca do perfil, não é do vídeo)"),
    (0x1F170, 0x1F1E5, "símbolo de palavra (🆓 🆕 🅰️)"), (0x1F200, 0x1F251, "símbolo de palavra (🈯 🉐)"),   # 1F1E6–1F1FF (bandeiras = lugar) ficam valendo
]


def tema_lista(e):
    """emoji_tema (str com ou sem espaço, ou lista de str) → lista de emojis inteiros na ordem (ZWJ 🐻‍❄️, FE0F e tom de pele = 1). None/vazio → []."""
    if e is None: return []
    if isinstance(e, (list, tuple)): e = " ".join(x for x in e if isinstance(x, str))
    return EMOJI_SEQ.findall(e) if isinstance(e, str) else []


def tema_render(e):
    """A forma que vai para a legenda: os emojis juntos, sem espaço, na ordem (mantém o FE0F: 🌬️ não vira glifo de texto). None se vazio."""
    return "".join(tema_lista(e)) or None


def tema_chave(e):
    """Para comparar: lista ordenada dos emojis sem FE0F (🐊🦈 == '🐊 🦈' == ['🐊','🦈'])."""
    return tuple(norm_emoji(x) for x in tema_lista(e))


def _motivo_fora(emo):
    base = norm_emoji(emo)
    if base in {norm_emoji(x) for x in ENFEITE}: return "enfeite genérico"
    for ch in base:
        o = ord(ch)
        if o in (0x200D,) or 0x1F3FB <= o <= 0x1F3FF: continue
        for a, b, motivo in _FAIXAS_FORA:
            if a <= o <= b: return motivo
        if ch in ENFEITE: return "enfeite genérico"
    return None


def tema_erros(e):
    """Erros do emoji_tema pela regra 'bonito sem brega'. [] = válido. None/null não passa por aqui (= pool)."""
    if isinstance(e, (list, tuple)):
        if not e or not all(isinstance(x, str) and x.strip() for x in e): return ["emoji_tema em lista precisa de 1 a 3 strings de emoji"]
        bruto = " ".join(x.strip() for x in e)
    elif isinstance(e, str): bruto = e.strip()
    else: return [f"emoji_tema tem que ser texto ou lista ({type(e).__name__})"]
    lst = tema_lista(bruto)
    sobra = EMOJI_SEQ.sub("", bruto).replace(" ", "")
    if not lst: return [f"emoji_tema sem emoji reconhecido ({bruto!r}; keycap 1️⃣ e símbolo de palavra 🆓 não valem)"]
    if sobra or re.search(r"[\x00-\x1f\x21-\x7f]", bruto): return [f"emoji_tema com letra/número/sinal ({bruto!r}): só emojis, separados por nada ou por 1 espaço (keycap 1️⃣ não vale)"]
    erros = []
    if len(lst) > TEMA_MAX: erros.append(f"{len(lst)} emojis no tema (máx. {TEMA_MAX}: os protagonistas do vídeo, na ordem em que entram)")
    chaves = [norm_emoji(x) for x in lst]
    rep = sorted({x for x in chaves if chaves.count(x) > 1})
    if rep: erros.append(f"emoji repetido no tema ({' '.join(rep)}): cada protagonista entra 1 vez")
    for x in lst:
        m = _motivo_fora(x)
        if m: erros.append(f"{x} no tema é {m}: só coisa concreta que aparece no vídeo (animal, objeto, lugar, fenômeno)")
    return erros


def tema_valido(e):
    """emoji_tema aceito pela regra de 26/10/2026 (1–3 emojis concretos, sem repetir, sem enfeite/rosto/mão/seta/coração)."""
    return e is not None and not tema_erros(e)


_STOP_NOME = {"FACE", "WITH", "SIGN", "SYMBOL", "BLACK", "WHITE", "LARGE", "SMALL", "MEDIUM", "SELECTOR", "VARIATION", "ZERO", "WIDTH", "JOINER",
              "EMOJI", "MODIFIER", "TYPE", "FITZPATRICK", "AND", "THE", "FOR", "OF", "MARK", "CIRCLE", "SQUARE", "HEAVY", "LEFT", "RIGHT"}


# palavras comuns em inglês quando o nome Unicode é formal demais (🔦 = ELECTRIC TORCH, o roteiro diz flashlight). Acrescente aqui, não afrouxe a regra.
APELIDOS = {"💧": "water drop drops", "🔦": "flashlight torch", "🌊": "ocean sea wave waves water tide", "🌬": "wind breath breathe breathing air exhale",
            "🦶": "foot feet", "🫁": "lungs lung breath breathing", "🔌": "power plug outage electricity blackout", "🌀": "hurricane cyclone storm spiral",
            "🧯": "fire extinguisher", "🚒": "fire firefighter firefighters", "🐦": "bird birds hummingbird", "🌙": "moon night sleep bedtime",
            "☀": "sun sunlight", "⚡": "lightning electricity power storm", "🦴": "bone bones skeleton", "🌍": "earth planet world", "🌎": "earth planet world",
            "🏷": "label labels labeling", "🔮": "future fortune predict prediction", "🔍": "magnifying zoom detail closer", "🔎": "magnifying zoom detail closer",
            "🐻": "bear grizzly", "🐆": "cheetah", "🦅": "falcon peregrine hawk", "🐝": "bee bees", "🐜": "ant ants", "🕷": "spider spiders", "🕸": "web spider", "🐙": "octopus", "🦑": "squid",
            "🐋": "whale whales", "🐳": "whale whales", "🐬": "dolphin dolphins", "🧊": "ice glacier frozen", "❄": "snow cold ice freezing",
            "🌋": "volcano lava eruption", "🌪": "tornado", "🔋": "battery batteries power", "📻": "radio", "🧰": "kit toolbox tools", "🍯": "honey",
            "🧠": "brain mind", "🫀": "heart", "👁": "eye eyes vision", "🦷": "tooth teeth", "🪞": "mirror", "📝": "notes note write writing"}


APELIDOS_PT = {"🐊": "crocodilo jacare", "🦈": "tubarao", "🐘": "elefante", "🦁": "leao", "🐅": "tigre", "🐆": "leopardo onca", "🐍": "cobra serpente", "🐢": "tartaruga",
               "🐸": "sapo", "🐧": "pinguim", "🦅": "aguia", "🦉": "coruja", "🦇": "morcego", "🐻": "urso", "🐼": "panda", "🦍": "gorila", "🐒": "macaco",
               "🐋": "baleia", "🐳": "baleia", "🐬": "golfinho", "🐙": "polvo", "🦑": "lula", "🐝": "abelha abelhas", "🐜": "formiga", "🕷": "aranha", "🐦": "passaro",
               "🐟": "peixe", "🐠": "peixe", "🦀": "caranguejo", "🐀": "rato", "🐁": "rato", "🐹": "capivara hamster", "🦫": "castor capivara", "🐎": "cavalo", "🐄": "vaca",
               "🐖": "porco", "🐑": "ovelha", "🐐": "cabra", "🐕": "cachorro", "🐈": "gato", "🐇": "coelho", "🍌": "banana bananas", "💧": "agua gota", "🔥": "fogo",
               "🌊": "mar oceano onda", "🌍": "terra planeta mundo", "🌎": "terra planeta mundo", "🧠": "cerebro", "🫀": "coracao", "👁": "olho olhos", "🦷": "dente dentes",
               "⚡": "raio eletricidade energia", "🌙": "lua noite", "☀": "sol", "❄": "neve gelo frio", "🧊": "gelo", "🌋": "vulcao", "🌪": "tornado", "🔋": "bateria",
               "🏎": "carro corrida", "🚗": "carro", "✈": "aviao", "🚀": "foguete", "💰": "dinheiro", "🍯": "mel", "🦴": "osso ossos", "🛰": "satelite"}
for _k, _v in APELIDOS_PT.items(): APELIDOS[_k] = (APELIDOS.get(_k, "") + " " + _v).strip()


def tema_no_roteiro(e, script):
    """Tema com 2–3 emojis: cada um tem que ser dito/escrito no vídeo. Confere o nome Unicode (em inglês: SHARK, CROCODILE, POLAR BEAR…) contra todo
    texto do script.json (narração, falas, legenda, cenas). Só para 2–3 (1 emoji não passa por aqui); emoji sem nome conhecido não reprova.
    É uma checagem de presença, não de protagonismo: escolher só os protagonistas continua sendo decisão da sessão (produzir.md)."""
    import unicodedata
    lst = tema_lista(e)
    if len(lst) < 2: return []
    textos = []
    def junta(o):
        if isinstance(o, str): textos.append(o)
        elif isinstance(o, dict): [junta(v) for v in o.values()]
        elif isinstance(o, (list, tuple)): [junta(v) for v in o]
    junta(script or {})
    sem_acento = lambda t: "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    palavras = set(re.findall(r"[a-z]{3,}", sem_acento(" ".join(textos).lower())))
    palavras |= {w[:-1] for w in palavras if w.endswith("s") and len(w) > 3}
    erros = []
    for x in lst:
        nomes = []
        for ch in x:
            try: nomes += unicodedata.name(ch).split()
            except ValueError: pass
        nomes = [n.lower() for n in nomes if n not in _STOP_NOME and len(n) >= 3]
        for ch in norm_emoji(x).split("‍"): nomes += APELIDOS.get(ch, "").split()
        nomes = [sem_acento(n) for n in nomes]
        if not nomes: continue
        if not any(n in palavras or any((len(w) >= 4 and w in n) or (len(w) == 3 and n.endswith(w)) or (len(n) >= 4 and n in w) for w in palavras) for n in nomes):   # bee ⊂ honeybee, shark ⊂ sharks
            erros.append(f"{x} ({' / '.join(dict.fromkeys(nomes[:4]))}) no tema, mas o vídeo não fala/mostra isso no script.json: com 2–3 emojis cada um é um protagonista do vídeo; senão use 1")
    return erros
HASHTAGS = re.compile(r"(\s*#\w+)+\s*")
# 1ª linha (COM e SEM CTA): gancho/observação, nada que empurre
EMPURRA = re.compile(r'💬|\bcomment\s+"|\bcoment[ae]m?\s+"|\bte mando\b|\bvou te (mandar|enviar)\b|\blink na bio\b|\bna bio\b|\bmanda (uma )?DM\b|'
                     r"\b(baixe|baixa|clique|clica|inscreva-?se|segue (a gente|o perfil|a p[áa]gina)|salve? (este|esse)|compartilh[ae] (este|esse)|corre|[úu]ltima chance|n[ãa]o perca|s[óo] hoje|gr[áa]tis)\b|"
                     r"\bDMs?\b|\bsend you\b|\bI.?ll send\b|\blink in (my |the )?bio\b|\bin (my )?bio\b|"
                     r"\b(download|get yours|grab yours|click|sign up|subscribe|follow (me|us|for)|save this|share this|hurry|limited time|"
                     r"last chance|don'?t miss|today only|act fast|before it'?s gone|while it lasts|for free|free (download|guide|pdf))\b", re.I)
# legenda inteira SEM CTA: nenhuma forma de chamada
CHAMADA_SEM = re.compile(r'💬\s*coment|\b(?i:coment[ae]m?)\s+"?(?-i:[A-Z]{3,7})"?(?![A-Za-zÀ-ú])|\bte mando\b|\bvou te (mandar|enviar)\b|\blink na bio\b|\bna bio\b|\bmanda (uma )?DM\b|\b(baixe|clique|inscreva-?se|[úu]ltima chance|n[ãa]o perca|s[óo] hoje|corre)\b|💬\s*comment|\bcomment\s+"?[A-Z]{3,7}"?(?![a-z])|\bDMs?\b|\bsend you\b|\bI.?ll send\b|link in (my |the )?bio|\bin (my )?bio\b|'
                         r"\b(hurry|limited|last chance|don'?t miss|today only|act fast|get yours|grab yours|while it lasts)\b", re.I)

PADRAO = {"frases": ['comment "{P}" and I\'ll send you {X} {E}', '{E} comment "{P}" and I\'ll send you {X}',
                     'one word does it: comment "{P}" and I\'ll send you {X} {E}', 'want more? comment "{P}" and I\'ll send you {X} {E}',
                     '{E} if this one stayed with you, comment "{P}" and I\'ll send you {X}', 'comment "{P}" below and I\'ll send you {X} {E}',
                     'there\'s a longer version: comment "{P}" and I\'ll send you {X} {E}', '{E} for later: comment "{P}" and I\'ll send you {X}'],
          "emojis": ["💬", "✨", "📩", "👇", "🔎"]}


def banco(p):
    b = (p or {}).get("legenda_cta") or {}
    return list(b.get("frases") or PADRAO["frases"]), list(b.get("emojis") or PADRAO["emojis"])


def _regex(frase):
    partes = re.split(r"(\{[PXE]\})", frase)
    # {E} = 1 ou mais emojis inteiros (ZWJ/FE0F/tom de pele), juntos ou com 1 espaço (26/10/2026: o tema pode ter 1–3). O limite de 3, repetido e
    # enfeite NÃO ficam aqui (linha com 4 viraria "fora do banco", mensagem enganosa): quem barra é o confere/tema_erros, com motivo próprio.
    emo = f"(?:{EMOJI_SEQ.pattern})"
    m = {"{P}": r'(?P<P>[A-Z]{3,7})', "{X}": r"(?P<X>.+?)", "{E}": rf"(?P<E>{emo}(?: ?{emo})*)"}
    return re.compile("".join(m.get(x, re.escape(x)) for x in partes))


def preenche(frase, pal, prom, emo):
    return frase.replace("{P}", pal).replace("{X}", prom).replace("{E}", emo).strip()


def detecta(linha, p):
    """{'frase', 'emoji', 'palavra', 'promessa'} da linha de chamada; frase = o molde do banco ou 'legado' (a linha fixa antiga, 💬 … <emoji>)."""
    l = linha.strip()
    m = re.fullmatch(r'💬\s*comment\s+"([A-Z]{3,7})"\s+and I\'ll send you\s+(.+?)\s+(\S+)', l)   # a linha fixa antiga (23/10/2026)
    if m and EMOJI_SEQ.fullmatch(m.group(3)): return {"frase": "legado", "emoji": m.group(3), "palavra": m.group(1), "promessa": m.group(2).strip()}
    frases, _ = banco(p)
    for f in sorted(frases, key=lambda f: -len(re.sub(r"\{[PXE]\}", "", f))):   # o molde mais específico primeiro
        m = _regex(f).fullmatch(l)
        if m: return {"frase": f, "emoji": m.group("E"), "palavra": m.group("P"), "promessa": m.group("X").strip()}
    m = RE_CTA.search(l)
    if not m: return None
    pr = re.search(r"I'll send you\s+(.+?)(?:\s*[^\sA-Za-z0-9\"'.,:;!?()]+)?\s*$", l)
    es = EMOJI_SEQ.findall(l)
    return {"frase": "fora_do_banco", "emoji": es[-1] if es else "", "palavra": m.group(1), "promessa": pr.group(1).strip() if pr else ""}


def corpo_e_tags(texto):
    linhas = [l for l in texto.strip("\n").split("\n")]
    k = len(linhas)
    while k > 0 and (HASHTAGS.fullmatch(linhas[k - 1]) or not linhas[k - 1].strip()): k -= 1
    return linhas[:k], linhas[k:]


def tira_cta(texto):
    return "\n".join(l for l in texto.split("\n") if not RE_CTA.search(l))


def promessa_fixa(p):
    """Palavra e promessa da linha fixa do perfil (perfil.yaml → oferta.cta), para as edições sem script.cta (FACTS, CALM, IDEAS…)."""
    of = (p or {}).get("oferta") or {}
    d = detecta(of.get("cta") or "", p)
    return (d["palavra"], d["promessa"]) if d and d.get("promessa") else None


def historico(p, excluir=None, ate=None):
    """Chamadas das edições do perfil (fila + publicado), em ordem de horário; ate = só as de horário anterior a esse."""
    base = ROOT / p["pasta"] / "posts"
    vistos = {}
    for d in ("05-publicado", "04-aprovado"):
        for f in (base / d).glob("*.json") if (base / d).exists() else []:
            if f.name.startswith("._"): continue
            try: it = json.loads(f.read_text(encoding="utf-8"))
            except Exception: continue
            if it.get("id") == excluir or (ate and it.get("horario", "") >= ate): continue
            linhas = (SOBREPOR.get(it.get("id")) or it.get("legenda") or "").split("\n")
            k = next((i for i, l in enumerate(linhas) if RE_CTA.search(l)), None)
            info = detecta(linhas[k], p) if k is not None else None
            vistos[it.get("id")] = {"id": it.get("id"), "horario": it.get("horario", ""), "cta": bool(info),
                                    **({"frase": info["frase"], "emoji": info["emoji"], "pos": k} if info else {})}
    return sorted(vistos.values(), key=lambda x: x["horario"])


def escolhe(p, ed, hist, n_corpo, tema=None):
    """(frase, emoji, pos) da edição: sorteio pela semente = id (igual ao sorteio_cenas), fora das janelas do histórico.
    tema = emoji do assunto do vídeo: o emoji é ele (sem janela de emoji); só a frase e a posição são sorteadas."""
    frases, emojis = banco(p)
    tema = tema_render(tema)   # 1–3 emojis do tema (26/10/2026), juntos na ordem; a posição na frase vem do molde sorteado (início, meio ou fim)
    if tema: emojis = [tema]
    h = [x for x in hist if x.get("cta")]
    ult_e = set() if tema else {norm_emoji(x["emoji"]) for x in h[-N_EMOJI:]}
    ult_f = {x["frase"] for x in h[-N_FRASE:]}
    pares = {(x["frase"], norm_emoji(x["emoji"])) for x in h[-N_PAR:]}
    rnd = random.Random(f"{ed}-legenda")
    cand = [(f, e) for f in frases for e in emojis if norm_emoji(e) not in ult_e and f not in ult_f and (f, norm_emoji(e)) not in pares]
    cand = cand or [(f, e) for f in frases for e in emojis if (f, norm_emoji(e)) not in pares] or [(f, e) for f in frases for e in emojis]
    f, e = rnd.choice(cand)
    vagas = list(range(2, n_corpo + 1)) if n_corpo >= 2 else [n_corpo]   # 3ª linha em diante: nunca o gancho nem entre o gancho e a resposta
    ult_pos = h[-1].get("pos") if h else None
    pos = rnd.choice([v for v in vagas if v != ult_pos] or vagas)
    return f, e, pos


def monta(texto, p, pal, prom, ed=None, ate=None, tema=None):
    """Tira toda linha de chamada (onde estiver: os geradores antigos põem no topo) e põe a variante sorteada no corpo."""
    corpo, tags = corpo_e_tags(tira_cta(texto))
    f, e, pos = escolhe(p, ed or "sem-id", historico(p, excluir=ed, ate=ate), len(corpo), tema=tema)
    corpo.insert(min(pos, len(corpo)), preenche(f, pal, prom, e))
    return "\n".join(corpo + tags)


def troca_emoji(texto, p, pal, prom, tema):
    """Legenda já na regra com OUTRO emoji (do pool, de antes da regra do emoji do tema): troca só o emoji pelo do tema, na mesma frase e na
    mesma linha (não sorteia de novo nem muda a posição). None = não dá (frase legado/fora do banco): quem chama usa o monta."""
    linhas = texto.split("\n")
    ks = [i for i, l in enumerate(linhas) if RE_CTA.search(l)]
    tema = tema_render(tema)
    if len(ks) != 1 or not tema: return None
    info = detecta(linhas[ks[0]], p) or {}
    frases, _ = banco(p)
    if info.get("frase") not in frases: return None
    linhas[ks[0]] = preenche(info["frase"], pal, prom, tema)
    return "\n".join(linhas)


def ja_na_regra(texto, p, pal, prom, tema=None):
    return not confere(texto, p, pal, prom, com_historico=False, tema=tema)


def confere(texto, p, pal, prom, ed=None, ate=None, com_historico=True, tema=None):
    """Erros da chamada no corpo (COM CTA). tema = emoji do assunto (script.json → cta.emoji_tema): com ele, o emoji da chamada tem que ser
    esse (outro emoji, mesmo do pool, reprova) e não entra na janela de emoji; sem ele (None), o emoji vem do pool do perfil."""
    erros = []
    linhas = texto.split("\n")
    ks = [i for i, l in enumerate(linhas) if RE_CTA.search(l)]
    corpo, _tags = corpo_e_tags(texto)
    if linhas and EMPURRA.search(linhas[0]): erros.append(f'1ª linha com chamada/empurrão ("{EMPURRA.search(linhas[0]).group(0)}"): ela é o gancho do vídeo, a chamada desce para o corpo')
    if not ks: return erros + [f'sem a frase de comentário com "{pal}" entre aspas no corpo']
    if len(ks) > 1: erros.append(f"{len(ks)} linhas de chamada (é 1 só, no corpo)")
    k = ks[0]
    if k == 0: erros.append("frase de comentário na 1ª linha (ela desce para o corpo)")
    elif k == 1 and len(corpo) >= 3: erros.append("frase de comentário na 2ª linha, entre o gancho e a resposta (vai da 3ª linha em diante)")
    if k >= len(corpo): erros.append("frase de comentário depois das hashtags")
    if f'"{pal}"' not in linhas[k]: erros.append(f'a linha de chamada não traz "{pal}" entre aspas')
    info = detecta(linhas[k], p) or {}
    frases, emojis = banco(p)
    if info.get("frase") not in frases: erros.append(f"frase de chamada fora do banco do perfil (perfil.yaml → legenda_cta.frases): {linhas[k][:70]!r}")
    else:
        if info.get("promessa") != prom: erros.append(f'promessa da legenda "{info.get("promessa")}" diferente da do vídeo "{prom}"')
        if tema:
            erros += [f"emoji do tema: {e_}" for e_ in tema_erros(tema)]   # bonito sem brega (26/10/2026): 1–3, sem repetir, sem enfeite/rosto/mão/seta
            na_linha = EMOJI_SEQ.findall(linhas[k])   # TODOS os emojis da linha (pega mistura tema + pool e emoji solto na promessa)
            if tema_chave(na_linha) != tema_chave(tema):
                erros.append(f'emoji da chamada {"".join(na_linha) or "(nenhum)"} ≠ emoji do tema do vídeo {tema_render(tema)} (script.json → cta.emoji_tema; na ordem, '
                             f'sem misturar com o pool nem pôr outro emoji na linha)')
            elif len(na_linha) > TEMA_MAX: erros.append(f"{len(na_linha)} emojis na linha de chamada (máx. {TEMA_MAX})")
        elif norm_emoji(info.get("emoji")) not in {norm_emoji(e) for e in emojis}: erros.append(f'emoji {info.get("emoji")} fora do pool do perfil ({" ".join(emojis)}) e a edição não tem emoji do tema')
    if com_historico and info.get("frase") in frases:
        h = [x for x in historico(p, excluir=ed, ate=ate) if x.get("cta")]
        if not tema and norm_emoji(info["emoji"]) in {norm_emoji(x["emoji"]) for x in h[-N_EMOJI:]}: erros.append(f'emoji {info["emoji"]} repetido das {N_EMOJI} últimas edições')
        if info["frase"] in {x["frase"] for x in h[-N_FRASE:]}: erros.append(f"frase de chamada repetida das {N_FRASE} últimas edições")
        if (info["frase"], norm_emoji(info["emoji"])) in {(x["frase"], norm_emoji(x["emoji"])) for x in h[-N_PAR:]}: erros.append(f"frase + emoji iguais a uma das {N_PAR} últimas edições")
    return erros


def confere_sem_cta(texto):
    """Edição SEM CTA: 1ª linha discreta e nenhuma forma de chamada na legenda inteira."""
    erros = []
    linhas = texto.split("\n")
    if linhas and EMPURRA.search(linhas[0]): erros.append(f'edição SEM CTA: 1ª linha empurrando ("{EMPURRA.search(linhas[0]).group(0)}"); é uma frase discreta do tema')
    m = CHAMADA_SEM.search(texto)
    if m: erros.append(f'edição SEM CTA com chamada na legenda ("{m.group(0)}"): sem palavra de comentário, DM, "send you", link ou urgência')
    return erros


def registra(p, ed, horario, texto):
    """reviews/legendas.jsonl (uma linha por edição; a última de cada id vale)."""
    linhas = texto.split("\n")
    k = next((i for i, l in enumerate(linhas) if RE_CTA.search(l)), None)
    info = detecta(linhas[k], p) if k is not None else None
    reg = {"id": ed, "horario": horario, "cta": bool(info), **({"frase": info["frase"], "emoji": info["emoji"], "pos": k, "palavra": info["palavra"]} if info else {}),
           "linha1": linhas[0] if linhas else ""}
    h = ROOT / p["pasta"] / "reviews" / "legendas.jsonl"; h.parent.mkdir(parents=True, exist_ok=True)
    with h.open("a", encoding="utf-8") as f_: f_.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg
