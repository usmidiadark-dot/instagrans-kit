# brief.md — {{HANDLE}}

> Este arquivo guarda os FATOS do perfil. O que está aqui o agente não pode inventar nem trocar.
> As ESCOLHAS de cada post (história, personagem do dia, frase) ficam em `shots/<id>.md`.
> Preencha com o estilo extraído das refs (skill analisar-refs).

## Perfil

| Campo | Valor |
|---|---|
| Handle | {{HANDLE}} |
| Tema | |
| Público | |
| Idioma do conteúdo | |
| Idioma de produção | PT-BR |
| Essência (uma frase) | |
| O que o viewer deve lembrar | |
| Foto de perfil / bio | |

## Formato

| Campo | Valor |
|---|---|
| Tipo de post | reel / carrossel / imagem |
| Aspect | 9:16, 1080×1920 |
| FPS | 30 |
| Duração | |
| Safe area | área segura do feed 4:5: tudo que importa em y ≈ 285–1635, fora da coluna de botões (x > 950 abaixo de y 1000); capa inteira no corte 3:4 (y 240–1680) — regras-gerais §1 |
| Loudness | −14 LUFS integrado, pico −1 dBTP |
| Encode | H.264 High, CRF 18, AAC 192k, +faststart |

## Tipos de post (formato misto)

| Tipo | O que é | Narração | Proporção da grade |
|---|---|---|---|
| A | | | |
| B | | | |

## Regras fixas (o que não muda entre posts)

-

## Legenda e hashtags

- Tom da legenda:
- CTA:
- Hashtags (fixas + variáveis, máx.):

## Assets obrigatórios (o agente para se faltar)

```
assets/
  brand/       logo, palette.json
  fonts/
  audio/       music/, sfx/, narration/
  reference/   referências de estilo (uso interno)
```

## Pipeline (ferramentas aprovadas)

| Etapa | Ferramenta |
|---|---|
| Direção + código + revisão | Claude Code, em PT-BR |
| Imagem / vídeo | |
| Narração | |
| Mix / encode | ffmpeg |
| Postagem | ver `../perfis.yaml` |

## O que torna um post inaceitável

-

## Licenças a checar antes de escalar

-
