"""Hook UserPromptSubmit: mostra avisos pendentes entre conversas (max 5, 1 linha cada). Vazio = nada impresso.
Pula nas sessoes automaticas (INSTAGRANS_AUTO=1). Mesmo formato de saida do ctx_guard.py."""
import json
import os
import sys
from pathlib import Path

PEND = Path(__file__).resolve().parent / "avisos" / "pendentes"


def main():
    if os.environ.get("INSTAGRANS_AUTO") == "1":
        return
    try:
        sys.stdin.buffer.read()
    except Exception:
        pass
    av = []
    try:
        for f in sorted(PEND.glob("*.json")):
            try:
                av.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    except Exception:
        return
    if not av:
        return
    try:
        import avisos as _av; papeis = _av.PAPEIS
    except Exception:
        papeis = ["sistema", "geral"]
    linhas = []
    for a in av[:5]:
        falta = [p for p in a["para"] if p not in a.get("conferido_por", [])]
        para = "todos" if len(a["para"]) >= len(papeis) else ",".join(a["para"])
        linhas.append(f'- {a["id"]} | {a["de"]}->{para} | {a["titulo"]} | falta: {",".join(falta)}')
    extra = f"\n(+{len(av) - 5} outros: python _sistema/avisos.py listar)" if len(av) > 5 else ""
    txt = ("AVISOS PENDENTES entre conversas: leia so os do seu papel (" + ", ".join(papeis) + "), "
           "confira a documentacao citada e marque com: python _sistema/avisos.py conferido --id ID --papel SEU_PAPEL "
           "(detalhes no .json em _sistema/avisos/pendentes/).\n" + "\n".join(linhas) + extra)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": txt}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
