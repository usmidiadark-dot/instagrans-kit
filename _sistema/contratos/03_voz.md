# 03 · Voz

**Quem faz:** o Claude, dentro de uma sessão do Claude Code, pelo **MCP do ElevenLabs** (conector `creative_*`). A geração não usa chave de API: a conta é a do conector autenticado na sessão (a `ELEVENLABS_API_KEY` do `.env`, se houver, só lê o saldo de créditos). Por isso a produção automática roda como sessão do Claude Code (ver `_sistema/automacao.md §1`). **Conta certa:** se a voz falhar por crédito, confira primeiro qual workspace do ElevenLabs o conector está usando. Uma fala curta de teste NÃO prova qual conta está vinculada (passa em qualquer conta com uns poucos créditos); o que diz a conta é o workspace mostrado na tela de autorização do ElevenLabs, ou abrir no site o link do flow gerado e ver em qual workspace ele cai.

**Entradas:** `script.json` (campo `vo` de cada plano), `<perfil>/perfil.yaml → voz` (voice_id, modelo, velocidade).

**Saída** em `<perfil>/out/<id>/`:
- `voice.mp3` — narração final, já na velocidade do perfil;
- `words.json` — lista `[{ "w": "honey", "start": 0.82, "end": 1.10 }, …]`, em segundos, sobre o `voice.mp3` final;
- `voice.log.json` — voice_id, modelo, flow_id/session_id do ElevenLabs, créditos gastos, origem dos timestamps (`elevenlabs` ou `faster-whisper`).

## Passo a passo
1. Juntar o `vo` dos planos num texto só, na ordem. Pausas marcadas no roteiro viram pontuação/tags de pausa do modelo (ex.: `...` ou `[pause]` no v4) — se o perfil marca pausa antes do número, ela tem pelo menos 0,5 s. Com modelo que aceita tags de emoção, use tags por frase.
2. Gerar com `creative_generate_speech` (`voice_id` e `model_id` do `perfil.yaml` do perfil, `generations_count: 1`). Antes, `estimate_only: true` para registrar o custo no log. Nunca chamar de novo para "tentar de novo" sem que o gate tenha reprovado (cada chamada cobra).
3. Esperar com `creative_get_flow_run_status` e baixar o áudio da URL devolvida para `voice_raw.mp3`.
4. Velocidade: o MCP não tem parâmetro de velocidade. Se `velocidade ≠ 1.0`, aplicar com ffmpeg `atempo=<velocidade>` (não muda o tom) → `voice.mp3`.
5. Timestamps por palavra: se o MCP devolver alinhamento por palavra, converter para `words.json` (ajustando pela velocidade). **Se não devolver, gerar com faster-whisper** sobre o `voice.mp3` final: `python _sistema/orquestrador/voz_words.py <voice.mp3> <narracao.txt> <saida>` (`narracao.txt` = texto exato enviado ao ElevenLabs; modelo `small.en` ou maior, `word_timestamps=True`), alinhando as palavras do Whisper ao texto do roteiro para manter a grafia certa. O script junta números ditos por extenso ("three thousand" → `3,000`) e prende as bordas das palavras aos silêncios reais do áudio, para a legenda não entrar antes da fala.
6. Conferir (gate).

## Gate (passa se)
- Duração dentro de ±10% do previsto no roteiro; voz + hold final dentro de `format.json → duration_s`.
- Pausa marcada antes do número ≥ 0,5 s, quando houver (medida com `silencedetect`).
- Whisper transcreve o `voice.mp3` com erro de palavra (WER) < 5% contra o texto do roteiro.
- `words.json` cobre todas as palavras do roteiro, em ordem, sem tempos sobrepostos.
- Sem silêncio > 2 s fora das pausas marcadas.

**Proibido:** mudar a voz, o modelo ou a velocidade do perfil; usar chave de API ou outro provedor de voz; gerar várias tomadas "para escolher" na produção automática (a escolha de voz é feita uma vez, com o dono, e fica no `perfil.yaml` do perfil).

**Se reprovar:** uma nova geração (limite de 2, `automacao.md §3`); depois gravar `fail.json` com etapa, motivo e últimas saídas, e parar.
