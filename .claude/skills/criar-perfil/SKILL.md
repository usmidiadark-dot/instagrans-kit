---
name: criar-perfil
description: Cria um perfil novo (qualquer assunto) neste kit: pasta a partir do modelo, refs de vídeo + links, estilo extraído, folha de aprovação e edição de teste. Use quando a pessoa disser "quero criar um perfil", "novo perfil", "novo canal".
---

# Criar perfil novo

Siga na ordem; não pule elo. Fale em português simples. Decisões da pessoa vão por `AskUserQuestion` (recomendação primeiro).

1. **Perguntar o básico** (uma pergunta de cada vez): assunto/nicho, idioma do conteúdo, @ do Instagram (ou "ainda não tem"), com narração ou só efeitos, quantos posts por dia.
2. **Criar a pasta**: `python _sistema/orquestrador/criar_perfil.py <pasta> --handle @x --idioma en --nicho "..."` (copia `_modelo-perfil/`, cria `refs/`, registra em `perfis.yaml → ordem`, com `producao_auto: false`).
3. **Referências**: peça à pessoa para pôr 3–10 vídeos em `<pasta>/refs/` e/ou links em `<pasta>/refs/links.txt`. Rode `python _sistema/orquestrador/refs.py baixar <pasta>` (se houver links) e `... analisar <pasta>`.
4. **Estilo**: siga a skill `analisar-refs`.
5. **Voz e sons**: se o perfil tem narração, 3 vozes candidatas pelo conector do ElevenLabs; a pessoa escolhe ouvindo a mesma frase. Sons em código quando o estilo pedir.
6. **Folha de aprovação**: renderize 3 capas + 1 cena de 3 s do estilo + grade 3×3 simulada; mostre à pessoa (abra no Explorer e envie). Só continue com o OK dela.
7. **Gates do perfil**: ajuste `ritmo`, `qualidade`, `audio`, `grade` no `perfil.yaml` (ver `_sistema/orquestrador/CHAVES-PERFIL.md`); gate que só serve a este perfil vai em `<pasta>/gates.py`.
8. **Edição de teste**: faça a 1ª edição com a pessoa olhando (`orquestrador.py`), passe no QA (corte 6,8, máx. 5 rodadas), confira em folhas de quadros densas.
9. **Instagram**: guia em `_sistema/briefs/configurar-meta.md` (conta profissional, página, token no `.env`). Teste de publicação só a pedido da pessoa.
10. **Ligar**: `producao_auto: true` no `perfil.yaml` só depois do passo 8 aprovado. Escreva `<pasta>/RETOMAR.md` (estado, pendências, mapa).

Regras que valem sempre: `REGRAS-UNIVERSAIS.md`. Toda arte em código. Nunca posta sem a pessoa ligar.
