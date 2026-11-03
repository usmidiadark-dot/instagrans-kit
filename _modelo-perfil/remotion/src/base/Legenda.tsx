/**
 * Legenda em blocos que acendem com a voz (tempos por palavra do words.json: {w, start, end} em segundos).
 * Anti-reflow: o bloco inteiro é montado de uma vez com todas as palavras (as ainda não faladas ficam apagadas),
 * então o texto nunca muda de lugar enquanto acende. O bloco fica até o próximo começar (sem buraco que pisca).
 */
import React, {useMemo} from 'react';
import {useCurrentFrame} from 'remotion';
import {DURACOES, FONTES, PALETA, POSICOES, TAMANHOS, TELA} from '../estilo';
import {Palavra} from '../tipos';
import {NaAreaSegura} from './AreaSegura';
import {presenca} from './anim';

type Bloco = {palavras: Palavra[]; ini: number; fim: number};

export const montarBlocos = (words: Palavra[], porBloco = 4): Bloco[] => {
  // bloco fecha com porBloco palavras, no fim de frase (. ! ?) ou numa pausa da voz (> 0,4 s): nunca mistura duas frases
  const blocos: Bloco[] = [];
  let atual: Palavra[] = [];
  const fecha = () => {
    if (!atual.length) return;
    blocos.push({palavras: atual, ini: atual[0].start, fim: atual[atual.length - 1].end + DURACOES.respiroLegenda});
    atual = [];
  };
  words.forEach((p, i) => {
    atual.push(p);
    const prox = words[i + 1];
    if (atual.length >= porBloco || /[.!?]$/.test(p.w) || (prox && prox.start - p.end > 0.4)) fecha();
  });
  fecha();
  // encosta o fim de cada bloco no início do próximo quando a pausa é curta (evita some-e-volta < 0,5 s)
  for (let i = 0; i < blocos.length - 1; i++) {
    if (blocos[i + 1].ini - blocos[i].fim < 0.5) blocos[i].fim = blocos[i + 1].ini;
  }
  return blocos;
};

export const Legenda: React.FC<{words: Palavra[]; porBloco?: number; y?: number; ate?: number}> = ({words, porBloco = 4, y = POSICOES.legendaY, ate}) => {
  const f = useCurrentFrame();
  const t = f / TELA.fps;
  const blocos = useMemo(() => montarBlocos(words, porBloco), [words, porBloco]);
  const altura = TAMANHOS.legenda * 2.6;
  return (
    <>
      {blocos.map((b, i) => {
        const fim = ate !== undefined ? Math.min(b.fim, ate) : b.fim;
        const op = presenca(f, Math.round(b.ini * TELA.fps), Math.round(fim * TELA.fps), 4, 4);
        if (op <= 0) return null;
        return (
          <NaAreaSegura key={i} y={y} altura={altura} style={{opacity: op}}>
            <div style={{fontFamily: FONTES.corpo, fontWeight: FONTES.pesoCorpo, fontSize: TAMANHOS.legenda, lineHeight: 1.2,
              textAlign: 'center', textShadow: `0 4px 14px ${PALETA.sombraTexto}`}}>
              {b.palavras.map((p, j) => (
                <span key={j} style={{color: t >= p.start ? (j === b.palavras.findIndex((q) => t >= q.start && t < q.end) ? PALETA.destaque : PALETA.texto) : PALETA.textoApagado}}>
                  {p.w}{j < b.palavras.length - 1 ? ' ' : ''}
                </span>
              ))}
            </div>
          </NaAreaSegura>
        );
      })}
    </>
  );
};
