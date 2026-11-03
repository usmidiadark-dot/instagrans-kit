# 04 · Cena

**Entradas:** `script.json`, `words.json`, `style-guide.md`, `<perfil>/assets/`

**Saída:** `scene/` com a composição Remotion da edição

**Gate (passa se):** Compila; cada plano do roteiro existe; textos e bocas amarrados aos timestamps; câmera com camadas e paralaxe; só cores e fontes do guia.

**Proibido:** Gerador de imagem ou vídeo; cores ou fontes fora do guia; câmera sem profundidade; personagem flutuando.

**Se reprovar:** corrigir e tentar de novo até o limite de `_sistema/automacao.md §3` (QA: máx. 5 rodadas no total); depois gravar `fail.json` com etapa, motivo e últimas saídas, e parar.

**Como a cena é lida:** a cena é o `script.json` (planos, câmera por nome de plano, objetos e inserts) lido pela composição do perfil (`<perfil>/remotion/src/`, `perfil.yaml → composicao.edicao`). Sujeito ou cenário novo = um componente novo na pasta `cenas/` do Remotion do perfil. A etapa também grava o `sfx.json` (eventos de som amarrados ao `words.json`). Conferir com `npx remotion still … --props=<pasta>/props.json` antes do render.
