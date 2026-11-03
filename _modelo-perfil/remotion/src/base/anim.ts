/**
 * Helpers de animação + REGRA ANTI-PISCADA.
 * - Tudo é função de useCurrentFrame() + constantes. Nada de Math.random, Date.now ou estado que muda entre quadros.
 * - Aleatório só com random(semente) do Remotion (mesma semente = mesmo valor em todo quadro e em todo render).
 * - Geometria/material/listas criados uma vez (constante de módulo ou useMemo com dependências fixas); chaves (key) estáveis.
 * - Elemento entra e sai por opacidade/escala interpolada, nunca por montar/desmontar a cada quadro.
 */
import {Easing, interpolate, random} from 'remotion';
import {DURACOES, EASING, seg} from '../estilo';

export const ease = (b: readonly [number, number, number, number]) => Easing.bezier(b[0], b[1], b[2], b[3]);

/** 0→1 na entrada, 1 no meio, 1→0 na saída (quadros absolutos). */
export const presenca = (frame: number, ini: number, fim: number, entra = seg(DURACOES.entrada), sai = seg(DURACOES.saida)) => {
  if (fim <= ini) return 0;
  const a = interpolate(frame, [ini, ini + entra], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease(EASING.entrada)});
  const b = interpolate(frame, [fim - sai, fim], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease(EASING.saida)});
  return Math.min(a, b);
};

/** Aleatório determinístico (anti-piscada): use no lugar de Math.random. */
export const sorteio = (semente: string | number) => random(String(semente));
