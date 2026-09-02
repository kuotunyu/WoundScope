import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const BASE_PATH = '/WoundScope/';
const HOST = '127.0.0.1';
const PORT = 4173;
const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
};

function fail(code) {
  throw new Error(code);
}

function loadPublishRoot() {
  const value = process.env.WOUNDSCOPE_PAGES_PUBLISH_DIR;
  if (!value || !path.isAbsolute(value)) {
    fail('PUBLISH_DIR_INVALID');
  }
  const stat = fs.statSync(value, { throwIfNoEntry: false });
  if (!stat || !stat.isDirectory()) {
    fail('PUBLISH_DIR_INVALID');
  }
  return value;
}

function normalizeRelativePath(urlPath) {
  if (urlPath === BASE_PATH) {
    return 'index.html';
  }
  if (!urlPath.startsWith(BASE_PATH)) {
    return null;
  }
  const remainder = urlPath.slice(BASE_PATH.length);
  if (!remainder || remainder.endsWith('/')) {
    return null;
  }
  const pieces = remainder.split('/');
  const decoded = [];
  for (const piece of pieces) {
    if (!piece) {
      return null;
    }
    const value = decodeURIComponent(piece);
    if (value === '.' || value === '..' || value.includes('\\')) {
      return null;
    }
    decoded.push(value);
  }
  return decoded.join('/');
}

function createAllowlist(publishRoot) {
  const manifestPath = path.join(publishRoot, 'pages-manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const allowed = new Set(['pages-manifest.json']);
  for (const fileRecord of manifest.files) {
    allowed.add(fileRecord.path);
  }
  return allowed;
}

function responseHeaders(filePath, size) {
  return {
    'Cache-Control': 'no-store',
    'Content-Length': String(size),
    'Content-Type': MIME_TYPES[path.extname(filePath)] ?? 'application/octet-stream',
    'X-Content-Type-Options': 'nosniff',
  };
}

const publishRoot = loadPublishRoot();
const allowlist = createAllowlist(publishRoot);
const notFoundPath = path.join(publishRoot, '404.html');
const notFoundBody = fs.readFileSync(notFoundPath);

const server = http.createServer((request, response) => {
  const requestUrl = new URL(request.url ?? '/', `http://${HOST}:${PORT}`);
  if (requestUrl.search) {
    response.writeHead(404, responseHeaders(notFoundPath, notFoundBody.length));
    response.end(notFoundBody);
    return;
  }
  const relativePath = normalizeRelativePath(requestUrl.pathname);
  if (!relativePath || !allowlist.has(relativePath)) {
    response.writeHead(404, responseHeaders(notFoundPath, notFoundBody.length));
    response.end(notFoundBody);
    return;
  }
  const targetPath = path.join(publishRoot, relativePath);
  const stat = fs.statSync(targetPath, { throwIfNoEntry: false });
  if (!stat || !stat.isFile()) {
    response.writeHead(404, responseHeaders(notFoundPath, notFoundBody.length));
    response.end(notFoundBody);
    return;
  }
  response.writeHead(200, responseHeaders(targetPath, stat.size));
  fs.createReadStream(targetPath).pipe(response);
});

server.listen(PORT, HOST, () => {
  process.stdout.write(`listening ${HOST}:${PORT}\n`);
});
