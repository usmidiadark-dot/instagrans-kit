/**
 * CENA DE EXEMPLO (mínima): só prova o encaixe de todas as peças de src/base/ com public/exemplo/script.json.
 * O motor de um perfil novo TROCA este arquivo pela cena do perfil (mesma assinatura: props da Edicao).
 *
 * Contrato que toda cena precisa cumprir (o render.py e o piscadas.py dependem disso):
 * - props = {script, words, capa?, soOverlay?}; duração vem de script.duration_s (Root.tsx).
 * - soOverlay = true → desenhar SÓ textos/HUD/inserts/cards sobre preto (sem fundo, câmera, luz, vinheta, grão).
 * - capa = true → quadro da capa com o texto de script.capa por cima.
 * - anti-piscada: nada de Math.random/Date.now; formas sorteadas uma vez (constante de módulo) com random(semente).
 */
import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {FONTES, PALETA, TAMANHOS, TELA} from '../estilo';
import {EdicaoProps, Plano} from '../tipos';
import {Fundo} from '../base/Fundo';
import {Camada, Camera3D} from '../base/Camera3D';
import {Legenda} from '../base/Legenda';
import {Hud} from '../base/Hud';
import {Insert} from '../base/Insert';
import {GanchoAbertura, fimDoGancho} from '../base/GanchoAbertura';
import {CardFinal, CardSeguir} from '../base/Cards';
import {NaAreaSegura} from '../base/AreaSegura';
import {presenca, sorteio} from '../base/anim';

// geometria fixa (anti-piscada): sorteada UMA vez no carregamento do módulo, com semente
const NUVENS = Array.from({length: 7}, (_, i) => ({
  x: sorteio(`nuvem-x-${i}`) * 1080, y: 200 + sorteio(`nuvem-y-${i}`) * 1500,
  r: 160 + sorteio(`nuvem-r-${i}`) * 220, fase: sorteio(`nuvem-f-${i}`) * Math.PI * 2,
}));

const Nuvens: React.FC = () => {
  const t = useCurrentFrame() / TELA.fps;
  return (
    <AbsoluteFill>
      {NUVENS.map((n, i) => (
        <div key={i} style={{position: 'absolute', left: n.x - n.r + Math.sin(t * 0.6 + n.fase) * 30, top: n.y - n.r * 0.5,
          width: n.r * 2, height: n.r, borderRadius: n.r, background: 'rgba(255,255,255,0.14)', filter: 'blur(6px)'}} />
      ))}
    </AbsoluteFill>
  );
};

/** Assunto desenhado em código (SVG): o raio. Perfil novo troca por seus próprios desenhos. */
export const Raio: React.FC<{tamanho?: number}> = ({tamanho = 360}) => {
  const t = useCurrentFrame() / TELA.fps;
  const brilho = 0.75 + 0.25 * Math.sin(t * 9);
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 100 100" style={{filter: `drop-shadow(0 0 ${18 * brilho}px ${PALETA.destaque})`}}>
      <polygon points="58,4 22,56 46,56 36,96 80,38 54,38" fill={PALETA.destaque} stroke={PALETA.texto} strokeWidth={2} strokeLinejoin="round" />
    </svg>
  );
};

const planoAtual = (shots: Plano[], t: number) => shots.find((s) => t >= s.t_start && t < s.t_end) ?? shots[shots.length - 1];

export const CenaExemplo: React.FC<EdicaoProps> = ({script, words, capa, soOverlay}) => {
  const f = useCurrentFrame();
  const t = f / TELA.fps;
  if (!script) return <AbsoluteFill style={{background: PALETA.fundoA}} />;
  const plano = planoAtual(script.shots, t);
  const fimVoz = words.length ? words[words.length - 1].end : script.duration_s;
  const gancho = fimDoGancho();
  // o assunto sai da frente enquanto um card está na tela (card e assunto nunca se sobrepõem)
  const seg0 = script.seguir ? presenca(f, Math.round(script.seguir.t * TELA.fps), Math.round((script.seguir.t + (script.seguir.dur ?? 2)) * TELA.fps)) : 0;
  const fin0 = script.oferta?.card ? presenca(f, Math.round((script.oferta.t0 ?? fimVoz + 0.1) * TELA.fps), Math.round(script.duration_s * TELA.fps) + 1, undefined, 1) : 0;
  const subir = interpolate(t, [gancho - 0.4, gancho], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) * (1 - Math.max(seg0, fin0));

  return (
    <AbsoluteFill style={{background: soOverlay ? '#000' : undefined}}>
      {/* CENA (some no soOverlay) */}
      {!soOverlay && (
        <Camera3D key={plano.n} movimento={plano.camera.move} inicio={Math.round(plano.t_start * TELA.fps)} fim={Math.round(plano.t_end * TELA.fps)}>
          <Camada z="fundo"><Fundo /></Camada>
          <Camada z="meio"><Nuvens /></Camada>
          <Camada z="frente">
            {t >= gancho - 0.4 && !capa ? (
              <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: subir, transform: `translateY(${-180}px)`}}>
                <Raio tamanho={420} />
              </AbsoluteFill>
            ) : null}
          </Camada>
        </Camera3D>
      )}

      {/* OVERLAY (textos/HUD/inserts/cards): fica no soOverlay */}
      {capa && script.capa ? (
        <NaAreaSegura y={900} altura={900} style={{flexDirection: 'column'}}>
          <Raio tamanho={380} />
          <div style={{fontFamily: FONTES.titulo, fontWeight: FONTES.pesoTitulo, fontSize: TAMANHOS.gancho, color: PALETA.texto, textAlign: 'center', lineHeight: 1}}>
            {script.capa.texto}
          </div>
        </NaAreaSegura>
      ) : (
        <>
          {script.gancho ? (
            <GanchoAbertura texto={script.gancho.texto} sub={script.gancho.sub}>{soOverlay ? null : <Raio tamanho={320} />}</GanchoAbertura>
          ) : null}
          {script.hud ? <Hud rotulo={script.hud.rotulo} passos={script.hud.passos} fim={fimVoz + 0.2} /> : null}
          {(script.dados ?? []).map((d, i) => <Insert key={i} {...d} />)}
          <Legenda words={words} porBloco={script.legenda?.porBloco ?? 4} />
          <CardSeguir seguir={script.seguir} />
          <CardFinal oferta={script.oferta} inicio={fimVoz + 0.1} fim={script.duration_s} />
        </>
      )}
    </AbsoluteFill>
  );
};
