> **Cópia de referência.** A regra vigente do QA está em `_sistema/contratos/06_qa.md` e no `qa.py` (itens, gates, 3 avaliadores com mediana, máx. 5 rodadas). Em divergência vale o contrato e o código.

# 06 · QA visual

**Entradas:** quadros do vídeo (1 a cada 0,5 s + momentos-chave), `cover.jpg`, `script.json`, `style-guide.md`

**Saída:** `qa.json` (schema `schemas/qa.schema.json`)

**Checklist (nota 0–10 cada):**
1. **Assunto reconhecível de cara** — sem som e sem legenda, dá pra dizer o que é em 1 segundo? (peso dobrado)
2. **Fundo bonito e vivo** — colorido na paleta, com luz e algo em movimento; nunca escuro chapado. (peso dobrado)
3. Estilo do guia (traço, cores, tipografia).
4. Profundidade de câmera e planos variados (mínimo do `format.json`).
5. Capa: quadro do **momento da ação do título**, nunca um quadro neutro; o texto nunca contradiz a imagem; nada solto voando por cima; diz o que é o vídeo em destaque (assunto grande, tipo chamativo, cores vibrantes, texto inserido na arte) e funciona na grade: título, assunto e selo inteiros no corte 3:4 do centro (y 240–1680), no modelo e na cor do ciclo do perfil (`regras-gerais.md §1`). **Sem defeito de montagem** (borda ou faixa vazia dentro de moldura, imagem que não preenche, recorte errado, texto cortado).
6. Texto legível, dentro da área segura do feed (corte 4:5, y 285–1635, fora da coluna de botões), sem cobrir rosto ou assunto e sem amontoar.
7. Personagem/objeto apoiado na cena (nada flutuando).
8. Ritmo: algo muda a cada 1,5–3 s.
9. **HUD interativa** (perfis com `qualidade.hud`) presente, no estilo do vídeo, com dados que mudam com a narração; inserts legíveis; legenda dinâmica e limpa; nada de piscada rápida.
10. **Ação → insert e fundo vivo**: cada ação na tela tem um insert ou card no mesmo trecho; inserts novos desta edição; fundo com elementos se mexendo. Nota baixa se a cena parece parada ou se uma ação passa sem reforço.

**Gate:** média ponderada ≥ `perfil.yaml → qa.corte` (padrão 6,8), cada item com gate (assunto, fundo, capa, HUD, ação, variação) ≥ corte, nenhum item "nunca" do `style-guide.md` violado.

**Se reprovar:** volta para a etapa 04 com o motivo. Limite de **5 rodadas de QA no total**; na 5ª reprovação grava `fail.json` e a edição sai da fila.

**Precisão (para não gastar rodada):**
- O QA recebe o roteiro de cada frame (cena, narração, camadas e ações previstas). O que está no roteiro é intencional e não é defeito; o QA avalia se ficou claro, não se existe.
- Cada correção ataca de uma vez todos os pontos reais do relatório; nada de corrigir um ponto por rodada.
- Script: `python _sistema/orquestrador/qa.py preparar <pasta>` → 3 subagentes independentes (`prompt.md`, `prompt_2.md`, `prompt_3.md`) → `python _sistema/orquestrador/qa.py julgar <pasta>`: vale a **mediana por item**. "Nunca" só conta se ≥ metade apontar.

## Conferência EM MOVIMENTO (todos os perfis, sem exceção)
Quadros parados não mostram texto que reflui, pisca ou pula com a câmera andando. Depois do QA e ANTES de entrar em `04-aprovado`, 2 etapas:
(a) **Detector** `python _sistema/orquestrador/movimento.py <pasta> --saida movimento.json`: o `fila.py` já roda e grava `out/<id>/movimento.json` (piscadas A→B→A) e as folhas densas em `out/<id>/movimento/`. **Limite conhecido:** é só AVISO: dispara também em vídeo bom e não pega o texto refluindo com câmera andando; não confie nele sozinho.
(b) **Folhas de quadros densos olhadas pelo revisor** (obrigatório): 1 quadro a cada 0,25 s nas peças novas e 0,5 s no resto (`movimento.py <pasta> --densas --passo 0.25`). Procurar: texto que muda de quebra de linha, pisca ou escala torto; peça sobreposta a HUD, legenda ou sujeito; corte brusco na entrada/saída; legenda sumindo sem motivo; peça fora do tema. Qualquer achado reprova e volta para refazer.
**Em aberto:** um check estrutural de texto (nº de linhas/caixa por quadro) exige a composição gravar um log de layout; pixel puro não separa esse defeito de vídeos bons.
