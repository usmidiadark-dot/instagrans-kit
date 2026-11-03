// Precheck de composição (antes do render): mede textos do DOM em quadros amostrados e acusa sobreposição, contraste baixo,
// texto pequeno, texto coberto e texto fora do quadro/da área segura. Uso:
//   node precheck.mjs <pasta_remotion> <composicao> <props.json> <saida.json> [--passo=15] [--safe=y0,y1,x0,x1] [--min-fonte=28]
import {createRequire} from 'module';
import path from 'path';
import fs from 'fs';
import os from 'os';
import {fileURLToPath} from 'url';
import net from 'net';

// porta livre: com várias sessões renderizando (perfis diferentes) a 3000 é disputada e uma serve a composição da outra
const porta = await new Promise((res) => { const sv = net.createServer(); sv.listen(0, '127.0.0.1', () => { const p = sv.address().port; sv.close(() => res(p)); }); });

const [, , remotionDir, comp, propsFile, outJson, ...flags] = process.argv;
const fl = Object.fromEntries(flags.map((f) => f.replace(/^--/, '').split('=')));
const PASSO = +(fl.passo || 15);
const MINFONTE = +(fl['min-fonte'] || 28);
const SAFE = fl.safe ? fl.safe.split(',').map(Number) : null;
const FRAMES_DIR = fl['frames-dir'] ? path.resolve(fl['frames-dir']) : null; // guarda os quadros em escala 1 para a checagem de contraste por pixel (precheck.py)
if (FRAMES_DIR) fs.mkdirSync(FRAMES_DIR, {recursive: true});

const rdir = path.resolve(remotionDir);
const req = createRequire(path.join(rdir, 'package.json'));
const {bundle} = req('@remotion/bundler');
const R = req('@remotion/renderer');
const props = JSON.parse(fs.readFileSync(propsFile, 'utf8'));

const aqui = path.dirname(fileURLToPath(import.meta.url));
const entry = path.join(rdir, 'src', '_precheck_entry.ts');
const medidorTmp = path.join(rdir, 'src', '_precheck_medidor.ts'); // copiado para dentro do projeto para resolver 'remotion'
fs.copyFileSync(path.join(aqui, 'medidor.ts'), medidorTmp);
fs.writeFileSync(entry, `import './index';\nimport './_precheck_medidor';\n`);
let serveUrl;
try {
  serveUrl = await bundle({entryPoint: entry, rootDir: rdir, ignoreRegisterRootWarning: true});
} finally {
  fs.rmSync(entry, {force: true});
  fs.rmSync(medidorTmp, {force: true});
}

const chromiumOptions = {gl: 'angle'};
const composition = await R.selectComposition({serveUrl, id: comp, inputProps: props, chromiumOptions, logLevel: 'error', port: porta});
const browser = await R.openBrowser('chrome', {chromiumOptions, logLevel: 'error'});
const frames = []; // varredura do DOM: todos estes quadros numa carga só
if (fl.frames) fl.frames.split(',').map(Number).filter((f) => f >= 0 && f < composition.durationInFrames).forEach((f) => frames.push(f)); // lista explícita (ex.: logo após cada palavra da legenda)
else for (let f = 0; f < composition.durationInFrames; f += PASSO) frames.push(f);
const PIXEL = +(fl['pixel-passo'] || 60);
const pixelFrames = FRAMES_DIR ? frames.filter((f) => f % PIXEL === 0) : [frames[0]];   // stills só onde vai medir contraste por pixel
const tmp = path.join(os.tmpdir(), 'precheck_still.jpg');
const medidas = new Map();
let primeiro = true;
for (const f of pixelFrames) {
  const ip = primeiro ? {...props, __precheck_frames: frames} : props; primeiro = false;
  await R.renderStill({
    composition, serveUrl, frame: f, output: FRAMES_DIR ? path.join(FRAMES_DIR, `f${f}.jpg`) : tmp, inputProps: ip, puppeteerInstance: browser,
    port: porta, timeoutInMilliseconds: 900000, imageFormat: 'jpeg', jpegQuality: 90, scale: FRAMES_DIR ? 1 : 0.1, logLevel: 'error', chromiumOptions,
    onBrowserLog: (l) => {
      if (l.text.startsWith('__PRE__')) {
        const j = JSON.parse(l.text.slice(7));
        medidas.set(j.frame, j.itens);
      }
    },
  });
}
await browser.close({silent: true});

const W = composition.width;
const H = composition.height;
const achados = new Map();
const marca = (tipo, chave, t, detalhe) => {
  const k = tipo + '|' + chave;
  const a = achados.get(k) || {tipo, detalhe, t0: t, t1: t, n: 0};
  a.t1 = t;
  a.n++;
  if (detalhe.ratio !== undefined) a.detalhe.ratio = Math.max(a.detalhe.ratio ?? 0, detalhe.ratio);   // intensidade máxima da sobreposição
  achados.set(k, a);
};
for (const f of frames) {
  const it = medidas.get(f);
  if (!it) {
    marca('sem_medida', String(f), f / 30, {frame: f});
    continue;
  }
  const t = f / 30;
  it.forEach((a, i) => {
    const id = a.txt;
    if (a.fonte_px < MINFONTE) marca('texto_pequeno', id, t, {txt: id, fonte_px: a.fonte_px, minimo: MINFONTE});
    if (a.contraste !== null && a.contraste < 3) marca('contraste_baixo', id, t, {txt: id, contraste: a.contraste, minimo: 3});
    if (a.coberto_por) marca('texto_coberto', id + '|' + a.coberto_por, t, {txt: id, por: a.coberto_por});
    if (a.x < -2 || a.y < -2 || a.x + a.w > W + 2 || a.y + a.h > H + 2) marca('fora_do_quadro', id, t, {txt: id, x: a.x, y: a.y, w: a.w, h: a.h});
    else if (SAFE && (a.y < SAFE[0] || a.y + a.h > SAFE[1] || a.x < SAFE[2] || a.x + a.w > SAFE[3])) marca('fora_da_area_segura', id, t, {txt: id, y: a.y, fim_y: a.y + a.h});
    for (let j = i + 1; j < it.length; j++) {
      const b = it[j];
      if (a.coberto_por || b.coberto_por) continue; // um deles está escondido sob um card opaco (por desenho): não colide de verdade
      if (a.txt === b.txt && Math.abs(a.x - b.x) < 10 && Math.abs(a.y - b.y) < 10) continue; // cópia de sombra/contorno
      const ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      const razao = ix > 0 && iy > 0 ? (ix * iy) / Math.min(a.w * a.h, b.w * b.h) : 0;
      if (razao > 0.25) marca(a.girado || b.girado ? 'texto_sobreposto_girado' : 'texto_sobreposto', [a.txt, b.txt].sort().join(' <-> '), t, {a: a.txt, b: b.txt, ratio: +razao.toFixed(2)});
    }
  });
}
const lista = [...achados.values()].map((a) => ({...a, t0: +a.t0.toFixed(2), t1: +a.t1.toFixed(2)}));
fs.writeFileSync(outJson.replace(/\.json$/, '.medidas.json'), JSON.stringify({W, H, medidas: Object.fromEntries(medidas)}));
fs.writeFileSync(outJson, JSON.stringify({comp, quadros_medidos: frames.length, passo: PASSO, achados: lista}, null, 1));
console.log(`precheck: ${frames.length} quadros, ${lista.length} achado(s) -> ${outJson}`);
