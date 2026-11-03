"""Gera o token definitivo da Meta para um perfil, sem mostrar nenhum segredo na tela.
Antes, no .env: META_APP_ID, META_APP_SECRET, META_GRAPH_VERSION e META_TOKEN_CURTO (token de usuário gerado no
Explorador da Graph API com: instagram_basic, instagram_content_publish, instagram_manage_insights,
pages_show_list, pages_read_engagement, business_management).
Uso (na raiz do projeto):  python _sistema/orquestrador/meta_token.py --perfil <prefixo>
Faz: token curto → token de usuário de 60 dias → token da página ligada ao Instagram (não vence) →
grava IG_USER_ID_<X> e IG_TOKEN_<X> no .env e apaga o META_TOKEN_CURTO."""
from perfis_cfg import carrega  # config por perfil: <pasta>/perfil.yaml
import argparse, pathlib, sys
import requests, yaml
from dotenv import dotenv_values

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
sys.stdout.reconfigure(encoding="utf-8")

def grava_env(valores: dict, apagar=()):
    linhas = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    feitas, saida = set(), []
    for l in linhas:
        chave = l.split("=", 1)[0].strip()
        if chave in apagar: continue
        if chave in valores: saida.append(f"{chave}={valores[chave]}"); feitas.add(chave)
        else: saida.append(l)
    saida += [f"{k}={v}" for k, v in valores.items() if k not in feitas]
    ENV.write_text("\n".join(saida) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--perfil", required=True); a = ap.parse_args()
    cfg = carrega(ROOT)
    p = next(x for x in cfg["perfis"] if a.perfil in (x.get("prefixo"), x.get("handle"), x.get("pasta")))
    env = dotenv_values(ENV)
    falta = [k for k in ("META_APP_ID", "META_APP_SECRET", "META_TOKEN_CURTO") if not (env.get(k) or "").strip()]
    if falta: sys.exit(f"faltam no .env: {', '.join(falta)}")
    ver = (env.get("META_GRAPH_VERSION") or "v26.0").strip()
    g = f"https://graph.facebook.com/{ver}"
    def get(caminho, **params):
        r = requests.get(f"{g}/{caminho}", params=params, timeout=60)
        if not r.ok: sys.exit(f"erro da Meta em {caminho}: {r.json().get('error', {}).get('message', r.status_code)}")
        return r.json()
    longo = get("oauth/access_token", grant_type="fb_exchange_token", client_id=env["META_APP_ID"].strip(),
                client_secret=env["META_APP_SECRET"].strip(), fb_exchange_token=env["META_TOKEN_CURTO"].strip())["access_token"]
    paginas = get("me/accounts", fields="name,access_token,instagram_business_account{id,username}", access_token=longo).get("data", [])
    alvo = p["handle"].lstrip("@")
    pg = next((x for x in paginas if (x.get("instagram_business_account") or {}).get("username") == alvo), None)
    if not pg:
        achadas = [f'{x["name"]} → @{(x.get("instagram_business_account") or {}).get("username", "sem Instagram")}' for x in paginas]
        sys.exit(f"nenhuma página ligada a @{alvo}. Páginas que o token enxerga: {achadas or 'nenhuma (faltou pages_show_list?)'}")
    grava_env({p["user_id_env"]: pg["instagram_business_account"]["id"], p["token_env"]: pg["access_token"]}, apagar=("META_TOKEN_CURTO",))
    print(f'ok: @{alvo} ligado à página "{pg["name"]}". {p["user_id_env"]} e {p["token_env"]} gravados no .env (valores não exibidos).')
    print(f"confira com: python _sistema/orquestrador/post.py checar --perfil {p['prefixo']}")

if __name__ == "__main__":
    main()
