"""Copia o vídeo final aprovado para o Google Drive (pasta sincronizada do Drive para computador; opcional).
Destino: <DRIVE_PASTA>/<pasta do perfil>/<id>.mp4. Refeita: o arquivo novo substitui e o antigo vai para <perfil>/anteriores/<id>_<AAAAMMDD-HHMMSS>.mp4.
NUNCA bloqueia o post: qualquer falha vira AVISO (caixa _sistema/avisos) e a função devolve False. Copia, nunca move nem apaga o original.
Config: .env → DRIVE_PASTA=<pasta sincronizada do Drive>  (vazio = desligado, sem aviso).
Uso: python _sistema/orquestrador/drive.py enviar <perfil_pasta> <id>"""
import datetime as dt, hashlib, os, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _sha(f):
    h = hashlib.sha1()
    with open(f, "rb") as a:
        for b in iter(lambda: a.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def _aviso(titulo, mudou):
    try:
        subprocess.run([sys.executable, str(ROOT / "_sistema" / "avisos.py"), "criar", "--de", "sistema", "--para", "sistema", "--titulo", titulo, "--mudou", mudou,
                        "--conferir", "Ver _sistema/orquestrador/drive.py e o .env (DRIVE_PASTA); o post NÃO foi bloqueado."], capture_output=True, timeout=30)
    except Exception: pass

def enviar(perfil_pasta, ed):
    """True se o vídeo está no Drive (novo, substituído ou igual); False em qualquer falha ou se desligado. Nunca levanta exceção."""
    try:
        try:
            from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
        except Exception: pass
        base = (os.environ.get("DRIVE_PASTA") or "").strip().strip('"')
        if not base: return False   # desligado até alguém instalar o Drive e preencher DRIVE_PASTA
        origem = ROOT / perfil_pasta / "out" / ed / "video.mp4"
        if not origem.exists(): _aviso(f"Drive: sem vídeo de {ed}", f"{origem} não existe; nada enviado."); return False
        pb = pathlib.Path(base)
        if not pb.exists(): _aviso("Drive: pasta não encontrada", f"DRIVE_PASTA={base} não existe (Drive para computador fechado ou deslogado?). Edição {ed} não enviada."); return False
        dest = pb / perfil_pasta / f"{ed}.mp4"; dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.stat().st_size == origem.stat().st_size and _sha(dest) == _sha(origem): return True
            ant = dest.parent / "anteriores"; ant.mkdir(exist_ok=True)
            shutil.move(str(dest), str(ant / f"{ed}_{dt.datetime.now():%Y%m%d-%H%M%S}.mp4"))
        shutil.copy2(origem, dest)
        return dest.exists() and dest.stat().st_size == origem.stat().st_size
    except Exception as e:
        _aviso(f"Drive: falha ao enviar {ed}", f"{type(e).__name__}: {e}"); return False

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "enviar": print("ok" if enviar(sys.argv[2], sys.argv[3]) else "NÃO enviado")
    else: print(__doc__)
