# Legenda do post · regra de todos os perfis

> Vale para todo perfil e toda edição, acima do modelo de legenda dos guias. Conteúdo no idioma do perfil (`perfil.yaml → idioma_conteudo`), no tom de cada perfil. Quem escreve: a etapa 02 (roteiro) grava em `script.json → caption`; a etapa 07 (fila) arruma a chamada (se houver), aplica as hashtags e confere.

## 1. Lição rápida (padrão de todos os perfis)
"Um resumo em forma de lição rápida de ler e dinâmica." Ligado por `perfil.yaml → legenda.licao_rapida` (padrão `true`).

Molde (`legenda.caracteres`, padrão 120–450 caracteres, fora as hashtags):
```
<título: a lição em 1 linha, no máximo ~80 caracteres>

1. <a situação, 1 frase curta>
2. <o fato ou número com fonte curta, 1 frase>
3. <o que fazer / o que levar, 1 frase>

<linha em branco>
<6 hashtags: 3 fixas + 3 variáveis>
```
Regras: cada linha numerada tem até ~90 caracteres e lê em 2 segundos, sem parágrafo; o fato continua com fonte (registrada em `brief.json → sources`); ≤ 3 emojis; tom e caixa (minúsculas ou não) do guia do perfil; sem repetir o vídeo palavra por palavra. COM CTA, a linha de chamada (1 só) entra depois da linha 3, antes das hashtags, e não conta como linha. SEM CTA, nenhuma chamada. Gate: `fila.py → confere_licao_rapida` (dentro de `confere_legenda`).

## 2. Hashtags
**6 por legenda = 3 FIXAS do perfil + 3 VARIÁVEIS**, numa linha só, depois de uma linha em branco. As variáveis saem do banco do perfil e **não podem repetir nos 3 posts anteriores** (nem nos 3 seguintes já agendados). Banco: `<perfil>/perfil.yaml → hashtags: {fixas, variaveis}` (12 ou mais variáveis); sem bloco `hashtags`, no máximo 3 hashtags. O `fila.py` aplica e confere (`_sistema/orquestrador/hashtags.py`); o bloco de hashtags não conta nos caracteres da lição.

**Hashtags por assunto:** `hashtags.py` lê o campo `tema` de `out/<id>/script.json`; se `perfil.yaml → hashtags.por_tema` tiver esse tema, sorteia as variáveis dali (fora dos 3 posts vizinhos) e completa com o banco inteiro; o `confere` exige ao menos 2 das 3 do assunto. Sem `tema`, vale o banco inteiro. Cuidado: `hashtags.py aplicar --perfil <pasta>` REESCREVE as legendas da fila; não rode em perfil com legenda ajustada à mão.

## 3. O que a legenda precisa fazer
Entregar valor **sem parecer venda**. Quem lê deve sair com a sensação: *"se isso aqui é de graça e já é bom assim, imagina o resto"*. Isso se cria com generosidade e acabamento, nunca com pedido. O Instagram mostra só o começo (≈ 125 caracteres) antes do "mais": **ali fica o título/gancho**, não o pedido.

## 4. Vídeo SEM CTA (padrão de perfil sem oferta: `sem_cta_sempre: true`)
- O título é uma frase discreta do tema (uma observação ou pergunta), sem palavra de comentário, sem "DM", "send you", link, bio, "free" nem urgência.
- Nenhuma linha de chamada na legenda inteira (o `fila.py` tira a que vier). O final do vídeo pede para **seguir** (`_sistema/regras-gerais.md §1`), não para comentar.

## 5. Vídeo COM CTA (só em perfil com oferta ligada)
A chamada é **uma linha só, no corpo**: depois das 3 linhas numeradas e antes das hashtags, nunca no título.
- A frase sai do **banco do perfil** (`<perfil>/perfil.yaml → legenda_cta.frases`; sem o campo, o padrão do `legenda_cta.py`). Todo molde tem `comment "{P}"` (PALAVRA em MAIÚSCULAS, **entre aspas**), `I'll send you {X}` (a promessa exata do vídeo, a mesma da fala e do card) e um `{E}` (emoji). Sem preço, "free", "course" ou "bio".
- A palavra e a promessa vêm de `script.json → cta`; edição sem `script.cta` usa a palavra fixa do perfil (`oferta.cta`).
- **Quem põe a chamada:** o `fila.py` (`com_palavra` → `_sistema/orquestrador/legenda_cta.py`). Quem escreve a legenda **não precisa** escrever a linha: se escrever, ela é tirada e trocada pela variante sorteada.
- **Sem repetir** (histórico = as legendas reais da fila + publicado, em ordem de horário; registro em `<perfil>/reviews/legendas.jsonl`): o emoji do pool não repete nenhum das 3 últimas; a frase não repete nenhuma das 6 últimas; o par frase + emoji não repete nenhuma das 10 últimas. Sorteio com semente = id da edição, então rodar de novo dá o mesmo resultado.

### Emoji do tema do vídeo
- O emoji da linha de chamada é o **emoji do assunto do vídeo** (um animal, um objeto, um fenômeno: o que bate o olho e diz o assunto).
- **Quem escolhe:** a sessão que produz a edição, junto com o roteiro. Grava em `script.json → cta.emoji_tema` (edição sem objeto `cta`: `script.json → emoji_tema` no topo; nunca crie `cta` só para isso). `brief.json → emoji_tema` também é lido.
- **Tema abstrato sem emoji que o represente:** `emoji_tema: null` → o emoji é sorteado do pool do perfil (`legenda_cta.emojis`, ≥ 5).

**De 1 a 3 emojis, bonito sem brega.** `cta.emoji_tema` aceita de 1 a 3 emojis, em texto (`"🐙"`, `"🐙🦀"`) ou em lista. Eles são **os protagonistas do assunto, na ordem em que entram no vídeo**; na legenda o grupo sai junto, sem espaço, na vaga `{E}`. O emoji é uma legenda do que a pessoa acabou de ver, não um enfeite: se tirar o emoji, a frase não perde informação; se trocar por ✨, ela perde.

Regras (gate: `legenda_cta.py → tema_erros`, `tema_no_roteiro`, `confere`; `fila.py → confere_tema_na_entrada`, `confere_legenda`):
1. **No máximo 3 emojis** na linha de chamada (ZWJ, FE0F e tom de pele contam como 1).
2. **Nenhum repetido.**
3. **Só coisa concreta do vídeo:** animal, objeto, lugar (bandeira vale), fenômeno, comida, parte do corpo. **Reprova:** enfeite genérico (✨ 🔥 💯 🚨 🎉 ⭐ 💥 ❗ ❓ ✅ 💬 📩 📌 👀 e afins), rosto/emoção, coração, mão e seta, forma geométrica que é marca do perfil e símbolo de palavra (🆓 🆕). O pool do perfil pode ter alguns deles: valem **só no pool**, nunca como tema.
4. **Sem misturar tema com pool na mesma linha.**
5. **2–3 só quando o vídeo tem mesmo 2–3 protagonistas;** senão, 1. O código confere que cada um é dito ou escrito no `script.json` (nome do emoji em inglês contra narração, falas, legenda e cenas).
6. **Total da legenda ≤ 3 emojis:** se a linha de chamada tem 3, o resto da legenda tem 0.

**Posição sem padrão:** o grupo pode ficar no início, no meio (entre a frase e a promessa) ou no fim do molde; espalhe as posições pelo banco.

Ruins (reprovam, ou são brega mesmo passando): enfeite junto do tema · emoji repetido · 4 emojis · rosto ou mão no grupo · tema + emoji do pool na mesma linha · 3 bichos quando o vídeo é de um só · emoji que conta piada em vez de dizer o assunto · trocar o protagonista por um parente "mais bonito".

### Banco de frases: tamanho e como ampliar
Comece com pelo menos 8 frases (de preferência 15) e ≥ 5 emojis no pool. Para ampliar:
1. **Acrescente no fim** de `legenda_cta.frases`. Nenhuma frase existente muda ou sai, porque o histórico guarda o molde pelo texto exato. Use só aspas retas e nenhum emoji literal no molde.
2. **Forma:** `comment "{P}"` e `I'll send you {X}` exatos, um `{E}`, de 6 a 14 palavras antes do `comment`, na voz do perfil.
3. **Nada de empurrar:** sem "don't miss", "hurry", "free", "link in bio", "grab yours", "DM", "course", "price", nem as palavras de `fila.py → PROIBIDAS` (e as de `legenda.proibidas` do perfil). Sem clichê de vendedor e sem repetir o começo de outra frase do banco com uma palavrinha trocada.
4. **Confira antes de gravar:** toda linha de chamada real (fila + publicado) continua detectada com o banco novo (`legenda_cta.py → detecta`); cada molde preenchido só casa consigo; o ciclo `monta` → `confere` passa com tema de 1, 2 e 3 emojis e com `null`.

## 6. Emojis (todas as legendas)
No máximo 3 na legenda inteira (sequência ZWJ/tom de pele conta como 1). Nunca em sequência, com uma exceção: o grupo do tema na linha de chamada.

## 7. Tom
- Como alguém que sabe muito e está contando de graça porque gosta do assunto. Confiante, curto, específico.
- Caixa e estilo do guia do perfil (a PALAVRA de comentário fica sempre em maiúsculas).

## 8. Proibido
- Verbo de venda: buy, shop, sale, discount, offer, deal, limited, hurry, last chance, don't miss, DM me. O único pedido permitido é a linha de chamada no corpo (comentar a palavra), e só COM CTA.
- Pedir like, save ou share na legenda ("save this").
- "Link in bio" seco como frase sozinha; urgência; escassez; emoji em sequência (fora o grupo do tema na chamada) ou mais de 3 no total.
- Fato inventado ou sem fonte.
- Repetir o vídeo palavra por palavra.

## 9. Conferência (regra vira gate)
- **`fila.py` (entrada da fila, `confere_legenda`)** reprova: lição rápida fora do molde ou da faixa de caracteres; hashtags fora da regra 3+3 (ou mais de 3 sem banco); mais de 3 emojis; palavra proibida. COM CTA também: chamada no título; sem a palavra entre aspas; mais de 1 linha de chamada; chamada depois das hashtags; frase fora do banco; edição sem a decisão do emoji do tema (`cta.emoji_tema` ausente; `null` vale); emoji diferente do tema ou fora da regra; tema de 2–3 com algum que não está no `script.json`; promessa diferente da do vídeo; frase ou par repetido das janelas. SEM CTA: qualquer `comment "PALAVRA"`, DM, "send you", "I'll send", link in bio ou urgência.
- **`post.py` (hora de postar)** usa a mesma regra: legenda já na regra passa igual (nunca põe nada no topo); emoji diferente do tema é trocado no lugar; erro de estrutura da chamada bloqueia o post. A janela de repetição é conferida na entrada da fila, não no post.

## 10. Exemplos (lição rápida)
SEM CTA:
```
octopuses taste with their arms.

1. each arm has its own cluster of neurons, so it can act on its own.
2. the suckers carry chemical sensors: touching is tasting (Nature, 2020).
3. next time you see one exploring a rock, it's reading the menu.

#perfilfixa1 #perfilfixa2 #perfilfixa3 #ocean #animalfacts #biology
```
COM CTA:
```
a longer exhale slows your heart.

1. the heart speeds up a little on every in-breath and slows on every out-breath.
2. it's called respiratory sinus arrhythmia, and slow breathing makes the swing bigger.
3. try four in, six out, three times.
🌬️ no rush. comment "EXHALE" and I'll send you the one-minute practice

#perfilfixa1 #perfilfixa2 #perfilfixa3 #breathwork #calm #wellness
```
