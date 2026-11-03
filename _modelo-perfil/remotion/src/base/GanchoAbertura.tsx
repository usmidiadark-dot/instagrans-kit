/**
 * Gancho de abertura (primeiros 3 s): o ASSUNTO grande e legível em 1 s, sem depender da legenda nem do som.
 * Já está na tela no quadro 0 (nada de abrir vazio) e se mexe desde o início (escala/deriva), para não ser imagem parada.
 * Use junto com o desenho do assunto (children = ícone/objeto em código, acima do texto).
 */
import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {DURACOES, FONTES, PALETA, POSICOES, TAMANHOS, TELA, seg} from '../estilo';
import {NaAreaSegura} from './AreaSegura';
import {presenca} from './anim';

export const GanchoAbertura: React.FC<{texto: string; sub?: string; dur?: number; children?: React.ReactNode}> = ({texto, sub, dur = DURACOES.gancho, children}) => {
  const f = useCurrentFrame();
  const fim = seg(dur);
  // entra já visível (entrada de 1 quadro) e sai suave no fim do gancho
  const op = presenca(f, 0, fim, 1, seg(DURACOES.saida));
  if (op <= 0) return null;
  const escala = interpolate(f, [0, fim], [1, 1.08]);
  const altura = TAMANHOS.gancho * 2.6 + (sub ? TAMANHOS.legenda * 1.4 : 0) + (children ? 360 : 0);
  return (
    <NaAreaSegura y={POSICOES.ganchoY} altura={altura} style={{opacity: op, flexDirection: 'column'}}>
      {children ? <div style={{height: 340, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{children}</div> : null}
      <div style={{fontFamily: FONTES.titulo, fontWeight: FONTES.pesoTitulo, fontSize: TAMANHOS.gancho, lineHeight: 1.0, color: PALETA.texto,
        textAlign: 'center', textTransform: 'uppercase', transform: `scale(${escala})`, textShadow: `0 8px 24px ${PALETA.sombraTexto}`}}>
        {texto}
      </div>
      {sub ? <div style={{fontFamily: FONTES.corpo, fontWeight: FONTES.pesoCorpo, fontSize: TAMANHOS.legenda, color: PALETA.destaque, marginTop: 16, textAlign: 'center'}}>{sub}</div> : null}
    </NaAreaSegura>
  );
};

/** Duração do gancho em segundos (para a cena saber quando a legenda começa a dividir a tela). */
export const fimDoGancho = (fps = TELA.fps) => seg(DURACOES.gancho) / fps;
