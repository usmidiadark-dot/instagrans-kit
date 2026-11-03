# shotlist.md — {{HANDLE}}

> Template do roteiro. Copie para `shots/<id>.md` a cada post.
> Cada beat precisa de: estado de entrada, estado de saída e motivo de existir. Beat sem motivo é cortado.
> Preencha com o estilo extraído das refs (skill analisar-refs).

## TEMPLATE

```
POST
id:            {{PREFIXO}}-NNN
tipo:          A | B
duração:       s
o viewer deve lembrar: [uma frase]
personagem:    [quem, aparência, onde está]
cena:          [lugar]
ação:          [o que a personagem FAZ — sem ação, sem post]
frase grande:  "[1–5 palavras]"
narração:      "[frases curtas]"
trilha:        [arquivo + BPM]

ESTADOS (ordem)
HOOK -> CONTEXTO -> DESENVOLVIMENTO -> PAYOFF -> FECHO

BEATS
tempo      estado      entrada -> saída        motivo        som
00.0–02.0  HOOK        ...                     gancho        ...

TEXTO NA TELA
t_in   t_out  texto

LEGENDA DINÂMICA
gerada dos timestamps da narração — nunca digitada à mão

GRID DE BEATS (som)
t        cue
```
