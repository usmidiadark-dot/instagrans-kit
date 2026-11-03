# Regras universais (todo perfil, sem exceção)

Cada regra abaixo vira **checagem automática** no `fila.py` (ou no QA). Valores ajustáveis ficam em `<perfil>/perfil.yaml → ritmo / qualidade / audio`.

## 1. Gancho forte nos primeiros segundos
- Em **0–3 s** o assunto aparece grande e legível; sem som e sem legenda, em 1 segundo dá para dizer o que é.
- A primeira frase é uma pergunta, um número ou uma promessa concreta (nada de "olá", logo, vinheta).
- Movimento já no primeiro quadro; o gancho tem 1 corte ou 1 movimento de câmera claro.
- Checagem: `ritmo.gancho_ate_s` (padrão 3) + folha densa dos 3 primeiros segundos (0,25 s).

## 2. Pausa para pedir para seguir
- Um momento curto e visível (card) pedindo para **seguir** o perfil: `ritmo.seguir.momento` (`meio` ou `final`) e `ritmo.seguir.duracao_s` (padrão 1,5–2,5 s). A fala acompanha o card.
- Fica na área segura, com a arte do perfil, variando o desenho a cada edição (a animação pode repetir, o desenho não).
- Legenda: sem pedir comentário/DM a menos que o perfil tenha oferta ligada.

## 3. Imagem
- **Fundo vivo** (cor da paleta do perfil, luz e movimento); nunca escuro e sem graça, salvo estilo de referência que seja assim.
- **Profundidade 3D** (camadas, paralaxe) sem trocar o estilo.
- **Tela limpa**: poucos elementos, HUD pequena e fixa no lugar, sem imagenzinhas recortadas; história primeiro.
- **Área segura do feed**: texto, HUD e inserts entre y 285 e 1635 (1080×1920), no máximo 2 inserts juntos.
- **Nenhuma piscada**: nada recriado por frame.
- **Variar a execução**: recurso repetido mantém a animação mas muda o desenho (sem Ctrl+C Ctrl+V).
- **Capa** diz o que é o vídeo, cabe no corte 3:4 e segue o ciclo de cores da grade (`grade.ciclo`).

## 4. Áudio
- Voz na frente, trilha com ducking suave, SFX ajustados; transições em "bafinho" (bem baixas).
- Mix e gate de áudio em `_sistema/audio-mix.md` (alvo e limites no `perfil.yaml → audio`).
- Som (SFX) só depois da animação pronta, com tempos medidos no render.

## 5. Texto publicado
- Legenda: título + 3 linhas numeradas (lição rápida), 120–450 caracteres.
- Hashtags: 6 por legenda, 3 fixas do perfil + 3 variáveis que não repetem nos 3 posts vizinhos, depois de uma linha em branco.
- "Traduzir reel" (Instagram → Mais opções → Acessibilidade e tradução): ligar quando disponível, ao postar.

## 6. QA
- Nota de corte **6,8** em todos os itens (média, assunto, fundo, capa, HUD, ação, variação); máx. 5 rodadas de ajuste; levantar tudo e corrigir de uma vez.
- Depois do QA, olhar o `video.mp4` em folhas de quadros densas (0,25 s em peça nova, 0,5 s nas demais): texto que reflui, pisca ou pula só aparece assim.
- Peça sorteada (cena, apoio, insert) só vale se tiver ligação clara com o fato do roteiro.
- Roteiro raso reprova: cada frase traz decisão, porquê, número ou virada.
- Antes de afirmar "está pronto/feito", conferir por mais de um ângulo (feed real, cores, quadros).

## 7. Fluxo e segurança
- Pauta → roteiro → voz → cena → render → QA → fila → post (contratos em `_sistema/contratos/`).
- Perfil novo só liga `producao_auto` depois de 1 edição de teste aprovada com a pessoa olhando.
- Segredos só no `.env`. Cada pessoa usa as próprias contas (Meta/Instagram, ElevenLabs, Claude).
