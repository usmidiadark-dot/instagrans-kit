"""Cor da capa pela ORDEM REAL DE PUBLICAÇÃO (regras-gerais §1 "Grade do perfil bonita").
Antes a cor saía de quantas edições já tinham cor na hora de produzir; como se produz várias ao mesmo tempo, refazem-se edições e há
posts fora de hora, a ordem de produção não bate com a da grade e saíam vizinhas da mesma cor.
Agora a posição de um post = quantos posts do perfil (publicados + na fila) vêm antes dele por horário; a cor = ciclo[posição % tamanho].
Cada coluna da grade (3 colunas) fica de uma cor, porque a grade lê da esquerda para a direita, do mais novo para o mais velho.
  cor(perfil_pasta, horario=None, ignorar=None)  → cor esperada (sem horario = a próxima da fila, depois de todos)
  acertar_fila(perfil_pasta, refazer_todas=False) → corrige o script.json de cada edição da fila e refaz só a capa (render.py --so-capa)
Uso:  python _sistema/orquestrador/grade.py <perfil_pasta> [--refazer]"""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import json, pathlib, re, subprocess, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _ciclo(perfil_pasta):
    p = next((x for x in carrega(ROOT)["perfis"] if x.get("pasta") == perfil_pasta), {})
    return (p.get("grade") or {}).get("ciclo") or []

def sequencia(perfil_pasta):
    """[(horario, id)] de tudo que está publicado ou na fila, em ordem de horário; o mesmo id em duas pastas conta uma vez (o da fila vale)."""
    vistos = {}
    for d in ("05-publicado", "04-aprovado"):
        for f in (ROOT / perfil_pasta / "posts" / d).glob("*.json"):
            if f.name.startswith("._"): continue
            try: it = json.loads(f.read_text(encoding="utf-8")); vistos[it["id"]] = it.get("horario") or f.name[:15].replace("_", " ")
            except Exception: pass
    return sorted((h, i) for i, h in vistos.items())

def cor(perfil_pasta, horario=None, ignorar=None):
    ciclo = _ciclo(perfil_pasta)
    if not ciclo: return None
    seq = [(h, i) for h, i in sequencia(perfil_pasta) if i != ignorar]
    n = len(seq) if horario is None else sum(1 for h, _ in seq if h < horario)
    return ciclo[n % len(ciclo)]

def acertar_fila(perfil_pasta, refazer_todas=False):
    """Para cada edição da fila (não publicada): cor esperada pela posição; se o script.json tem outra, corrige e refaz a capa.
    refazer_todas: refaz a capa mesmo com a cor certa (mudança de layout da capa)."""
    ciclo = _ciclo(perfil_pasta); feitos = []
    if len(ciclo) < 2: return feitos
    fila = {}
    for f in (ROOT / perfil_pasta / "posts" / "04-aprovado").glob("*.json"):
        if f.name.startswith("._"): continue
        it = json.loads(f.read_text(encoding="utf-8")); fila[it["id"]] = it["horario"]
    for ed, h in sorted(fila.items(), key=lambda kv: kv[1]):
        pasta = ROOT / perfil_pasta / "out" / ed; arq = pasta / "script.json"
        if not arq.exists(): continue
        s = json.loads(arq.read_text(encoding="utf-8"))
        if not s.get("capa"): continue
        esperada = cor(perfil_pasta, h, ignorar=ed)
        if (s["capa"].get("fundo") or "").upper() == esperada.upper() and not refazer_todas: continue
        antes = s["capa"].get("fundo"); s["capa"]["fundo"] = esperada
        arq.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "_sistema" / "orquestrador" / "render.py"), str(pasta), "--so-capa"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        feitos.append({"id": ed, "horario": h, "de": antes, "para": esperada, "capa_ok": r.returncode == 0, "saida": (r.stdout or r.stderr)[-300:]})
    return feitos

if __name__ == "__main__":
    pf = sys.argv[1]
    if "--refazer" in sys.argv or "--so-cores" in sys.argv:
        for x in acertar_fila(pf, refazer_todas="--refazer" in sys.argv): print(json.dumps(x, ensure_ascii=False))
    else:
        for h, i in sequencia(pf): print(h, i, cor(pf, h, ignorar=i))
        print("próxima:", cor(pf))
