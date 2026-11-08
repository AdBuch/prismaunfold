import type { ArtMotif, ImageRef } from '../models.ts';
import { esc } from './util.ts';

/** Deterministic PRNG so artwork is stable between renders. */
function rng(seed: number) {
  let a = seed * 2654435761 >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Palette { sky1: string; sky2: string; far: string; mid: string; near: string; accent: string; light: string }

const PALETTES: Record<ArtMotif, Palette> = {
  alpine:   { sky1: '#e9dfcf', sky2: '#c9d3d6', far: '#9fb1ba', mid: '#6f8794', near: '#3f5563', accent: '#e8b77a', light: '#f6efe2' },
  sea:      { sky1: '#d7dcd9', sky2: '#9fb3b4', far: '#6b8a8f', mid: '#3f6068', near: '#223c45', accent: '#e9c39b', light: '#eef0ea' },
  terraces: { sky1: '#f1dfc0', sky2: '#e8c799', far: '#b9a26a', mid: '#8a8a4c', near: '#56602f', accent: '#c4572d', light: '#f8ecd2' },
  night:    { sky1: '#0e1830', sky2: '#25365a', far: '#1b2748', mid: '#121b34', near: '#0a1022', accent: '#f1e3b8', light: '#f8f3e0' },
  trees:    { sky1: '#f3ead3', sky2: '#d9dfb7', far: '#aebb82', mid: '#6f8b4e', near: '#3e5a35', accent: '#d99b4a', light: '#faf4de' },
  city:     { sky1: '#d9d5cd', sky2: '#a9a8a6', far: '#807d7b', mid: '#4f4d52', near: '#2c2b30', accent: '#e9b45b', light: '#f1ece0' },
  seed:     { sky1: '#efe7d3', sky2: '#d6c9a8', far: '#b79f6d', mid: '#8a6e3d', near: '#4f3b1f', accent: '#c4572d', light: '#faf3df' },
  library:  { sky1: '#efe1c8', sky2: '#d8b98f', far: '#b08a5e', mid: '#7d5a3a', near: '#3f2b1c', accent: '#f4d58a', light: '#fbf0d6' },
  market:   { sky1: '#2a1f3a', sky2: '#6a3b4a', far: '#a8523f', mid: '#6b3033', near: '#2a1620', accent: '#f4c45a', light: '#fbe7b8' },
  grid:     { sky1: '#eee9de', sky2: '#d8d2c2', far: '#b6ae9a', mid: '#8d8571', near: '#4c4739', accent: '#8c2f1b', light: '#faf6ea' },
};

let uid = 0;

function ridge(r: () => number, base: number, amp: number, fill: string, w = 800, steps = 14): string {
  const pts: string[] = [`0,500`];
  let y = base + (r() - 0.5) * amp;
  for (let i = 0; i <= steps; i++) {
    y = base + (r() - 0.5) * amp * 2;
    pts.push(`${Math.round((i / steps) * w)},${Math.round(y)}`);
  }
  pts.push(`${w},500`);
  return `<polygon points="${pts.join(' ')}" fill="${fill}"/>`;
}

function body(motif: ArtMotif, seed: number, p: Palette): string {
  const r = rng(seed + motif.length * 17);
  const out: string[] = [];
  const sunX = 150 + r() * 500;
  switch (motif) {
    case 'alpine': {
      out.push(`<circle cx="${sunX}" cy="${130 + r() * 40}" r="46" fill="${p.accent}" opacity=".85"/>`);
      out.push(ridge(r, 250, 60, p.far));
      out.push(ridge(r, 310, 55, p.mid));
      out.push(`<rect x="0" y="360" width="800" height="140" fill="${p.sky2}"/>`);
      for (let i = 0; i < 9; i++) {
        out.push(`<rect x="${60 + r() * 600}" y="${372 + i * 12}" width="${80 + r() * 160}" height="2" fill="${p.light}" opacity=".5"/>`);
      }
      out.push(ridge(r, 420, 30, p.near, 800, 10));
      break;
    }
    case 'sea': {
      out.push(`<circle cx="${sunX}" cy="190" r="38" fill="${p.accent}" opacity=".8"/>`);
      out.push(`<rect x="0" y="240" width="800" height="260" fill="${p.mid}"/>`);
      for (let i = 0; i < 18; i++) {
        const y = 250 + i * 14;
        out.push(`<path d="M0 ${y} Q 100 ${y - 6 - r() * 6} 200 ${y} T 400 ${y} T 600 ${y} T 800 ${y}" stroke="${i % 3 ? p.far : p.light}" stroke-opacity=".5" fill="none" stroke-width="${1 + (i / 18) * 2}"/>`);
      }
      const sx = 200 + r() * 400;
      out.push(`<g fill="${p.near}"><rect x="${sx}" y="226" width="70" height="12"/><rect x="${sx + 40}" y="206" width="14" height="22"/><rect x="${sx + 8}" y="214" width="6" height="14"/></g>`);
      break;
    }
    case 'terraces': {
      out.push(`<circle cx="${sunX}" cy="120" r="52" fill="${p.accent}" opacity=".8"/>`);
      out.push(ridge(r, 230, 40, p.far));
      const cols = [p.far, p.mid, p.mid, p.near, p.near];
      for (let i = 0; i < 9; i++) {
        const y = 270 + i * 28;
        out.push(`<path d="M0 ${y + 30} Q 220 ${y - 12 - r() * 14} 420 ${y + 6} T 800 ${y - 8} V500 H0Z" fill="${cols[i % cols.length]}" opacity="${0.95 - i * 0.02}"/>`);
        out.push(`<path d="M0 ${y + 30} Q 220 ${y - 12} 420 ${y + 6} T 800 ${y - 8}" stroke="${p.light}" stroke-opacity=".35" fill="none" stroke-width="2"/>`);
      }
      break;
    }
    case 'night': {
      for (let i = 0; i < 90; i++) {
        out.push(`<circle cx="${r() * 800}" cy="${r() * 330}" r="${0.5 + r() * 1.5}" fill="${p.light}" opacity="${0.35 + r() * 0.6}"/>`);
      }
      const cx = 200 + r() * 400, cy = 90 + r() * 90;
      out.push(`<path d="M${cx} ${cy} L ${cx + 190} ${cy + 60}" stroke="${p.accent}" stroke-opacity=".35" stroke-width="5" stroke-linecap="round"/>`);
      out.push(`<circle cx="${cx}" cy="${cy}" r="6" fill="${p.accent}"/>`);
      out.push(ridge(r, 400, 40, p.mid));
      out.push(ridge(r, 450, 25, p.near));
      break;
    }
    case 'trees': {
      out.push(`<circle cx="${sunX}" cy="110" r="44" fill="${p.accent}" opacity=".7"/>`);
      out.push(`<rect x="0" y="360" width="800" height="140" fill="${p.far}"/>`);
      for (let row = 0; row < 3; row++) {
        const fills = [p.far, p.mid, p.near];
        const baseY = 330 + row * 40;
        for (let i = 0; i < 6 - row; i++) {
          const x = (i + 0.5) * (800 / (6 - row)) + (r() - 0.5) * 30;
          const rad = 54 + row * 22 + r() * 12;
          out.push(`<rect x="${x - 4 - row * 2}" y="${baseY - 10}" width="${8 + row * 4}" height="${70 + row * 30}" fill="${p.near}"/>`);
          out.push(`<circle cx="${x}" cy="${baseY - rad * 0.7}" r="${rad}" fill="${fills[row]}" opacity=".95"/>`);
        }
      }
      break;
    }
    case 'city': {
      let x = -10;
      while (x < 800) {
        const w = 50 + r() * 70, h = 120 + r() * 230;
        out.push(`<rect x="${x}" y="${500 - h}" width="${w}" height="${h}" fill="${r() > 0.5 ? p.mid : p.near}"/>`);
        for (let wy = 500 - h + 14; wy < 480; wy += 22) {
          for (let wx = x + 8; wx < x + w - 10; wx += 16) {
            if (r() > 0.62) out.push(`<rect x="${wx}" y="${wy}" width="7" height="10" fill="${p.accent}" opacity=".85"/>`);
          }
        }
        x += w + 4 + r() * 8;
      }
      break;
    }
    case 'library': {
      out.push(`<rect x="0" y="400" width="800" height="100" fill="${p.near}"/>`);
      for (let i = 0; i < 5; i++) {
        const x = 60 + i * 150;
        out.push(`<path d="M${x} 400 V190 a50 50 0 0 1 100 0 V400Z" fill="${p.accent}" opacity=".9"/>`);
        out.push(`<path d="M${x + 50} 140 V400 M${x} 260 H${x + 100}" stroke="${p.near}" stroke-width="4" fill="none"/>`);
        out.push(`<path d="M${x + 10} 400 L ${x - 40 + r() * 20} 500 H ${x + 160} L ${x + 90} 400Z" fill="${p.light}" opacity=".18"/>`);
      }
      break;
    }
    case 'market': {
      for (let s = 0; s < 3; s++) {
        const y = 60 + s * 40;
        out.push(`<path d="M0 ${y} Q 400 ${y + 70} 800 ${y}" stroke="${p.near}" stroke-width="2" fill="none"/>`);
        for (let i = 1; i < 12; i++) {
          const x = (i / 12) * 800;
          const yy = y + 70 * 2 * (x / 800) * (1 - x / 800) * 1;
          out.push(`<circle cx="${x}" cy="${yy + 8}" r="${7 + r() * 4}" fill="${p.accent}"/><circle cx="${x}" cy="${yy + 8}" r="16" fill="${p.accent}" opacity=".15"/>`);
        }
      }
      for (let i = 0; i < 5; i++) {
        const x = 20 + i * 155;
        out.push(`<rect x="${x}" y="330" width="130" height="170" fill="${p.near}"/><path d="M${x - 8} 330 L ${x + 65} 280 L ${x + 138} 330Z" fill="${p.far}"/>`);
        out.push(`<rect x="${x + 16}" y="370" width="98" height="12" fill="${p.accent}" opacity=".8"/>`);
      }
      break;
    }
    default: {
      for (let i = 0; i < 40; i++) {
        out.push(`<rect x="${(i % 8) * 100}" y="${Math.floor(i / 8) * 100}" width="100" height="100" fill="${[p.far, p.mid, p.near, p.accent][Math.floor(r() * 4)]}" opacity=".7"/>`);
      }
    }
  }
  return out.join('');
}

/** Returns an inline SVG for the image reference. 800x500, scales with `object-fit` like behaviour. */
export function artSvg(image: ImageRef): string {
  const p = PALETTES[image.motif] ?? PALETTES.grid;
  const id = `g${++uid}`;
  return `<svg class="art" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${esc(image.alt)}" xmlns="http://www.w3.org/2000/svg">
<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.sky1}"/><stop offset="1" stop-color="${p.sky2}"/></linearGradient>
<filter id="${id}n"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="${image.seed}"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .09 0"/></filter></defs>
<rect width="800" height="500" fill="url(#${id})"/>${body(image.motif, image.seed, p)}<rect width="800" height="500" filter="url(#${id}n)"/></svg>`;
}
