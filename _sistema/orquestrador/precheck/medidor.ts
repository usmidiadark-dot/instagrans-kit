// Medidor injetado pelo precheck.mjs: mede os textos do DOM a cada quadro que o Remotion pinta e loga "__PRE__{json}".
// Não altera nada da composição; só lê. (Entrada gerada em <perfil>/remotion/src/_precheck_entry.ts e apagada depois.)
import {delayRender, continueRender, getInputProps} from 'remotion';

const luz = (c: number[]) => {
  const f = (v: number) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
};
const cor = (s: string): number[] | null => {
  const m = s.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
  return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
};
const opac = (el: Element) => {
  let o = 1;
  for (let e: Element | null = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity);
  return o;
};
const fundo = (el: Element) => {
  for (let e: Element | null = el; e; e = e.parentElement) {
    const c = cor(getComputedStyle(e).backgroundColor);
    if (c && c[3] >= 0.5) return c;
  }
  return null;
};

const medir = (frame: number) => {
  const itens: any[] = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const txt = (n.textContent || '').replace(/\s+/g, ' ').trim();
    const el = n.parentElement;
    if (!txt || !el || /^(SCRIPT|STYLE)$/.test(el.tagName)) continue;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') continue;
    const o = opac(el);
    if (o < 0.05) continue;
    const r = document.createRange();
    r.selectNodeContents(n);
    const rs = Array.from(r.getClientRects()).filter((q) => q.width > 0 && q.height > 0);
    if (!rs.length) continue;
    const b = r.getBoundingClientRect();
    const fs = parseFloat(st.fontSize);
    const lh = parseFloat(st.lineHeight);
    const razao = isFinite(lh) && fs ? lh / fs : 1.2;
    const c = cor(st.color);
    const f = fundo(el);
    let contraste: number | null = null;
    if (c && f) {
      const a = Math.max(luz(c), luz(f));
      const z = Math.min(luz(c), luz(f));
      contraste = +((a + 0.05) / (z + 0.05)).toFixed(2);
    }
    // coberto: o que está por cima do centro do texto e não é o próprio texto (nem pai/filho), opaco e com fundo/imagem
    let coberto_por: string | null = null;
    const cx = b.left + b.width / 2;
    const cy = b.top + b.height / 2;
    if (cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight) {
      for (const t of document.elementsFromPoint(cx, cy)) {
        if (t === el || el.contains(t) || t.contains(el)) break;
        const bg = cor(getComputedStyle(t).backgroundColor);
        if (opac(t) > 0.9 && ((bg && bg[3] > 0.9) || /^(CANVAS|IMG|VIDEO)$/.test(t.tagName))) {
          coberto_por = t.tagName.toLowerCase() + (t.id ? '#' + t.id : '');
          break;
        }
      }
    }
    // texto girado: a caixa do navegador é a envolvente, então sobreposição de caixas pode ser falso positivo
    let girado = false;
    for (let e: Element | null = el; e; e = e.parentElement) {
      const tr = getComputedStyle(e).transform;
      if (tr && tr !== 'none') {
        const m = new DOMMatrix(tr);
        if (Math.abs(Math.atan2(m.b, m.a)) > 0.01) girado = true;
      }
    }
    itens.push({
      girado,
      txt: txt.slice(0, 60),
      x: Math.round(b.left),
      y: Math.round(b.top),
      w: Math.round(b.width),
      h: Math.round(b.height),
      fonte_px: +(rs[0].height / razao).toFixed(1),
      op: +o.toFixed(2),
      contraste,
      coberto_por,
      cor: st.color,
    });
  }
  console.log('__PRE__' + JSON.stringify({frame, itens}));
};

const raf2 = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));
const espera = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

const instala = () => {
  const w: any = window;
  if (!w.remotion_setFrame) {
    setTimeout(instala, 20);
    return;
  }
  if (w.__pre_wrapped) return;
  w.__pre_wrapped = true;
  const orig = w.remotion_setFrame;
  let varreu = false;
  w.remotion_setFrame = (frame: number, ...rest: any[]) => {
    const h = delayRender('precheck ' + frame);
    const r = orig(frame, ...rest);
    const lista: number[] | undefined = (getInputProps() as any).__precheck_frames;
    if (lista && !varreu) {
      // varredura: UMA carga de página mede todos os quadros da lista (sem screenshot), muito mais rápido que um still por quadro
      varreu = true;
      (async () => {
        try {
          for (const f of lista) {
            orig(f, ...rest);
            await raf2();
            await espera(150);
            medir(f);
          }
        } finally {
          continueRender(h);
        }
      })();
      return r;
    }
    setTimeout(
      () =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            try {
              medir(frame);
            } finally {
              continueRender(h);
            }
          }),
        ),
      300,
    );
    return r;
  };
};
instala();
