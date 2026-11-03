# 05 · Render

**Entradas:** `scene/`, `voice.mp3` (exceto perfil sem `voz`), trilha e SFX do perfil

**Saída:** `video.mp4`, `cover.jpg`, `sheet.jpg` (12 quadros), `audio_stems/` (voz, trilha, sfx)

**Passos:** Remotion renderiza o vídeo sem áudio final → mix de áudio pelas regras de `_sistema/audio-mix.md` (`python _sistema/orquestrador/mix.py <pasta>`, lê `sfx.json` gravado pela etapa 04) → mux → `faststart`.

**Gate (passa se):** 1080×1920, 30 fps, H.264 + AAC 48 kHz, duração dentro de `format.json`, sem frame preto > 0,2 s, texto dentro da área segura do feed (`piscadas.py → fora_da_area`, gate `area_segura_ok` nos perfis com `qualidade.area_feed`), card final com ≥ `ritmo.card_final_min_s` (padrão 1,6 s) depois da última palavra, e o gate de áudio de `_sistema/audio-mix.md` (`mix_check.json → passou`).

**Proibido:** re-encodar com perda acima de CRF 18; pular a mix.

**Sem piscadas:** o `render.py` roda `piscadas.py`: renderiza só textos/HUD/inserts (prop `soOverlay`) e reprova se algo aparece e some em menos de 0,4 s ou some e volta em até 0,5 s (`piscadas.json`, gate `sem_piscada_ok`). Toda composição nova precisa aceitar `soOverlay` (esconde cena, luz, vinheta e grão). Corrija a causa no código ou nos tempos do `script.json` e renderize de novo; isso não conta como rodada de QA.
