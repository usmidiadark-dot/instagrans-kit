"""Cria uma pasta de perfil nova a partir de _modelo-perfil/ e registra em perfis.yaml -> ordem.

Uso (na raiz do kit):
  python _sistema/orquestrador/criar_perfil.py <pasta> --handle @meu.perfil [--prefixo mpf] [--idioma en] [--nicho "..."] [--sem-npm]

O perfil nasce com producao_auto: false. Nada e postado. Proximo passo: refs/ + refs.py analisar (skill analisar-refs).
"""
import argparse, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORA = shutil.ignore_patterns("node_modules", "out", "__pycache__", ".git")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta", help="nome da pasta (minusculas, sem espaco/acento; nao renomeie depois)")
    ap.add_argument("--handle", required=True, help="@ do Instagram, ex.: @meu.perfil")
    ap.add_argument("--prefixo", help="ids das edicoes (padrao: 3 primeiras letras da pasta)")
    ap.add_argument("--idioma", default="en")
    ap.add_argument("--nicho", default="")
    ap.add_argument("--sem-npm", action="store_true", help="nao rodar npm install no remotion do perfil")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.pasta):
        sys.exit("Nome de pasta invalido: use minusculas, numeros e hifen.")
    prefixo = (a.prefixo or re.sub(r"[^a-z0-9]", "", a.pasta)[:3]).lower()
    if not re.fullmatch(r"[a-z0-9]+", prefixo):
        sys.exit("Prefixo invalido: so letras minusculas e numeros.")
    destino, modelo = ROOT / a.pasta, ROOT / "_modelo-perfil"
    if destino.exists():
        sys.exit(f"{destino} ja existe.")
    if not modelo.is_dir():
        sys.exit("_modelo-perfil/ nao encontrado.")

    cfgp = ROOT / "perfis.yaml"
    txt = cfgp.read_text(encoding="utf-8")
    m = re.search(r"^ordem:\s*\[(.*?)\](.*)$", txt, re.M)
    if not m:
        sys.exit("perfis.yaml sem a linha 'ordem: [...]'.")
    atuais = [x.strip() for x in m.group(1).split(",") if x.strip()]
    if a.pasta in atuais:
        sys.exit("Ja esta em perfis.yaml -> ordem.")

    shutil.copytree(modelo, destino, ignore=IGNORA)
    subs = {
        "{{HANDLE}}": a.handle if a.handle.startswith("@") else "@" + a.handle,
        "{{PREFIXO}}": prefixo, "{{PREFIXO_UP}}": prefixo.upper(),
        "{{PASTA}}": a.pasta, "{{NICHO}}": a.nicho, "{{IDIOMA}}": a.idioma,
        "{{DATA}}": date.today().strftime("%d/%m/%Y"),
    }
    for f in destino.rglob("*"):
        rel = f.relative_to(destino).parts
        if not f.is_file() or f.suffix.lower() not in {".md", ".yaml", ".yml", ".txt", ".csv", ".json"}:
            continue
        if rel[0] == "remotion" and f.name != "README.md":
            continue
        if True:
            try:
                t = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            n = t
            for k, v in subs.items():
                n = n.replace(k, v)
            if n != t:
                f.write_text(n, encoding="utf-8")

    novo = ", ".join(atuais + [a.pasta])
    cfgp.write_text(txt[: m.start()] + f"ordem: [{novo}]{m.group(2)}" + txt[m.end():], encoding="utf-8")

    env = ROOT / ".env.example"
    print(f"Perfil criado: {destino}")
    print(f"Registrado em perfis.yaml. Variaveis do .env a criar depois: IG_USER_ID_{prefixo.upper()} e IG_TOKEN_{prefixo.upper()}")
    if not a.sem_npm and (destino / "remotion" / "package.json").exists():
        npm = shutil.which("npm")
        if npm:
            print("npm install no remotion do perfil...")
            subprocess.run([npm, "install"], cwd=destino / "remotion", shell=(sys.platform == "win32"))
            subprocess.run([npm, "exec", "--", "remotion", "browser", "ensure"], cwd=destino / "remotion", shell=(sys.platform == "win32"))
        else:
            print("npm nao encontrado: rode instalar.ps1 ou 'npm install' em", destino / "remotion")
    print(f"Proximo passo: ponha videos em {a.pasta}/refs/ e rode: python _sistema/orquestrador/refs.py analisar {a.pasta}")


if __name__ == "__main__":
    main()
