"""Carrega a configuração dos perfis.
Cada perfil tem o seu arquivo: <pasta>/perfil.yaml (o mesmo conteúdo que era um item da lista `perfis:` do perfis.yaml).
O perfis.yaml da raiz guarda só o que vale para todos: `padrao` (valores-base) e `ordem` (ordem dos perfis nos relatórios e no Painel).
O dado devolvido tem a MESMA forma de antes ({"padrao": {...}, "perfis": [{...}, ...]}), então quem lia o perfis.yaml só troca a linha de leitura:
    from perfis_cfg import carrega      # (o diretório _sistema/orquestrador já está no sys.path dos scripts de lá)
    CFG = carrega(ROOT)
Valor de um perfil que vale só para ele (fila_alvo, producao_max_por_noite, horarios...) fica no arquivo dele e não influencia os outros;
quem precisa de "o valor deste perfil, senão o padrão" usa `valor(CFG, perfil, "fila_alvo", 3)`."""
import pathlib
import yaml


def _ler(caminho):
    return yaml.safe_load(pathlib.Path(caminho).read_text(encoding="utf-8")) or {}


def carrega(root=None, so=None):
    """`so` = pasta do perfil que o chamador pediu: se o perfil.yaml DELE estiver quebrado, o erro sobe (ninguém trabalha com config errada).
    Qualquer OUTRO perfil quebrado é pulado com aviso (stderr + logs/perfis_cfg_erros.log) e os demais seguem funcionando."""
    import sys, datetime
    root = pathlib.Path(root) if root else pathlib.Path(__file__).resolve().parents[2]
    base = _ler(root / "perfis.yaml")   # a raiz quebrada derruba tudo mesmo: sem ela não há ordem nem padrão
    perfis = []
    for pasta in base.get("ordem") or []:
        arq = root / pasta / "perfil.yaml"
        if not arq.exists():  # perfil que mora em outra máquina: _sistema/perfis_fora/<pasta>.yaml
            arq = root / "_sistema" / "perfis_fora" / f"{pasta}.yaml"
        try:
            d = _ler(arq); d.setdefault("pasta", pasta); perfis.append(d)   # `pasta` = nome da pasta, se o perfil.yaml não disser
        except Exception as e:
            if so and so == pasta: raise
            msg = f"AVISO perfis_cfg: perfil '{pasta}' PULADO, {arq.relative_to(root) if arq.is_relative_to(root) else arq} não carregou ({type(e).__name__}: {str(e)[:300]}). Os outros perfis seguem."
            print(msg, file=sys.stderr)
            try:
                lg = root / "logs"; lg.mkdir(exist_ok=True)
                with (lg / "perfis_cfg_erros.log").open("a", encoding="utf-8") as f_: f_.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}" + chr(10))
            except Exception: pass
    return {"padrao": base.get("padrao", {}), "perfis": perfis}


def valor(cfg, perfil, chave, padrao_final=None):
    """Valor do perfil para `chave`; se ele não define, o `padrao` global; senão `padrao_final`."""
    if chave in perfil: return perfil[chave]
    return cfg.get("padrao", {}).get(chave, padrao_final)
