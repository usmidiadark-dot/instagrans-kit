/**
 * Composição "Capa": pôster 1080×1920 do post (1 quadro), props = {script} com script.capa = {texto, sub?, fundo?}.
 * A capa precisa dizer o que é o vídeo, caber no corte 3:4 da grade (texto no meio, longe das bordas de cima/baixo)
 * e usar a cor do ciclo da grade (o render.py grava script.capa.fundo pela ordem de publicação).
 */
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {FONTES, PALETA, TAMANHOS} from './estilo';
import {EdicaoProps} from './tipos';
import {NaAreaSegura} from './base/AreaSegura';
import {Raio} from './cenas/exemplo';

export const Capa: React.FC<EdicaoProps> = ({script}) => {
  const capa = script?.capa;
  const fundo = capa?.fundo ?? PALETA.fundoA;
  return (
    <AbsoluteFill style={{background: `linear-gradient(170deg, ${fundo} 0%, ${PALETA.fundoB} 100%)`}}>
      {capa ? (
        // zona do corte 3:4 da grade: 1080×1440 centrado (y 240–1680); texto no miolo, dentro da área segura
        <NaAreaSegura y={960} altura={1000} style={{flexDirection: 'column', gap: 24}}>
          {/* o desenho do assunto (aqui o raio do exemplo); perfil novo troca pelo assunto da edição */}
          <Raio tamanho={420} />
          <div style={{fontFamily: FONTES.titulo, fontWeight: FONTES.pesoTitulo, fontSize: TAMANHOS.gancho, lineHeight: 1, color: PALETA.texto,
            textAlign: 'center', textTransform: 'uppercase', textShadow: `0 8px 24px ${PALETA.sombraTexto}`}}>{capa.texto}</div>
          {capa.sub ? <div style={{fontFamily: FONTES.corpo, fontWeight: FONTES.pesoCorpo, fontSize: TAMANHOS.legenda, color: PALETA.destaque}}>{capa.sub}</div> : null}
        </NaAreaSegura>
      ) : null}
    </AbsoluteFill>
  );
};
