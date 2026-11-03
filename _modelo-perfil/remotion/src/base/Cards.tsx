/**
 * CardSeguir: a PAUSA para pedir para seguir (script.seguir = {t, dur?, texto?, arroba?}). Momento e duração configuráveis.
 * CardFinal: card com a oferta no hold final (script.oferta.card = {tag?, titulo, sub?}); o render.py exige ≥ 1,6 s depois da última palavra.
 * Os dois ficam na área segura e não desenham nada quando o campo não existe no script.
 */
import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {DURACOES, FONTES, PALETA, POSICOES, RAIO, TAMANHOS, TELA} from '../estilo';
import {NaAreaSegura} from './AreaSegura';
import {presenca} from './anim';
import {Script} from '../tipos';

const caixa: React.CSSProperties = {background: PALETA.painel, border: `2px solid ${PALETA.contorno}`, borderRadius: RAIO.caixa,
  padding: '36px 56px', textAlign: 'center', color: PALETA.texto};

export const CardSeguir: React.FC<{seguir?: Script['seguir']}> = ({seguir}) => {
  const f = useCurrentFrame();
  if (!seguir) return null;
  const q0 = Math.round(seguir.t * TELA.fps);
  const q1 = Math.round((seguir.t + (seguir.dur ?? DURACOES.pausaSeguir)) * TELA.fps);
  const op = presenca(f, q0, q1);
  if (op <= 0) return null;
  const pulo = interpolate(f - q0, [0, 6, 12], [40, -6, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <NaAreaSegura y={POSICOES.cardSeguirY} altura={320} style={{opacity: op}}>
      <div style={{...caixa, transform: `translateY(${pulo}px)`}}>
        <div style={{fontFamily: FONTES.titulo, fontWeight: FONTES.pesoTitulo, fontSize: TAMANHOS.card}}>{seguir.texto ?? 'Follow for more'}</div>
        {seguir.arroba ? <div style={{fontFamily: FONTES.corpo, fontSize: TAMANHOS.card * 0.6, color: PALETA.destaque, marginTop: 10}}>{seguir.arroba}</div> : null}
      </div>
    </NaAreaSegura>
  );
};

export const CardFinal: React.FC<{oferta?: Script['oferta']; inicio: number; fim: number}> = ({oferta, inicio, fim}) => {
  const f = useCurrentFrame();
  if (!oferta?.card) return null;
  const q0 = Math.round((oferta.t0 ?? inicio) * TELA.fps);
  const op = presenca(f, q0, Math.round(fim * TELA.fps) + 1, undefined, 1); // fica até o último quadro
  if (op <= 0) return null;
  const escala = interpolate(f - q0, [0, 10], [0.92, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <NaAreaSegura y={POSICOES.cardFinalY} altura={440} style={{opacity: op}}>
      <div style={{...caixa, transform: `scale(${escala})`}}>
        {oferta.card.tag ? <div style={{fontFamily: FONTES.mono, fontSize: TAMANHOS.card * 0.45, letterSpacing: 4, opacity: 0.8}}>{oferta.card.tag}</div> : null}
        <div style={{fontFamily: FONTES.titulo, fontWeight: FONTES.pesoTitulo, fontSize: TAMANHOS.card * 1.1, margin: '8px 0'}}>{oferta.card.titulo}</div>
        {oferta.card.sub ? <div style={{fontFamily: FONTES.corpo, fontSize: TAMANHOS.card * 0.6, color: PALETA.destaque}}>{oferta.card.sub}</div> : null}
      </div>
    </NaAreaSegura>
  );
};
