/**
 * Composição "Edicao": a edição inteira (vídeo 1080×1920, 30 fps). Só escolhe a cena ativa do perfil.
 * Perfil novo: troque o import abaixo pela cena do perfil (src/cenas/<sua-cena>.tsx), mantendo as props.
 */
import React from 'react';
import {EdicaoProps} from './tipos';
import {CenaExemplo} from './cenas/exemplo';

export const Edicao: React.FC<EdicaoProps> = (props) => <CenaExemplo {...props} />;
