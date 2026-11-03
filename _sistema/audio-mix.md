# Mix de áudio · regra fixa de todos os perfis

A voz sempre na frente. Trilha e SFX nunca brigam com a fala. O render faz a mix em 4 passos, sempre nesta ordem. Script: `_sistema/orquestrador/mix.py <pasta_da_edicao>` (grava `mix_check.json`).

## 1. Cada faixa normalizada antes da mix
| Faixa | Alvo | Observação |
|---|---|---|
| Voz | −16 LUFS integrado, pico −3 dBTP | limpa: corte abaixo de 80 Hz, de-esser leve, compressor 3:1 |
| Trilha | −24 LUFS integrado | loop sem silêncio no início |
| SFX | pico −8 dBFS cada | sem cauda maior que 1,5 s |

## 2. Ducking (a trilha abaixa quando a voz fala)
- Sidechain da trilha pela voz: a trilha cai **10 dB** enquanto há fala, ataque 80 ms, release 400 ms.
- Nas pausas longas marcadas no roteiro a trilha volta ao nível cheio. Pausas curtas não deixam a trilha subir (`audio.duck_juntar_s`).
- SFX que caem em cima de uma palavra-chave descem 4 dB.
- **Música sem tranco:** a trilha abaixa e volta devagar; gate `ducking_suave_ok` (variação máxima da trilha em dB/s, `audio.duck_max_db_s`). Voz calma ou sussurrada pede ducking mais lento (ataque que começa antes da fala, release longo).
- Perfil sem voz: trilha e SFX por cima, sem ducking.

## 3. Master
Soma das faixas → limiter em −1,5 dBTP → normalização final a **−14 LUFS integrado** (padrão do Instagram), em duas passagens (loudnorm medido e depois aplicado).

## 4. Gate de áudio (QA técnico)
- Final entre −15 e −13 LUFS (ou `audio.final_lufs` ±1); pico ≤ −1,0 dBTP.
- Diferença voz × trilha durante a fala ≥ **12 LU em 90% das janelas** (p10) e mediana ≥ 15 LU (faixas separadas, janelas de 400 ms onde a voz está soando). Exigir em 100% reprova qualquer fala natural nos finais de palavra.
- Whisper na **mix final** (não só na voz) com erro de palavra < 5%: se a trilha atrapalhar o entendimento, reprova.
- Nenhum SFX acima da voz por mais de 300 ms (medido só onde há palavra).
- Sem silêncio > 2 s fora das pausas marcadas no roteiro.

## 5. Valores por perfil
Se precisarem ser diferentes, ficam em `<perfil>/perfil.yaml → audio` e sobrepõem a tabela (`REGRA` do `mix.py`), ex.: `audio: {sfx_pico: -11, trilha_lufs: -22}`. Também: `voz_filtros` (cadeia própria de EQ/compressão da voz), `voz_trilha_p10`, `voz_trilha_mediana`, `duck_db`, `ataque_s`, `release_s`, `duck_juntar_s`, `final_lufs`, `limiter_tp`. Lista completa: `CHAVES-PERFIL.md §8`.

## 6. SFX ambientados
- `sfx.json → ambiente`: um loop baixinho o vídeo todo (quarto, mar, cidade, conforme o perfil); gate `ambiente_ok`.
- Eventos com `db` próprio para cair por baixo da voz; SFX em cada plano (`shots[].sfx`, gate `som_por_plano_ok`).
- Som só depois da animação pronta, com os tempos medidos no render.

## 7. Transições são só um "bafinho" e nunca repetem (todos os perfis)
- **Volume:** som de transição (corte, troca de plano, câmera que passa) fica **30 dB abaixo** dos sons da história (`db` ≤ −30 no `sfx.json`): se alguém notar a transição, está alto demais. Nada de stinger, whoosh forte ou swoosh grave em transição.
- **Variação:** banco de **pelo menos 6 variações** do som de transição por perfil. Nunca a mesma variação duas vezes seguidas na edição, e nunca uma das 3 últimas usadas na edição anterior (guarde o histórico em `<perfil>/reviews/`).
- **Gate recomendado** (no `<perfil>/gates.py`): `sfx.json` com transição acima de −30 dB, ou a mesma variação repetida em sequência, reprova a edição.

## 8. Sons curtos e repetidos nascem baixos
Sons curtos e repetidos (gotas, pingos, tics de contador, pulsos de luz) e sons tonais que lembram notificação de celular (ping, "plin", pop) cansam e ficam altos quando o mix normaliza. Dê a eles um teto fixo bem abaixo dos sons da história (na faixa de −30 a −44 dB, conforme o som). Exceção: quando o som repetido é o som da própria história, ele pode subir um pouco.

## 9. Perfil só com efeitos (sem voz e sem música)
A normalização a −14 LUFS levanta os efeitos além do que o ouvido espera. Para perfil só com efeitos:
- Use `audio.final_lufs` bem mais baixo (na faixa de −23 a −30 LUFS) e `audio.limiter_tp` correspondente; o gate `lufs_ok` segue o alvo ±1.
- **Nível por loudness, não por pico:** `sfx_rms_norm: true` (cada efeito igualado pelo rms da parte ativa, `sfx_crest_db`), senão ruídos sustentados ficam muito mais altos que toques secos.
- **Compressor no barramento dos efeitos** (`sfx_comp_thr`, `sfx_comp_ratio`): nenhum som explode acima do resto.
- Fundo (ar, ambiente, sons contínuos) bem abaixo dos efeitos (`ambiente_max_db`, `continuo_max_db`).
- Se ainda parecer alto no celular: baixar só `final_lufs` e `limiter_tp`; não mexer som a som.
- Conferência antes de entregar: `mix_check.json` com o final no alvo ±1 e o pico dentro do limite.
