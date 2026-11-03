/**
 * Composições do perfil. O render.py lê perfil.yaml → composicao {edicao: Edicao, capa: Capa, cena: codigo}
 * e chama `npx remotion render|still src/index.ts <id> --props=<pasta>/props.json` com cwd = <perfil>/remotion.
 * Sem --props (Studio/teste), as composições usam o exemplo de public/exemplo/.
 */
import React from 'react';
import {Composition} from 'remotion';
import {Edicao} from './Edicao';
import {Capa} from './Capa';
import {TELA} from './estilo';
import {EdicaoProps, Palavra, Script} from './tipos';
import scriptExemplo from '../public/exemplo/script.json';
import wordsExemplo from '../public/exemplo/words.json';

const exemplo: EdicaoProps = {script: scriptExemplo as unknown as Script, words: wordsExemplo as Palavra[]};

export const Root: React.FC = () => (
  <>
    <Composition id="Edicao" component={Edicao} fps={TELA.fps} width={TELA.largura} height={TELA.altura} durationInFrames={TELA.fps}
      defaultProps={exemplo}
      calculateMetadata={({props}) => ({durationInFrames: props.script ? Math.ceil(props.script.duration_s * TELA.fps) : TELA.fps})} />
    <Composition id="Capa" component={Capa} fps={TELA.fps} width={TELA.largura} height={TELA.altura} durationInFrames={1}
      defaultProps={exemplo} />
  </>
);
