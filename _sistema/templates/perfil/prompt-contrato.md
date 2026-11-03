# prompt-contrato.md — {{HANDLE}}

> Cole o bloco abaixo no Claude Code com a pasta do perfil aberta. Só **POST DE HOJE** muda entre posts.
> **Atenção:** os gates com "espere meu OK" valem só para a 1ª edição de implantação. Depois a aprovação é automática pelo QA (regras-gerais §2) e a produção roda pelo `_sistema/orquestrador/produzir.md`.

```
Você está produzindo um post para {{HANDLE}}. Responda e documente em português.

ANTES DE QUALQUER GERAÇÃO
1. Leia ../CLAUDE.md, ../_sistema/regras-gerais.md, brief.md, style-guide.md, review-checklist.md.
2. Escreva shots/<id>.md a partir do shotlist.md.
3. Liste em reviews/<id>-assets.md todo asset que vai usar. Faltou asset obrigatório: PARE e pergunte.
4. Cote o custo de toda geração paga e espere meu OK.

POST DE HOJE
id:        {{PREFIXO}}-NNN
tipo:
pauta:
data_alvo:

GATES (pare e mostre antes de seguir)
Gate 1 — roteiro (shots/<id>.md)
Gate 2 — teste pequeno (1 frame / 1 frase), com custo
Gate 3 — render completo + contact sheet revisado por subagente
Gate 4 — nota do review-checklist + legenda → mover para posts/03-para-aprovar/

Nunca publique: publicação só a partir de posts/04-aprovado/, com minha confirmação.
```
