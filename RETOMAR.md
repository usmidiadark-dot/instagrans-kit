# RETOMAR — estado do kit (03/11/2026)

## Pronto e testado
- Motor genérico (sem nome de perfil no código; gates por perfil em `<pasta>/gates.py`): `_sistema/orquestrador/`; todas as chaves em `CHAVES-PERFIL.md`.
- `criar_perfil.py` (pasta nova a partir de `_modelo-perfil/`, registra em `perfis.yaml`), `refs.py` (refs → quadros, folhas, paleta, cortes, som).
- Modelo Remotion neutro (`_modelo-perfil/remotion`): gancho, legenda, HUD, card de seguir, card final, área segura.
- Teste em cópia limpa, em outra pasta: criar perfil → render da edição de exemplo (vídeo, capa e folha saíram) → `refs.py` com vídeo sintético.
- Instalador `instalar.ps1` (sintaxe validada; NÃO executado de ponta a ponta), CLAUDE.md, REGRAS-UNIVERSAIS.md, 4 skills, guia visual em `GUIA/index.html`.

## Pendente / não testado
- `.claude/settings.json` criado (hooks de contexto/trava/avisos com `$CLAUDE_PROJECT_DIR` + permissões); hooks rodaram sem erro fora de sessão, falta ver numa sessão real.
- `instalar.ps1` num Windows limpo (winget, Git, Node, Python, ffmpeg); QA real com avaliadores; mix/voz/post nunca rodados no kit.
- Plugin `gates.py` testado só com perfil de teste; `.mcp.json` do ElevenLabs (`uvx elevenlabs-mcp`) não conferido.
- Git: `git init` feito no kit, nada commitado nem enviado (criar o repositório privado e dar `git push`).
- Regra do Windows: caminho do kit curto (< 90 caracteres), senão o Chrome do Remotion não abre.
- Edição de teste real de um perfil novo (refs reais → estilo → vídeo) ainda não feita.
