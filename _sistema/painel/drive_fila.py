"""Copia a fila de vídeos aprovados (posts/04-aprovado) de cada perfil para a pasta sincronizada do Drive (opcional).
Destino: <DRIVE_PASTA>/fila/<pasta do perfil>/AAAA-MM-DD_HHMM_<id>.mp4 (+ capa .jpg e legenda .txt). DRIVE_PASTA vem do .env (vazio = desligado).
Só mexe dentro de <DRIVE_PASTA>/fila: tira de lá o que já saiu da fila (postado). Não altera nada do projeto.
Uso: python _sistema/painel/drive_fila.py [--destino <pasta>]  (pode rodar quantas vezes quiser; pula o que já está igual)."""
import argparse, json, os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_sistema" / "orquestrador"))
from perfis_cfg import carrega


def copia(src, dst):
    if not src.exists(): return False
    if dst.exists() and dst.stat().st_size == src.stat().st_size: return False
    shutil.copy2(src, dst); return True


def destino_padrao():
    try:
        from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    except Exception: pass
    return (os.environ.get("DRIVE_PASTA") or "").strip().strip('"')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--destino", default=None)
    destino = ap.parse_args().destino or destino_padrao()
    if not destino: print("Drive desligado: .env sem DRIVE_PASTA"); return
    if not Path(destino).exists(): print(f"Drive: pasta {destino} não existe (Drive para computador fechado?)"); return
    base = Path(destino) / "fila"
    novos = apagados = 0
    for p in carrega(ROOT)["perfis"]:
        pasta = p["pasta"]; fila = ROOT / pasta / "posts" / "04-aprovado"
        if not fila.exists(): continue
        dest = base / pasta; dest.mkdir(parents=True, exist_ok=True)
        manter = set()
        for j in sorted(fila.glob("*.json")):
            try: d = json.loads(j.read_text(encoding="utf-8"))
            except Exception: continue
            nome = f"{j.stem}_{d.get('id', 'video')}"
            manter |= {nome + ".mp4", nome + ".jpg", nome + ".txt"}
            if d.get("video") and copia(ROOT / d["video"], dest / (nome + ".mp4")): novos += 1
            if d.get("capa"): copia(ROOT / d["capa"], dest / (nome + ".jpg"))
            txt = dest / (nome + ".txt")
            if d.get("legenda") and (not txt.exists() or txt.read_text(encoding="utf-8") != d["legenda"]):
                txt.write_text(d["legenda"], encoding="utf-8")
        for f in dest.iterdir():
            if f.is_file() and f.name not in manter:
                f.unlink(); apagados += 1
    print(f"Drive: {novos} vídeo(s) copiado(s), {apagados} arquivo(s) antigo(s) removido(s) de {base}")


if __name__ == "__main__":
    try: main()
    except Exception as e: print("Erro:", e); sys.exit(1)
