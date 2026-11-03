/** Tipos das props que o render.py passa: {script: script.json, words: words.json, capa?, soOverlay?}. */

export type Palavra = {w: string; start: number; end: number};

export type Plano = {
  n: number;
  beat: string;
  t_start: number;
  t_end: number;
  vo?: string;
  on_screen?: {text?: string; style?: string; keyword?: string}[];
  camera: {plane: string; move: string};
  layers: string[];
};

export type Script = {
  profile: string;
  edition: string;
  title: string;
  format: string;
  duration_s: number;
  shots: Plano[];
  caption: string;
  /** gancho dos primeiros 3 s: assunto grande, sem depender da legenda */
  gancho?: {texto: string; sub?: string};
  /** HUD fixa no canto: rótulo + valores que mudam no tempo */
  hud?: {rotulo: string; passos: {t: number; v: string}[]};
  /** inserts de dado/número */
  dados?: {t: number; ate: number; valor: string; rotulo?: string; unidade?: string}[];
  /** pausa para pedir para seguir (momento e duração configuráveis) */
  seguir?: {t: number; dur?: number; texto?: string; arroba?: string};
  /** card final com a oferta (o render.py preenche a partir do perfil.yaml) */
  oferta?: {palavra?: string; t0?: number; card?: {tag?: string; titulo: string; sub?: string}};
  /** capa do post (composição Capa) */
  capa?: {texto: string; sub?: string; fundo?: string; t?: number};
  /** legenda em blocos: quantas palavras por bloco (padrão 4) */
  legenda?: {porBloco?: number};
};

export type EdicaoProps = {
  script: Script | null;
  words: Palavra[];
  capa?: boolean;
  soOverlay?: boolean;
  soSujeito?: boolean;
};
