import {Config} from '@remotion/cli/config';

// GPU opcional: REMOTION_GL=angle (PC com placa de vídeo) ou swangle (máquina sem GPU). Sem a variável, o padrão do Remotion.
if (process.env.REMOTION_GL) Config.setChromiumOpenGlRenderer(process.env.REMOTION_GL as 'angle' | 'swangle');
Config.setConcurrency(null);
// porta própria opcional (o render.py já passa --port livre; isto é para uso manual)
if (process.env.REMOTION_PORTA) Config.setRendererPort(Number(process.env.REMOTION_PORTA));
