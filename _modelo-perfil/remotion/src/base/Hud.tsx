/**
 * HUD interativa: pequena, FIXA no canto (não anda com a câmera), dentro da área segura.
 * Slot configurável: rótulo + valor que muda nos tempos do script (script.hud.passos), ou qualquer conteúdo via children.
 * O valor troca com um "pulso" curto de escala; a caixa tem largura fixa para não refluir.
 */
import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {AREA_SEGURA, FONTES, PALETA, POSICOES, RAIO, TAMANHOS, TELA} from '../estilo';
import {prenderTopo} from './AreaSegura';
import {presenca} from './anim';

export type HudProps = {
  rotulo: string;
  passos: {t: number; v: string}[];
  inicio?: number; // s
  fim?: number; // s
  largura?: number;
  canto?: 'topoDireito' | 'topoEsquerdo';
  children?: React.ReactNode;
};

export const Hud: React.FC<HudProps> = ({rotulo, passos, inicio = 0.4, fim = 9999, largura = 300, canto = POSICOES.hud.canto, children}) => {
  const f = useCurrentFrame();
  const t = f / TELA.fps;
  const op = presenca(f, Math.round(inicio * TELA.fps), Math.round(fim * TELA.fps));
  if (op <= 0) return null;
  const idx = passos.reduce((acc, p, i) => (t >= p.t ? i : acc), 0);
  const tTroca = passos[idx]?.t ?? 0;
  const pulso = interpolate(t - tTroca, [0, 0.12, 0.3], [1, 1.12, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const altura = TAMANHOS.hud * 3.2;
  const lado = canto === 'topoDireito' ? {right: Math.max(POSICOES.hud.x, AREA_SEGURA.margemX)} : {left: Math.max(POSICOES.hud.x, AREA_SEGURA.margemX)};
  return (
    <div style={{position: 'absolute', top: prenderTopo(POSICOES.hud.y, altura), ...lado, width: largura, height: altura, opacity: op,
      background: PALETA.painel, border: `2px solid ${PALETA.contorno}`, borderRadius: RAIO.hud, padding: '10px 18px', boxSizing: 'border-box',
      fontFamily: FONTES.mono, color: PALETA.texto, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
      {children ?? (
        <>
          <div style={{fontSize: TAMANHOS.hud * 0.7, opacity: 0.75, letterSpacing: 2, textTransform: 'uppercase'}}>{rotulo}</div>
          <div style={{fontSize: TAMANHOS.hud * 1.3, fontWeight: 700, color: PALETA.destaque, transform: `scale(${pulso})`, transformOrigin: 'left center'}}>
            {passos[idx]?.v ?? ''}
          </div>
        </>
      )}
    </div>
  );
};
