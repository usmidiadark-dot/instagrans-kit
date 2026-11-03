"""Hook UserPromptSubmit: avisa a conversa para abrir sessao nova quando ela ficou grande.

Regra (CLAUDE.md, "Economia de tokens e sessoes", item 1): conversa longa gasta limite
porque cada resposta reenvia tudo. Aqui o aviso e automatico: se a transcricao passa do
limite, injeta uma instrucao no contexto (no maximo 1 vez a cada 8 mensagens por conversa).
Nao mexe na producao automatica (`claude -p` abre conversa pequena, nunca chega no limite).
"""
import json
import os
import sys
import time
from pathlib import Path

LIMITE_TOKENS = 400_000    # contexto REAL (usage da última resposta); ~40% de uma janela de 1M
LIMITE_BYTES = 1_600_000   # só reserva, quando a transcrição não traz usage
A_CADA = 8                 # repete o aviso a cada N mensagens
ESTADO = Path(__file__).resolve().parents[2] / "logs" / "ctx-guard.json"

AVISO = (
    "AVISO AUTOMATICO (ctx_guard): esta conversa ja esta grande (~{mb} de contexto) e cada "
    "resposta reenvia tudo, o que gasta o limite do plano. Regra: NAO abra sessao nova. "
    "Ao terminar o que esta fazendo agora: (a) atualize o RETOMAR.md do perfil; (b) solte a trava das "
    "edicoes que esta conversa pegou (travas.py soltar <id>); (c) diga ao usuario numa linha so: "
    "'Contexto grande: de /compact (continua daqui) ou /clear (recomeca; retomar com: Leia <perfil>/RETOMAR.md e continue)'; "
    "(d) pare de trabalhar na tarefa ate ele responder. Se ele esta no meio de um pedido que cabe numa resposta, responda e avise logo depois."
)


def contexto_real(caminho):
    """Tokens que a última resposta do modelo reenviou (input + cache). Lê só o fim do arquivo: a transcrição pesa
    por causa de saídas de ferramentas e imagens, que nem sempre estão no contexto (28/10/2026: 17% de contexto abriu sessão nova)."""
    try:
        with open(caminho, "rb") as f:
            f.seek(0, 2); f.seek(max(0, f.tell() - 600_000))
            linhas = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return None
    for linha in reversed(linhas):
        if '"usage"' not in linha:
            continue
        try:
            u = (json.loads(linha).get("message") or {}).get("usage") or {}
        except Exception:
            continue
        t = sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        if t:
            return t
    return None


def main():
    try:
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return
    caminho = dados.get("transcript_path")
    sid = dados.get("session_id", "?")
    if not caminho or not os.path.exists(caminho):
        return
    tamanho = os.path.getsize(caminho)
    tokens = contexto_real(caminho)
    if tokens is not None:
        if tokens < LIMITE_TOKENS:
            return
    elif tamanho < LIMITE_BYTES:
        return
    try:
        estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        estado = {}
    n = estado.get(sid, {}).get("n", 0)
    estado[sid] = {"n": n + 1, "t": int(time.time()), "bytes": tamanho}
    try:
        ESTADO.parent.mkdir(exist_ok=True)
        ESTADO.write_text(json.dumps(estado), encoding="utf-8")
    except Exception:
        pass
    if n % A_CADA != 0:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": AVISO.format(mb=(f"{tokens // 1000} mil tokens" if tokens is not None else f"{tamanho / 1_000_000:.1f} MB de historico"))}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
