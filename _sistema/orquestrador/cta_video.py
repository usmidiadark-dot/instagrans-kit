"""Palavra de comentário POR VÍDEO (contrato geral em _sistema/palavras-comentario.md), para os perfis que ligam
`perfil.yaml → oferta.secoes`. Dá o `script.json → cta`, o `oferta` do card final (palavra + textos da seção),
o instante do card (a hora em que a voz diz "Comment") e a 1ª linha da legenda. As seções são as partes do produto de entrada; os textos
nunca citam preço, "free", "course" ou "bio".

    from cta_video import chamada
    c = chamada("abc", "WATER", "water", words)  # prefixo do perfil, palavra, seção     # words = out/<id>/words.json, com a chamada no fim da voz
    c["cta"] -> script["cta"] · c["oferta"] -> card · c["cardT"] · c["fim"] (hold depois da última palavra) · c["linha"] (1ª linha da legenda)

A narração termina com: "Comment PALAVRA and I'll send you <promessa da seção>." (a promessa é a de oferta.secoes[secao].promessa)."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import pathlib, re, yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _norm(w):
    return re.sub(r"[^a-z]", "", str(w).lower())


def oferta_do_perfil(prefixo):
    cfg = carrega(ROOT)
    return next(p for p in cfg["perfis"] if p.get("prefixo") == prefixo).get("oferta") or {}


def inicio_da_chamada(words, palavra):
    ws = [_norm(w["w"]) for w in words]
    ks = [k for k in range(len(ws) - 1) if ws[k] == "comment" and ws[k + 1] == palavra.lower()]
    if not ks: raise SystemExit(f'words.json sem "Comment {palavra.upper()}": a narração precisa terminar com a chamada (rode voz_words.py depois da voz)')
    return words[ks[-1]]["start"]


def chamada(prefixo, palavra, secao, words, hold_s=2.4, estilo=None, emoji_tema=...):   # emoji_tema: 1 a 3 emojis do assunto do vídeo ("🐊🦈" ou lista) ou None (vai para script.cta; regra em legenda_cta.tema_erros)
    of = oferta_do_perfil(prefixo)
    sec = of["secoes"][secao]
    pal = palavra.upper()
    inicio = inicio_da_chamada(words, pal)
    card = {"tag": sec["card"].get("tag") or of.get("card_tag") or "FIELD FILE", "titulo": sec["card"]["titulo"], "sub": sec["card"]["sub"], "dm": "and I'll send it to your DMs"}
    return {
        "cta": {"palavra": pal, "promessa": sec["promessa"], "secao": secao, **({} if emoji_tema is ... else {"emoji_tema": emoji_tema})},
        "oferta": {"palavra": pal, "card": card},
        "cardT": round(inicio + 0.05, 2),                 # o card entra com o "Comment"; a palavra estoura 0,25–0,6 s depois, quando a voz a diz
        "fim": round(words[-1]["end"] + hold_s, 2),
        "linha": f'💬 comment "{pal}" and I\'ll send you {sec["promessa"]} {of.get("emoji", "")}'.rstrip(),
        "fala": f"Comment {pal} and I'll send you {sec['promessa']}.",
        # card final do catálogo (cards_cta.tsx): hq["cta"]; estilo = montagem.card (o sorteio por edição); sem estilo = o card padrão antigo
        "hq_cta": {"estilo": estilo or "padrao", "palavra": pal, "titulo": sec["card"]["titulo"], "sub": sec["card"]["sub"], "promessa": sec["promessa"], "dm": "and I'll send it to your DMs"},
    }
