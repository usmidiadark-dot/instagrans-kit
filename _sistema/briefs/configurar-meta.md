# Ligar a postagem automática do Instagram (Graph API da Meta)

Quem faz os cliques é a pessoa; o Claude guia **um passo por vez**, espera confirmar, e nunca digita senha, token ou segredo no lugar dela. Segredos só no `.env`.

1. O @ do perfil precisa ser conta **profissional** (Criador ou Empresa) e estar ligado a uma **Página do Facebook** (celular: Editar perfil → Página).
2. Em developers.facebook.com: criar um app (tipo Empresa) com os produtos "Instagram" e "Facebook Login". Anotar `META_APP_ID` e `META_APP_SECRET`.
3. No Explorador da Graph API, com o app: gerar token com as permissões `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `instagram_manage_messages`, `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `business_management`. Esse é o token curto.
4. No `.env`: `META_APP_ID`, `META_APP_SECRET`, `META_GRAPH_VERSION` (confirme a versão atual da Graph API), `META_TOKEN_CURTO`, e os nomes `IG_USER_ID_<PREFIXO>` / `IG_TOKEN_<PREFIXO>` que estão em `perfil.yaml → user_id_env / token_env`.
5. Trocar pelo token longo: `python _sistema/orquestrador/meta_token.py --perfil <prefixo>` (grava o definitivo no `.env` e apaga o curto).
6. Conferir **sem postar**: `python _sistema/orquestrador/post.py checar --perfil <prefixo>` → `"ok": true`, username certo, cota e dias até o token vencer.
7. Só depois do perfil aprovado: teste de publicação **a pedido da pessoa** (`post.py publicar <item>`), conferindo a capa no Instagram.
