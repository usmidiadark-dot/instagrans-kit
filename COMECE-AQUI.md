# Comece aqui — instalar o kit com ajuda do Claude

Você não precisa saber instalar nada, nem ter conta no GitHub nem usar Git: o kit baixa como um arquivo .zip por um link público. Abra o Claude Code (ou o app do Claude, aba Code) em **qualquer pasta**, cole o texto abaixo e responda às perguntas. O Claude instala, confere e arruma sozinho os erros.

---

## Cole isto no Claude

```
Instale o INSTAGRANS-KIT neste computador (Windows) e deixe tudo funcionando, sem depender de mim para resolver erros. Responda em português simples.

Download (sem login, sem Git): https://github.com/usmidiadark-dot/instagrans-kit/archive/refs/heads/main.zip

Faça nesta ordem:
1. Pergunte (com opções) em qual pasta instalar. Recomende C:\INSTAGRANS-KIT. O caminho precisa ter no máximo 60 caracteres e, de preferência, sem espaço nem acento.
2. Baixe o .zip do link acima (PowerShell: Invoke-WebRequest -Uri <link> -OutFile $env:TEMP\kit.zip -UseBasicParsing), extraia (Expand-Archive) e coloque o CONTEÚDO da subpasta extraída (instagrans-kit-main) direto na pasta escolhida, de modo que instalar.ps1 fique na raiz dela.
3. Confirme que a pasta tem instalar.ps1, CLAUDE.md e _sistema. Se faltar algo, baixe de novo.
4. Dentro da pasta, rode: powershell -ExecutionPolicy Bypass -File .\instalar.ps1
   Se algum passo falhar, leia o erro, conserte sozinho (por exemplo atualizar o PATH, rodar o passo de novo, instalar o que faltar) e continue. Até 3 tentativas por problema; só me chame se for algo que só eu posso fazer (login, conta, senha).
5. Rode: python _sistema/verificar.py — repita a correção até não aparecer nenhum [FALTA]. Só [AVISO] pode ficar, e me explique cada um em uma frase.
6. Me explique, em frases curtas, que o Claude precisa ser aberto DENTRO da pasta do kit para valer as regras, as skills e a trava do projeto (CLAUDE.md, .claude/). Se o app permitir, abra a pasta como projeto agora; se não, me mostre o passo exato.
7. Guie o preenchimento do arquivo .env UM item por vez (Instagram/Meta e ElevenLabs só se eu for usar). Nunca peça para eu colar senha, token ou chave no chat: eu colo direto no arquivo.
8. NÃO ligue produção automática, NÃO poste nada e NÃO crie tarefas ligadas. Tudo começa desligado.
9. No fim diga: o que ficou pronto, o que NÃO foi testado, e qual é o próximo passo (criar meu primeiro perfil: "quero criar um perfil novo").
```

---

## O que o Claude faz por você
- Escolhe/cria a pasta fixa, baixa o .zip e instala Node, Python, ffmpeg e dependências.
- Baixa o navegador que gera o vídeo (Remotion) e confere tudo com `python _sistema/verificar.py`.
- Trava o projeto na pasta: ao abrir o Claude dentro dela, valem as regras (`CLAUDE.md`), as skills (`criar-perfil`, `analisar-refs`, `produzir`, `qa`) e os hooks (aviso de conversa longa, trava por edição).
- Deixa tudo desligado: nada é postado até você ligar um perfil.

## Se algo der errado
Rode `python _sistema/verificar.py` e cole o resultado para o Claude. Cada linha `[FALTA]` já diz o que fazer.

## Atualizar depois
Peça ao Claude: "atualize o kit". Ele roda `powershell -ExecutionPolicy Bypass -File _sistema\atualizar.ps1`, que baixa a versão nova, troca só o motor, as skills e os modelos, e roda o verificador. Seus perfis, vídeos e `.env` ficam intactos.
