"""Cliente mínimo da API Zernio (https://zernio.com/api/v1). Chave em ZERNIO_API_KEY (.env).

Uso: python zernio.py contas   -> lista contas conectadas (só leitura, não publica nada)
Docs: https://zernio.com/llms.txt
"""
import json, os, sys, urllib.request, urllib.error
from pathlib import Path

BASE = "https://zernio.com/api/v1"


def _chave():
    k = os.environ.get("ZERNIO_API_KEY")
    if not k:
        env = Path(__file__).resolve().parents[2] / ".env"
        if env.exists():
            for linha in env.read_text(encoding="utf-8").splitlines():
                if linha.startswith("ZERNIO_API_KEY="):
                    k = linha.split("=", 1)[1].split("#")[0].strip()
    if not k:
        raise SystemExit("ZERNIO_API_KEY não definida no .env")
    return k


def chamar(metodo, caminho, corpo=None):
    req = urllib.request.Request(
        BASE + caminho, method=metodo,
        data=json.dumps(corpo).encode() if corpo is not None else None,
        headers={"Authorization": f"Bearer {_chave()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Zernio {e.code}: {e.read().decode()[:500]}")


def contas():
    return chamar("GET", "/accounts")


def criar_post(texto, plataformas, agendar_para=None, agora=False):
    """plataformas: [{"platform": "instagram", "accountId": "..."}]. Sem horário e sem agora = rascunho."""
    corpo = {"content": texto, "platforms": plataformas}
    if agora:
        corpo["publishNow"] = True
    elif agendar_para:
        corpo["scheduledFor"] = agendar_para
    return chamar("POST", "/posts", corpo)


if __name__ == "__main__":
    if sys.argv[1:] == ["contas"]:
        print(json.dumps(contas(), indent=2, ensure_ascii=False))
    else:
        print(__doc__)
