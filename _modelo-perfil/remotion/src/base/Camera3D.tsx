/**
 * Câmera 3D simples em CSS: camadas em profundidades diferentes (translateZ) dentro de uma perspectiva.
 * A câmera desliza/aproxima por plano e cada camada anda conforme a profundidade (paralaxe).
 * Uso: <Camera3D movimento="push|pan|tilt|orbita|fixa" inicio={q0} fim={q1}><Camada z="fundo">…</Camada>…</Camera3D>
 */
import React, {createContext, useContext} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {CAMERA, EASING} from '../estilo';
import {ease} from './anim';

export type Movimento = 'push' | 'pull' | 'pan' | 'tilt' | 'orbita' | 'fixa';

const Ctx = createContext({x: 0, y: 0, z: 0, rot: 0});

export const Camera3D: React.FC<{movimento?: Movimento | string; inicio: number; fim: number; children: React.ReactNode}> = ({movimento = 'push', inicio, fim, children}) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [inicio, Math.max(inicio + 1, fim)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease(EASING.suave)});
  const d = CAMERA.derivaPx;
  const cam = {
    push: {x: 0, y: 0, z: p * d * 3, rot: 0},
    pull: {x: 0, y: 0, z: (1 - p) * d * 3, rot: 0},
    pan: {x: (p - 0.5) * d * 2, y: 0, z: d, rot: 0},
    tilt: {x: 0, y: (p - 0.5) * d * 2, z: d, rot: 0},
    orbita: {x: Math.sin(p * Math.PI - Math.PI / 2) * d, y: 0, z: d, rot: (p - 0.5) * 6},
    fixa: {x: 0, y: 0, z: 0, rot: 0},
  }[movimento as Movimento] ?? {x: 0, y: 0, z: 0, rot: 0};
  return (
    <Ctx.Provider value={cam}>
      <AbsoluteFill style={{perspective: CAMERA.perspectiva, overflow: 'hidden'}}>
        <AbsoluteFill style={{transformStyle: 'preserve-3d', transform: `rotateY(${cam.rot}deg)`}}>{children}</AbsoluteFill>
      </AbsoluteFill>
    </Ctx.Provider>
  );
};

/** Camada numa profundidade: "fundo" | "meio" | "frente" ou número em px (negativo = longe). */
export const Camada: React.FC<{z: keyof typeof CAMERA.profundidades | number; children: React.ReactNode}> = ({z, children}) => {
  const cam = useContext(Ctx);
  const prof = typeof z === 'number' ? z : CAMERA.profundidades[z];
  // escala compensa o encolhimento da perspectiva, para a camada continuar cobrindo a tela
  const escala = (CAMERA.perspectiva - prof) / CAMERA.perspectiva;
  const fator = 1 + prof / CAMERA.perspectiva; // camadas longe andam menos (paralaxe)
  return (
    <AbsoluteFill style={{transform: `translate3d(${-cam.x * fator}px, ${-cam.y * fator}px, ${prof + cam.z}px) scale(${escala * 1.08})`}}>
      {children}
    </AbsoluteFill>
  );
};
