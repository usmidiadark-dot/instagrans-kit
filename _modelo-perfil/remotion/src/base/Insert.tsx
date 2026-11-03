/**
 * Insert de dado/número: valor grande + rótulo, entra com escala e sai por opacidade.
 * Tempos em segundos (t, ate). Fica na área segura. No máximo 2 inserts juntos na tela (regra do feed).
 */
import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {FONTES, PALETA, POSICOES, RAIO, TAMANHOS, TELA} from '../estilo';
import {NaAreaSegura} from './AreaSegura';
import {presenca} from './anim';

export type InsertProps = {t: number; ate: number; valor: string; rotulo?: string; unidade?: string; y?: number};

export const Insert: React.FC<InsertProps> = ({t, ate, valor, rotulo, unidade, y = POSICOES.insertY}) => {
  const f = useCurrentFrame();
  const q0 = Math.round(t * TELA.fps);
  const op = presenca(f, q0, Math.round(ate * TELA.fps));
  if (op <= 0) return null;
  const escala = interpolate(f - q0, [0, 8, 14], [0.7, 1.06, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const altura = TAMANHOS.insertValor * 1.2 + (rotulo ? TAMANHOS.insertRotulo * 1.6 : 0) + 40;
  return (
    <NaAreaSegura y={y} altura={altura} style={{opacity: op}}>
      <div style={{background: PALETA.painel, border: `2px solid ${PALETA.contorno}`, borderRadius: RAIO.caixa, padding: '20px 48px',
        textAlign: 'center', transform: `scale(${escala})`, color: PALETA.texto}}>
        <div style={{fontFamily: FONTES.titulo, fontWeight: FONTES.pesoTitulo, fontSize: TAMANHOS.insertValor, lineHeight: 1.1, color: PALETA.destaque}}>
          {valor}{unidade ? <span style={{fontSize: TAMANHOS.insertValor * 0.45, marginLeft: 12}}>{unidade}</span> : null}
        </div>
        {rotulo ? <div style={{fontFamily: FONTES.corpo, fontWeight: FONTES.pesoCorpo, fontSize: TAMANHOS.insertRotulo, opacity: 0.85}}>{rotulo}</div> : null}
      </div>
    </NaAreaSegura>
  );
};
