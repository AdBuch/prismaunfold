import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { run } from './build.mjs';

const dist = fileURLToPath(new URL('../dist/', import.meta.url));
const port = Number(process.env.PORT ?? 4200);
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.map': 'application/json', '.svg': 'image/svg+xml' };

if (process.argv.includes('--watch')) await run({ watch: true });

createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', 'http://localhost');
  let file = normalize(join(dist, decodeURIComponent(url.pathname)));
  if (!file.startsWith(dist)) { res.writeHead(403).end('Forbidden'); return; }
  try {
    if (!(await stat(file)).isFile()) throw new Error('not a file');
  } catch {
    // Client-side routes fall back to index.html; missing assets stay 404.
    if (extname(url.pathname)) { res.writeHead(404).end('Not found'); return; }
    file = join(dist, 'index.html');
  }
  const body = await readFile(file);
  res.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream', 'Cache-Control': 'no-cache' });
  res.end(body);
}).listen(port, () => console.log(`PrismUnfold running at http://localhost:${port}`));
