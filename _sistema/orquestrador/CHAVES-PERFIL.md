# Chaves do `perfil.yaml` (o que o motor lê)

Cada perfil mora em `<pasta>/` com um `perfil.yaml`. A pasta entra no motor quando aparece em `perfis.yaml → ordem`.
O motor lê o arquivo por `_sistema/orquestrador/perfis_cfg.py → carrega()`.

**Padrão.** Nas chaves marcadas **(P)**, se o perfil não define o valor, vale o de `perfis.yaml → padrao`; se o padrao também não define, vale o padrão do código. Nas outras chaves não há esse recuo para o `padrao`.

**Leitores.** As siglas da coluna "quem lê" são:

| Sigla | Arquivo |
|---|---|
| fila | `fila.py` |
| gu | `gates_universais.py` |
| orq | `orquestrador.py` |
| post | `post.py` |
| qa | `qa.py` |
| render | `render.py` |
| mix | `mix.py` |
| painel | `painel/painel.py` |
| cross | `crosspost.py` |
| dm | `dm.py` |
| ht | `hashtags.py` |
| lc | `legenda_cta.py` |
| feed | `feed_check.py` |
| grade | `grade.py` |
| serie | `serie.py` |
| pre | `precheck/precheck.py` |
| avisos | `avisos.py` |

## 1. Identidade e estado

| Chave | Obrig. | Tipo | Exemplo | Quem lê | O que faz |
|---|---|---|---|---|---|
| `pasta` | não | str | `meu-perfil` | todos | Nome da pasta. Se faltar, `perfis_cfg` usa o nome que está em `ordem`. |
| `handle` | **sim** | str | `"@meu.perfil"` | orq, post, painel, dm, fila | Conta do Instagram. O `post.py checar` confere se o token é dessa conta. |
| `prefixo` | **sim** | str `[a-z0-9]` | `mpf` | orq, post, painel, dm, avisos | Prefixo dos ids das edições (`mpf-001`). Também é o `--perfil` curto e o papel em `avisos.py`. |
| `status` | **sim** | `ativo` \| `montando` \| `fora-do-pc` | `ativo` | orq, post, painel, cross, dm | Só perfil `ativo` produz e posta. |
| `nicho` | não | str | `ciência curiosa` | painel | Texto mostrado no Painel quando o perfil está fora. |
| `cor` | não | `"#hex"` ou `[destaque, fundo]` | `["#3A5BD9", "#101830"]` | painel | Cor do cartão no Painel. Sem ela, o cartão fica cinza. |
| `idioma_conteudo` | não | str | `en`, `pt-BR` | orq, cross | Idioma do que é publicado. `pt…` faz a sessão escrever em português. Padrão: inglês. |
| `pausado` (alias `paused`) | não | bool | `false` | orq, post, painel | Suspende a produção e a publicação do perfil. `padrao.pausado` suspende todos. |
| `pausa_programada` | não | `{ate, motivo, por}` | `{ate: "2026-12-01T00:00", motivo: "férias"}` | orq, painel | Não cria vídeo até `ate`, que é a hora local do PC. Depois volta sozinho. A postagem segue. |

## 2. Agenda, fila e produção

| Chave | Obrig. | Tipo | Exemplo | Quem lê | O que faz |
|---|---|---|---|---|---|
| `horarios` | **sim** | lista `"HH:MM"` | `["09:00", "19:00"]` | fila, painel, orq | Horários de postagem no fuso `padrao.fuso`. |
| `periodos` | não | `{nome: "HH:MM"}` | `{manha: "08:00"}` | fila, serie | Com `script.periodo`, o post sai nesse horário. |
| `fila_alvo` (P) | não | int | `3` | orq, painel | Vídeos prontos em `posts/04-aprovado`. Abaixo disso, a produção repõe. |
| `producao_max_por_noite` (P) | não | int | `1` | orq | Edições por execução manual (`--perfil`). O agendador faz no máximo 1 por perfil a cada rodada. |
| `producao_auto` | não | bool | `false` | orq, painel | O agendador só produz neste perfil se estiver `true`. Ligue só depois de 1 edição de teste aprovada. |
| `producao_ate` | não | `"AAAA-MM-DD"` | `"2026-12-20"` | orq | Para de produzir quando a fila cobre este dia. |
| `producao_rotina` | não | `{hora, txt}` | `{hora: "08:00", txt: "rotina diária"}` | painel | Só o texto no Painel, para quem produz por outra rotina. |
| `fila_em_ordem` | não | bool | `false` | fila, post | A edição nunca entra antes da última da fila. Se um post atrasa, o `post.py` empurra os seguintes, para série de "parte 2". |
| `serie` | não | `{tamanho, ordem}` | `{tamanho: 3, ordem: [ana, bia]}` | fila, serie, orq | Série por personagem: `script.personagem` precisa ser o da vez. A reserva fica em `posts/03-reserva`. |
| `ferramentas_mcp_extra` | não | lista | `["mcp__x"]` | orq | Conectores MCP a mais, só para este perfil. A base vem de `padrao.ferramentas_mcp`. |

## 3. Publicação (Meta)

| Chave | Obrig. | Tipo | Exemplo | Quem lê | O que faz |
|---|---|---|---|---|---|
| `user_id_env` | sim, para postar | str | `IG_USER_ID_MPF` | post, painel, dm, meta_token | Nome da variável do `.env` com o id da conta. **Vai junto com `token_env`.** |
| `token_env` | sim, para postar | str | `IG_TOKEN_MPF` | post, painel, dm, meta_token | Nome da variável do `.env` com o token. Perfil sem `token_env` não entra no `post.py`. |
| `post_manual` | não | bool | `false` | post, painel | A pessoa posta à mão: o `post.py` não publica. O Painel move o json para `05-publicado` quando acha o reel no Instagram. |
| `conferir_postagem.minutos_depois_do_horario` | não | int | `5` | painel | Com `post_manual`, quantos minutos depois do horário o Painel procura o reel. |
| `facebook_page_id` | não | str | `"1234567890"` | post | Publica o reel também na Página do Facebook. Se falhar aqui, o post do Instagram não cai. |
| `video_host` | não | URL `*.pages.dev` | `https://x.pages.dev` | post | Com `padrao.cloudflare: true`, é o projeto Pages que hospeda a cópia do vídeo longo. Sem ela, vale `oferta.link_bio`. |

## 4. Render, capa e grade

| Chave | Obrig. | Tipo | Exemplo | Quem lê | O que faz |
|---|---|---|---|---|---|
| `composicao.edicao` | **sim** | str | `Edicao` | render | Composição do Remotion (`<pasta>/remotion/src/index.ts`) que gera o vídeo. Sem ela o render para. |
| `composicao.capa` | não | str | `Capa` | render | Composição da capa. Sem ela, a capa é um quadro da própria edição. |
| `composicao.pos` | não | str (filtro ffmpeg) | `"[0:v]noise=alls=6:allf=t[v]"` | render | Pós-processamento do vídeo mudo. `{remotion}` vira `<pasta>/remotion`. |
| `composicao.capa_sujeito` | não | bool | `false` | render | Com `<pasta>/capa_check.py`, mede a capa só com o sujeito e grava `capa_check.json`. Capa reprovada barra o QA. |
| `grade.ciclo` | não | lista `"#hex"` | `["#3A5BD9", "#F2B33D"]` | render, grade, feed, fila, post | Cores de fundo da capa, em ordem. Com 2 ou mais cores, o `feed_check` confere o feed real antes de publicar. |
| `grade.amostra_x` / `grade.amostra_y` | não | lista | `[4, 8, 12]` / `[0.78, 0.80, 0.82]` | feed | Onde medir a cor da capa. |

## 5. Ritmo e qualidade (gates do `fila.py`)

Os gates universais estão em `gates_universais.py` e valem para todo perfil. As chaves abaixo ajustam cada um.

| Chave | Obrig. | Tipo | Padrão | Quem lê | O que faz |
|---|---|---|---|---|---|
| `ritmo.gancho_ate_s` (P) | não | número | `3` | gu | Janela do gancho. Exige `script.gancho.texto` entrando até 1 s, voz começando até 1 s, nada de "olá"/vinheta e movimento na janela. |
| `ritmo.gancho_movimento_min` (P) | não | número | `0.72` | gu | Movimento mínimo do vídeo na janela do gancho, medido pela diferença entre quadros. |
| `ritmo.abertura_calma` (P) | não | bool | `false` | gu | Dispensa só a medida de movimento. Para uma edição só: `out/<id>/abertura_excecao.json`. |
| `ritmo.seguir.momento` (P) | não | `meio` \| `final` \| `nenhum` | `final` | gu | Onde fica a pausa/card de SEGUIR (`script.seguir {t, dur, texto}`). `meio` = entre 20% e 80% do vídeo. |
| `ritmo.seguir.duracao_s` (P) | não | número (mín.) ou `[mín, máx]` | `[1.5, 2.5]` | gu | Duração do card de seguir. |
| `ritmo.card_final` (P) | não | `oferta` \| `seguir` \| `nenhum` | `oferta` se houver `oferta.card`, senão `seguir` | gu | Card no fim do vídeo. `oferta` usa `script.oferta.card` ou `oferta.card`. `seguir` usa `script.seguir` no fim ou `script.card_final.tipo: seguir`. |
| `ritmo.card_final_min_s` (P) | não | número | `1.6` | gu | Tempo mínimo de card depois da última palavra (`words.json`). |
| `qualidade.hud` (P) | não | bool | `false` | gu, qa | HUD interativa: `script.hud.passos` precisa de 2 ou mais valores que mudam. Também liga o item `hud_interativa` e o gate `hud_ok` do QA. |
| `qualidade.area_segura` (P) | não | `[y0, y1, x0, x1]` | `[285, 1635, 40, 1040]` | gu, pre | Área segura do feed no quadro 1080×1920. Vale para `dados[]`, `inserts[]`, `seguir` e `hud` que tenham `caixa` ou `y`. O gate usa só y0 e y1; o precheck usa os 4 valores. |
| `qualidade.max_inserts_juntos` (P) | não | int | `2` | gu | Máximo de `dados` e `inserts` ao mesmo tempo na tela, sem contar a HUD e a legenda. |
| `qualidade.area_feed` | não | bool | `false` | render | Liga `area_segura_ok` no `render_check.json`, medido por pixel no `piscadas.py`. O resultado (`fora_da_area`) é sempre conferido pelo gate. |
| `qualidade.liga_ao_fato` (P) | não | bool | `true` | gu | `script.explicador` e `inserts[]` com `sorteado: true` precisam de `liga_ao_fato`: 1 frase de 20+ caracteres que cita o assunto. |
| `qualidade.formato_varia` (P) | não | bool | `false` | fila | O mesmo formato não fica a menos de 2 posts de distância na grade. |
| `qualidade.inserts_novos_min` | não | int | — | gu | Mínimo de `inserts[].img` novos por edição. |
| `qualidade.cena_varia` | não | bool | — | gu | `script.cena` não repete a das 2 últimas edições. |
| `qualidade.variacoes` | não | `{cenas: [...], max_planos}` | — | gu | Planos de variação (`shots[].cena`): no máximo `max_planos` por edição e nunca iguais aos da edição anterior. |
| `qualidade.gancho_banco` | não | bool | — | gu | O gancho sai de `format.json → gancho.banco` e não repete o das 3 últimas edições. |
| `qualidade.fundo_vivo` | não | bool | — | gu | Com `script.vivo`, pelo menos um elemento ligado. |
| `qualidade.grade_por_ordem` (P) | não | bool | `false` | fila, render | A cor da capa segue a ordem real de publicação (`grade.py`). Ao entrar na fila, refaz as capas seguintes. |
| `qualidade.montagem_varia` | não | bool | `false` | orq | Roda a auditoria de repetição antes de produzir e gira o formato da pauta, que nunca repete o da edição anterior. |

As chaves sem padrão (—) só ligam o gate quando estão definidas. Os achados de todos os gates do `fila.py` têm a forma `{"nivel": "erro"|"aviso", "gate", "msg"}`: erro barra a entrada na fila, aviso só é impresso. Se o QA tiver `aprovado_dono: true`, os erros de `area_segura` viram aviso.

## 6. Legenda e hashtags

| Chave | Obrig. | Tipo | Padrão | Quem lê | O que faz |
|---|---|---|---|---|---|
| `legenda.licao_rapida` (P) | não | bool | `true` | fila, post | Título, depois `1.`, `2.`, `3.` (a linha de chamada, se houver, não conta), com 120–450 caracteres sem as hashtags. |
| `legenda.caracteres` (P) | não | `[mín, máx]` | `[120, 450]` | fila | Faixa de tamanho da lição rápida. |
| `legenda.proibidas` (P) | não | lista | `[]` | fila | Palavras proibidas a mais (as de venda já são proibidas). |
| `hashtags.fixas` | não | lista de 3 | `["#a", "#b", "#c"]` | ht, fila, cross | Ligam o bloco de 6 hashtags: 3 fixas e 3 variáveis, numa linha só, depois de uma linha em branco. Sem `hashtags`: no máximo 3. |
| `hashtags.variaveis` | com `fixas` | lista (12 ou mais) | — | ht | Banco das variáveis, que não repetem nos 3 posts vizinhos. |
| `hashtags.por_tema` | não | `{tema: [...]}` | — | ht | Com `script.tema`, pelo menos 2 das 3 variáveis saem daqui. Só valem tags que também estão em `variaveis`. |
| `legenda_cta.frases` / `legenda_cta.emojis` | não | listas | padrão no `legenda_cta.py` | lc, fila | Banco da frase de comentário. Precisa de `{P}` palavra, `{X}` promessa e `{E}` emoji. |
| `sem_cta_sempre` | não | bool | `false` | fila, orq, post | Nenhuma edição nova pede comentário: `script.cta` vazio e legenda sem chamada. |
| `ab_sem_cta_padrao` | não | bool | `false` | fila | Edição sem `script.cta` e sem linha de chamada sai SEM CTA (a fixa da oferta não entra). |

## 7. Oferta, DM e votação

| Chave | Obrig. | Tipo | Exemplo | Quem lê | O que faz |
|---|---|---|---|---|---|
| `oferta.card` | não | `{tag, titulo, sub}` | `{tag: "FREE GUIDE", titulo: "…"}` | render, gu | Card final de oferta, se o script não trouxer o dele. |
| `oferta.palavra` | não | str | `GUIDE` | render, dm, painel, fila | Palavra fixa de comentário. Liga o DM e entra na lista de palavras reservadas entre perfis. |
| `oferta.cta` | não | str | `comment "GUIDE" and I'll send you the guide 📩` | fila, lc | Linha fixa de chamada (palavra e promessa para edições sem `script.cta`). |
| `oferta.emoji` | não | str | `📩` | fila | Emoji da linha de chamada. |
| `oferta.secoes` | não | `{secao: {promessa, card: {titulo, sub}}}` | — | fila, render, cta_video | Palavra POR VÍDEO (`script.cta {palavra, promessa, secao}`): confere a promessa e monta o card. |
| `oferta.card_tag` / `oferta.card_dm` | não | str | — | render | Textos do card das seções. |
| `oferta.dm_ativa` | não | bool | `false` | dm, painel | Liga o envio da DM. |
| `oferta.link_gratis` | com `dm_ativa` | URL | — | dm, painel | Link do 1º produto enviado na DM (o nome é histórico: o produto pode ser pago). |
| `oferta.link_bio` / `oferta.link_curso` / `oferta.link_dm_base` | não | URL | — | post, dm, painel | Página do perfil, link do curso, base do link da DM por vídeo. |
| `oferta.dm` / `oferta.resposta_publica` | não | str (`{link}`) | — | dm | Texto da DM e resposta pública ao comentário. |
| `oferta.dm_por_video` / `oferta.respostas_publicas` / `oferta.ancoras` | não | str / lista / dict | — | dm | Modelos da DM por vídeo (`{promessa}`, `{palavra}`, `{link}`). |
| `curso_dm` | não | bool | `false` | dm | Comentário que é só a palavra de `padrao.curso` recebe o link do curso. |
| `dm_so_votacao` | não | bool | `false` | dm, fila | Perfil sem oferta: o comentário com uma das 2 palavras de `script.votacao.opcoes` vota. A votação fecha sozinha e a vencedora vira pauta prioritária. |
| `votacao_fecha_h` / `votacao_respostas` / `votacao_variantes` | não | número / lista / bool ou dict | `24` | dm | Prazo da votação, respostas públicas e variações de escrita aceitas. |

## 8. Voz e áudio

| Chave | Obrig. | Tipo | Exemplo | Quem lê | O que faz |
|---|---|---|---|---|---|
| `voz` | não | dict (ex.: `{voice_id, modelo}`) | `{voice_id: A_DEFINIR}` | painel, producao.md | Perfil sem `voz` não tem narração. `voice_id: A_DEFINIR` aparece como pendência no Painel. A sessão de produção usa o resto pelo `producao.md`. |
| `audio.*` | não | dict | `{trilha_lufs: -22}` | mix | Substitui as metas do `mix.py` (`REGRA`): `voz_lufs`, `voz_tp`, `trilha_lufs`, `sfx_pico`, `sfx_cauda_s`, `duck_db`, `ataque_s`, `release_s`, `sfx_chave_db`, `final_lufs`, `limiter_tp`, `trilha_fade_in_s`, `trilha_fade_out_s`, `voz_filtros`, `voz_trilha_p10`, `voz_trilha_mediana`, `duck_juntar_s`. Opcionais: `duck_max_db_s`, `ambiente_max_db`, `continuo_max_db`, `ambiente_obrigatorio`, `sfx_proibidos`, `respiracao_sfx`, `haptico_sfx`, `som_por_plano`, `sfx_rms_norm`, `sfx_crest_db`, `sfx_comp_thr`, `sfx_comp_ratio`. |

## 9. QA

| Chave | Obrig. | Tipo | Padrão | Quem lê | O que faz |
|---|---|---|---|---|---|
| `qa.corte` (P) | não | número | `6.8` | qa | Nota de corte da média e de cada item com gate. |
| `qa.cronicos` (P) | não | bool | `false` | qa | Antes da rodada roda `<pasta>/cronicos.py → checar(pasta) -> {ok, graves[], avisos[]}`. Se `ok` for falso, a rodada não abre. |

O QA também tem plugins **por arquivo** (não precisam de chave): `<pasta>/qa_itens.json` com o texto dos itens, `<pasta>/reviews/licoes_recorrentes.md` com os defeitos que voltam, e `<pasta>/gate_comum.py <pasta_edicao>`, que grava `gate_comum.json {ok, criticos[], avisos[]}` para o avaliador conferir.

## 10. Cross-post (YouTube Shorts / TikTok)

Tudo fica dentro de `crosspost`. Os segredos ficam só no `.env`; as chaves `*_env` guardam o **nome** da variável.

| Chave | Tipo | Quem lê | O que faz |
|---|---|---|---|
| `crosspost.desde` | `"AAAA-MM-DD HH:MM"` | cross, painel | Só manda o que saiu no Instagram depois disso. |
| `crosspost.acervo` / `crosspost.acervo_pausado_ate` | bool / data | cross | Manda também o que já estava no ar, com o que sobrar da cota. |
| `crosspost.youtube.ativo` | bool | cross, painel | Liga o YouTube. |
| `crosspost.youtube.client_id_env` / `client_secret_env` / `refresh_token_env` | str | cross, painel | Nomes das variáveis OAuth no `.env`. |
| `crosspost.youtube.privacidade` | `public` \| `unlisted` \| `private` | cross, painel | Padrão: `public`. |
| `crosspost.youtube.projeto_google` | str | cross | Cota por projeto do Google Cloud. |
| `crosspost.youtube.idioma` / `traduzir` | str / bool | cross | Idioma do título e da descrição (padrão: `idioma_conteudo`) e se traduz. |
| `crosspost.youtube.playlists` / `playlists_descricao` | dict por formato | cross | Playlists automáticas. |
| `crosspost.youtube.thumb` | `{composicao, remotion, zona_titulo}` | cross | Thumb 16:9 por uma composição do Remotion. |
| `crosspost.youtube.capa` | bool | cross | Sobe a capa própria (exige canal verificado). |
| `crosspost.tiktok.ativo` / `privacidade` / `client_key_env` / `client_secret_env` / `refresh_token_env` / `redirect_uri` | — | cross, painel | TikTok direto. |
| `crosspost.<plat>.via: zernio` + `zernio_account_id` (+ `playlist_id`, `rascunho`) | — | cross | Publica pela Zernio (`ZERNIO_API_KEY` no `.env`). |

## 11. Valores só do `perfis.yaml → padrao`

| Chave | Padrão | Quem lê | O que faz |
|---|---|---|---|
| `fuso` | `America/New_York` | fila, post, painel | Fuso dos `horarios`. |
| `fuso_painel` | `America/Sao_Paulo` | painel | Hora mostrada no Painel. |
| `ferramentas_mcp` | `[mcp__claude_ai_ElevenLabs]` | orq | MCPs liberados para a sessão automática (`claude -p`). Lista vazia = nenhum. |
| `cloudflare` | `false` | post | `true` liga o caminho por link do vídeo longo (`npx wrangler pages deploy`, branch de prévia). |
| `voz_min_creditos` | `2000` | orq | Caracteres mínimos no ElevenLabs para abrir uma sessão (precisa de `ELEVENLABS_API_KEY`, que só lê, no `.env`). |
| `pausado`, `fila_alvo`, `producao_max_por_noite`, `producao`, `legenda`, `qa`, `ritmo`, `qualidade` | — | vários | Padrão das chaves (P) acima. `producao` é só texto no Painel. |
| `curso` | — | dm, fila | `{palavra, nome, link, dm, resposta_publica}` do curso (2ª porta do DM). A palavra fica reservada entre os perfis. |

## 12. Arquivos que o motor exige na pasta do perfil

| Arquivo | Quem lê | Conteúdo |
|---|---|---|
| `perfil.yaml` | todos | Esta tabela. |
| `producao.md` | orq, painel | Etapas de produção do perfil, que entram no prompt da sessão. Pode citar `{id}`, `{handle}`, `{pasta}`, `{perfil}`, `{idioma}` e `{cta_modo}`; chave desconhecida fica como está. Sem ele, o orquestrador para. |
| `format.json` | render, orq, gu | `duration_s: [mín, máx]` (obrigatório no render), `min_camera_planes` (padrão 3). Opcionais: `ab_cta {desde, comeca}`, `final: seguir`, `gancho.banco`. |
| `pautas.csv` | orq, fila | Colunas: `tema`, `angulo`, `formato`, `fontes` (separadas por `;`) e `usado_em` (preenchida pelo orquestrador). Opcionais: `prioridade`, `cta` (sim/nao), `palavra`, `promessa`, `gancho`, `gancho_tela`, `gancho_visual`, `periodo`. |
| `formatos.md` | orq | Opcional. Tabela `| formato | base / em teste / ativo / cortado |`; formato `cortado` não sai. |
| `remotion/` | render, piscadas | Projeto Remotion com `src/index.ts` e as composições de `composicao`. Props recebidas: `{script, words}`; a capa recebe `capa: true`, o `piscadas.py` usa `soOverlay`, o `capa_check` usa `soSujeito`. |
| `style-guide.md` | qa | Regras e lista "Nunca" que o avaliador lê (ou `script.qa_guia`). |
| `gates.py`, `cronicos.py`, `capa_check.py`, `gate_comum.py`, `qa_itens.json` | fila / qa / render | Plugins opcionais (seção 13 e seção 9). |

## 13. Plugin `<pasta>/gates.py` (gates próprios do perfil)

O `fila.py` importa `<pasta>/gates.py`, se o arquivo existir, com um nome de módulo único por perfil. Depois chama `gates(ctx)` e junta o resultado aos achados dos gates universais.

```python
def gates(ctx) -> list[dict | str]:
    s = ctx["script"]
    if len(s.get("shots", [])) < 4:
        return [{"nivel": "erro", "gate": "meu_gate", "msg": "menos de 4 planos"}]
    return []
```

**`ctx` (dicionário)**

| Chave | Tipo | Conteúdo |
|---|---|---|
| `ROOT` | `Path` | Raiz do projeto. |
| `pasta` | `Path` | `<pasta>/out/<id>`. |
| `id` | str | Id da edição. |
| `perfil` | dict | O `perfil.yaml` do perfil (com `pasta`). |
| `padrao` | dict | `perfis.yaml → padrao`. |
| `script` | dict | `script.json`, já com a legenda final (`caption`). |
| `brief` | dict \| None | `brief.json`. |
| `words` | list \| None | `words.json` (`[{w, start, end}]`). |
| `render_check` | dict \| None | `render_check.json`. |
| `mix_check` | dict \| None | `mix_check.json`. |
| `qa` | dict | `qa.json`. |
| `anteriores(n=4)` | função | `[(id, script)]` das edições na fila e no ar antes desta, da mais recente para a mais antiga. |
| `opc(chave, padrao=None)` | função | Valor pontilhado do perfil (ex.: `"ritmo.seguir.momento"`). Se o perfil não tem, vale `padrao` do `perfis.yaml`; se também não tem, o argumento `padrao`. |

**Retorno.** Uma lista de achados. Cada achado é `{"nivel": "erro" | "aviso", "gate": "<nome>", "msg": "<texto>"}`. Uma `str` solta conta como `erro`. Lista vazia = passou.

**Falha fechada.** Exceção dentro do plugin, arquivo sem a função `gates` ou achado fora do formato viram **erro**: a edição não entra na fila.

**Regras.**
- O plugin só lê. Não grava nada e não chama rede.
- Não use `sys.path` para importar outro módulo do perfil; use caminho relativo a `ctx["ROOT"] / ctx["perfil"]["pasta"]`.
- Roda só na entrada da fila. O `post.py` não reconfere.

## 14. Campos do `script.json` que os gates universais leem

| Campo | Formato | Uso |
|---|---|---|
| `gancho` | `{texto, sub?, t?}` ou str | Gancho na tela. `t` = segundo em que entra (máx. 1). |
| `seguir` | `{t, dur, texto, sub?, caixa?}` | Pausa/card de SEGUIR. |
| `oferta` | `{t0?, card: {tag, titulo, sub}}` | Card final de oferta. |
| `card_final` | `{tipo: "seguir"}` | Alternativa para o card final de seguir. |
| `dados[]` / `inserts[]` | `{t, ate, valor?, img?, x?, y?, w?, h?, caixa?: [x, y, w, h], sorteado?, liga_ao_fato?}` | Área segura, amontoado e variação. |
| `hud` | `{rotulo?, passos: [{t, v}], caixa?}` ou `{contadores: [{passos}]}` | HUD interativa. |
| `explicador` | `{liga_ao_fato}` | Cena de explicador ligada ao fato. |
| `tema`, `title`, `cena`, `vivo`, `shots[].cena` | — | Liga ao fato e variação. |
| `caption`, `cta`, `sem_cta`, `periodo`, `personagem`, `montagem`, `ab_cta`, `capa.t`, `scene.capa_t` | — | Núcleo da fila: legenda, horário, série, histórico e capa. |
