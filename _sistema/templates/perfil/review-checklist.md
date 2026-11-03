# review-checklist.md — {{HANDLE}}

> A conferência visual é feita por um subagente Sonnet (nunca na conversa principal), com evidência: número do frame.

## Como gerar o contact sheet

1 frame por beat + faixa curta na transição mais rápida.

## Checklist

### Legibilidade e segurança
- [ ] Nada importante fora da safe area
- [ ] Texto legível em tela de celular

### Identidade (brief)
- [ ] Todos os elementos de identidade presentes

### Tipografia
- [ ]

### Movimento
- [ ] A personagem tem ação (não só o fundo muda)

### Som
- [ ] Narração = roteiro (diff do Whisper = 0)
- [ ] Cortes e SFX no beat

### Narrativa
- [ ] Gancho nos primeiros segundos (`ritmo.gancho_ate_s`)
- [ ] Cada beat passa no teste do corte

### Publicação
- [ ] Legenda e hashtags conforme brief
- [ ] Capa definida
- [ ] Custo registrado no arquivo do post

## Tarefa de crítica (colar para o subagente junto com o contact sheet)

## Pontuação

| Nota | Critério |
|---|---|
| média ≥ `qa.corte` (padrão 6,8) e cada item com gate (assunto, fundo, capa, HUD, ação, variação) ≥ corte; nenhum "nunca" | aprovado sozinho pelo `qa.py` → `posts/04-aprovado/` (aprovação automática, regras-gerais §2) |
| abaixo | volta para produção com o motivo (máx. 5 rodadas; depois `reviews/falhas/`) |

> Itens que todo perfil precisa ter neste checklist (regras-gerais §1): gancho nos primeiros segundos, HUD interativa (se o perfil liga), card de seguir e card final, área segura 4:5 do feed sem amontoar, nenhuma piscada, capa pôster no corte 3:4 com a cor do `grade.ciclo`, variação contra a edição anterior, som por plano + ambiente.
