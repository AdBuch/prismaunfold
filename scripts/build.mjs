import { build, context } from 'esbuild';
import { copyFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const p = (rel) => fileURLToPath(new URL(rel, root));

const options = {
  entryPoints: [p('src/main.ts')],
  bundle: true,
  format: 'esm',
  target: 'es2022',
  outfile: p('dist/main.js'),
  sourcemap: true,
  minify: false,
  logLevel: 'info',
};

async function copyStatic() {
  await mkdir(p('dist'), { recursive: true });
  await copyFile(p('src/index.html'), p('dist/index.html'));
  await copyFile(p('src/styles/main.css'), p('dist/styles.css'));
}

export async function run({ watch = false } = {}) {
  await copyStatic();
  if (!watch) return build(options);
  const ctx = await context(options);
  await ctx.watch();
  const { watch: fsWatch } = await import('node:fs');
  fsWatch(p('src'), { recursive: true }, (_e, f) => { if (f && /\.(css|html)$/.test(f)) copyStatic(); });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await run({ watch: process.argv.includes('--watch') });
}
