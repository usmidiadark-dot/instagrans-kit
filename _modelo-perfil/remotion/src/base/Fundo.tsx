/**
 * Fundo vivo: gradiente na paleta que gira devagar + luz que passeia + vinheta leve.
 * Nunca escuro e parado. Todo movimento sai do frame (sem aleatório por quadro).
 */
import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {PALETA, TELA, TEXTURA} from '../estilo';

export const Fundo: React.FC<{cores?: [string, string, string]}> = ({cores}) => {
  const f = useCurrentFrame();
  const t = f / TELA.fps;
  const [a, b, c] = cores ?? [PALETA.fundoA, PALETA.fundoB, PALETA.fundoC];
  const angulo = 160 + Math.sin(t * 0.35) * 25;
  const lx = 50 + Math.sin(t * 0.5) * 28;
  const ly = 35 + Math.cos(t * 0.4) * 18;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{background: `linear-gradient(${angulo}deg, ${a} 0%, ${b} 55%, ${c} 100%)`}} />
      <AbsoluteFill style={{background: `radial-gradient(circle at ${lx}% ${ly}%, ${PALETA.luz} 0%, transparent 45%)`, opacity: TEXTURA.brilhoLuz * 0.5, mixBlendMode: 'soft-light'}} />
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(0,0,0,${TEXTURA.vinheta}) 100%)`}} />
    </AbsoluteFill>
  );
};
