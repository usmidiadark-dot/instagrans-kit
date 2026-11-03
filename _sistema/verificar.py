"""Confere se a instalação do kit está completa. Não muda nada, não usa rede.
Uso (na raiz do kit):  python _sistema/verificar.py [--json]
Saída: uma linha por item (OK / FALTA / AVISO) com o que fazer. Código de saída 1 se faltar algo obrigatório."""
import importlib, json, shutil, subprocess, sys, os, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
itens = []  # (nivel, nome, dica)


def ok(nome): itens.append(("OK", nome, ""))
def falta(nome, dica): itens.append(("FALTA", nome, dica))
def aviso(nome, dica): itens.append(("AVISO", nome, dica))


def achar(cmd):
    p = shutil.which(cmd)
    if p or os.name != "nt":
        return p
    base = os.environ.get("LOCALAPPDATA", "")
    for g in glob.glob(str(Path(base) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg*" / "**" / (cmd + ".exe")), recursive=True):
        return g
    return None


def versao(cmd, *args):
    try:
        r = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=20, shell=(os.name == "nt" and cmd.lower().endswith((".cmd", ".bat"))))
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return ""


# 1. ferramentas
if sys.version_info >= (3, 10): ok(f"Python {sys.version.split()[0]}")
else: falta("Python 3.10+", "instale o Python 3.12 (instalar.ps1)")
for c, dica in (("node", "winget install OpenJS.NodeJS.LTS"), ("npm", "vem com o Node"), ("ffmpeg", "winget install Gyan.FFmpeg"),
                ("ffprobe", "vem com o ffmpeg"), ("git", "winget install Git.Git")):
    p = achar(c)
    ok(f"{c} ({versao(p, '-version' if c.startswith('ff') else '--version')[:40]})") if p else falta(c, dica + " e reabra o terminal")
if achar("claude"): ok("claude (Claude Code)")
else: aviso("claude", "instale o Claude Code e entre na conta (https://claude.com/claude-code)")

# 2. pacotes Python
pacotes = {"yaml": "pyyaml", "jsonschema": "jsonschema", "requests": "requests", "dotenv": "python-dotenv", "PIL": "pillow",
           "numpy": "numpy", "scipy": "scipy", "soundfile": "soundfile", "pyloudnorm": "pyloudnorm"}
for mod, pip in pacotes.items():
    try:
        importlib.import_module(mod); ok(f"pacote {pip}")
    except Exception:
        falta(f"pacote {pip}", "python -m pip install -r _sistema/orquestrador/requirements.txt")

# 3. pasta e arquivos do kit
n = len(str(ROOT))
if n <= 90: ok(f"caminho do kit ({n} caracteres)")
else: falta(f"caminho do kit longo ({n})", "mova para algo curto, ex.: C:\\INSTAGRANS-KIT")
for rel in ("CLAUDE.md", "REGRAS-UNIVERSAIS.md", "perfis.yaml", "_modelo-perfil/perfil.yaml", "_sistema/orquestrador/orquestrador.py",
            "_sistema/orquestrador/fila.py", "_sistema/orquestrador/render.py", "_sistema/orquestrador/criar_perfil.py", "_sistema/orquestrador/refs.py"):
    ok(rel) if (ROOT / rel).exists() else falta(rel, "baixe o kit de novo (git pull) — arquivo do motor sumiu")
for s in ("criar-perfil", "analisar-refs", "produzir", "qa"):
    ok(f"skill {s}") if (ROOT / ".claude" / "skills" / s / "SKILL.md").exists() else falta(f"skill {s}", "git pull")

# 4. trava do projeto (hooks)
cfg = ROOT / ".claude" / "settings.json"
try:
    j = json.loads(cfg.read_text(encoding="utf-8"))
    hooks = [h["command"] for g in j.get("hooks", {}).values() for b in g for h in b.get("hooks", [])]
    ok(f".claude/settings.json ({len(hooks)} hooks)")
except Exception as e:
    falta(".claude/settings.json", f"git pull ({e.__class__.__name__})")

# 5. .env e perfis
ok(".env") if (ROOT / ".env").exists() else falta(".env", "copie .env.example para .env e preencha o que for usar")
try:
    import yaml
    y = yaml.safe_load((ROOT / "perfis.yaml").read_text(encoding="utf-8")) or {}
    ordem = y.get("ordem") or []
    ok(f"perfis.yaml ({len(ordem)} perfis)")
    for p in ordem:
        d = ROOT / p
        if not (d / "perfil.yaml").exists():
            falta(f"perfil {p}", f"{p}/perfil.yaml não existe"); continue
        rm = d / "remotion"
        if not (rm / "node_modules").exists(): falta(f"{p}: remotion", f"cd {p}/remotion && npm install")
        elif not glob.glob(str(rm / "node_modules" / ".remotion" / "chrome-headless-shell" / "**" / "chrome-headless-shell*"), recursive=True):
            falta(f"{p}: navegador do Remotion", f"cd {p}/remotion && npx remotion browser ensure")
        else: ok(f"{p}: remotion + navegador")
        pa = yaml.safe_load((d / "perfil.yaml").read_text(encoding="utf-8")) or {}
        if pa.get("producao_auto"): aviso(f"{p}: producao_auto ligado", "produz sozinho: confirme que é isso mesmo")
        else: ok(f"{p}: producao_auto desligado")
except Exception as e:
    falta("perfis.yaml", str(e)[:80])

if "--json" in sys.argv:
    print(json.dumps([{"nivel": a, "item": b, "dica": c} for a, b, c in itens], ensure_ascii=False, indent=1))
else:
    for a, b, c in itens:
        print(f"[{a:5}] {b}" + (f"  ->  {c}" if c else ""))
    nf = sum(1 for a, _, _ in itens if a == "FALTA")
    print(f"\n{'Tudo certo.' if not nf else str(nf) + ' item(ns) faltando: resolva e rode de novo.'}")
sys.exit(1 if any(a == "FALTA" for a, _, _ in itens) else 0)
