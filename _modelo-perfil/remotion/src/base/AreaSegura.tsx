/**
 * Área segura do feed (y 285–1635). O reel aparece no feed cortado em 4:5: texto, HUD e cards fora desta faixa somem.
 * - prenderY(): helper que trava um y (e a altura do elemento) dentro da faixa. Todo componente de texto usa.
 * - <GuiaAreaSegura/>: faixas vermelhas só para conferir no Studio (prop mostrar); nunca no render final.
 */
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {AREA_SEGURA, TELA} from '../estilo';

/** Trava o centro y de um elemento de altura h para que ele inteiro caiba na área segura. */
export const prenderY = (y: number, h = 0) => {
  const min = AREA_SEGURA.yTopo + h / 2;
  const max = AREA_SEGURA.yBase - h / 2;
  if (min > max) return (AREA_SEGURA.yTopo + AREA_SEGURA.yBase) / 2;
  return Math.min(max, Math.max(min, y));
};

/** Trava o topo de um elemento de altura h. */
export const prenderTopo = (topo: number, h = 0) => prenderY(topo + h / 2, h) - h / 2;

/** Caixa posicionada pelo centro y já travada na área segura, ocupando a largura útil. */
export const NaAreaSegura: React.FC<{y: number; altura: number; children: React.ReactNode; style?: React.CSSProperties}> = ({y, altura, children, style}) => {
  const cy = prenderY(y, altura);
  return (
    <div style={{position: 'absolute', left: AREA_SEGURA.margemX, right: AREA_SEGURA.margemX, top: cy - altura / 2, height: altura,
      display: 'flex', alignItems: 'center', justifyContent: 'center', ...style}}>
      {children}
    </div>
  );
};

export const GuiaAreaSegura: React.FC<{mostrar?: boolean}> = ({mostrar}) => {
  if (!mostrar) return null;
  const faixa: React.CSSProperties = {position: 'absolute', left: 0, right: 0, background: 'rgba(255,0,0,0.25)'};
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{...faixa, top: 0, height: AREA_SEGURA.yTopo}} />
      <div style={{...faixa, top: AREA_SEGURA.yBase, height: TELA.altura - AREA_SEGURA.yBase}} />
    </AbsoluteFill>
  );
};
