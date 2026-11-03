/**
 * ESTILO DO PERFIL: o único arquivo de tokens visuais.
 * Os valores abaixo são NEUTROS (padrão do modelo). Ao criar um perfil, o Claude troca estes valores pelo estilo
 * extraído dos vídeos de referência (paleta, fontes, ritmo, cantos, posições). Os componentes de src/base/ só leem daqui:
 * nenhum componente deve ter cor, fonte ou tempo "chumbado".
 *
 * Fonte: o padrão é a pilha do sistema (não reflui enquanto carrega). Fonte própria do perfil = carregar com
 * @remotion/fonts ou @remotion/google-fonts (ou FontFace + delayRender/continueRender) ANTES do primeiro quadro;
 * fonte carregando no meio do render faz o texto refluir e pular (o detector de piscadas reprova).
 */

export const TELA = {largura: 1080, altura: 1920, fps: 30} as const;

/** Área segura do feed (reel visto no corte 4:5 sem abrir): texto, HUD e cards só entre estes y. */
export const AREA_SEGURA = {yTopo: 285, yBase: 1635, margemX: 72} as const;

export const PALETA = {
  fundoA: '#3A5BD9', // gradiente do fundo vivo (nunca escuro e sem graça)
  fundoB: '#7B4FD6',
  fundoC: '#E0628A',
  luz: '#FFFFFF', // brilho/luz que passeia no fundo
  texto: '#FFFFFF',
  textoApagado: 'rgba(255,255,255,0.45)',
  destaque: '#FFD23F', // palavra que acende, número do insert
  painel: 'rgba(12,14,30,0.55)', // caixa de HUD/insert/card
  contorno: 'rgba(255,255,255,0.22)',
  sombraTexto: 'rgba(0,0,0,0.35)',
} as const;

export const FONTES = {
  titulo: '"Segoe UI", "Helvetica Neue", Arial, sans-serif',
  corpo: '"Segoe UI", "Helvetica Neue", Arial, sans-serif',
  mono: 'Consolas, "Courier New", monospace',
  pesoTitulo: 800,
  pesoCorpo: 700,
} as const;

export const TAMANHOS = {
  gancho: 150, // assunto do gancho: legível em 1 s no celular
  legenda: 64,
  insertValor: 140,
  insertRotulo: 38,
  hud: 30,
  card: 58,
} as const;

/** Durações em segundos (convertidas para quadros com seg()). */
export const DURACOES = {
  entrada: 0.35,
  saida: 0.3,
  gancho: 3.0, // os primeiros 3 s
  pausaSeguir: 2.0, // duração padrão do card de seguir (o script pode trocar)
  cardFinalMin: 1.6, // gate do render.py: ≥ 1,6 s depois da última palavra
  respiroLegenda: 0.25, // bloco de legenda some este tempo depois da última palavra
} as const;

/** Curvas como bezier [x1,y1,x2,y2] para Easing.bezier. */
export const EASING = {
  entrada: [0.16, 1, 0.3, 1] as const,
  saida: [0.7, 0, 0.84, 0] as const,
  suave: [0.45, 0, 0.55, 1] as const,
};

export const RAIO = {caixa: 28, pilula: 999, hud: 16} as const;

/** Posições fixas (y em px de 1080×1920; sempre dentro da AREA_SEGURA). */
export const POSICOES = {
  ganchoY: 760,
  legendaY: 1380, // centro do bloco de legenda
  insertY: 620,
  hud: {canto: 'topoDireito' as 'topoDireito' | 'topoEsquerdo', y: 300, x: 72},
  cardSeguirY: 980,
  cardFinalY: 960,
} as const;

/** Câmera 3D: perspectiva e profundidade das camadas (fundo longe, frente perto). */
export const CAMERA = {
  perspectiva: 1400,
  profundidades: {fundo: -600, meio: -200, frente: 0},
  derivaPx: 60, // quanto a câmera anda num plano (paralaxe)
} as const;

/** Grão/vinheta do fundo vivo (0 = desligado). */
export const TEXTURA = {vinheta: 0.35, brilhoLuz: 0.55} as const;

export const seg = (s: number) => Math.round(s * TELA.fps);
