'use strict';
// solver_api.js — API Turnstile tương thích roblox_login.py (kiểu D3-vin api.py), backend = cf_solve.js (browserless).
//   GET /turnstile?url=&sitekey=  → {errorId:0, taskId}
//   GET /result?id=               → {status:'processing'} | {errorId:0, status:'ready', solution:{token}} | {errorId:1, errorDescription}
// Mỗi task chạy `node cf_solve.js` riêng (jsdom sạch). Cần net_bridge_server.py (:8901).
// usage: node solver_api.js [port=5091]   → python roblox_login.py --solver http://127.0.0.1:5091
const http = require('http');
const path = require('path');
const crypto = require('crypto');
const { execFile } = require('child_process');

const PORT = +(process.argv[2] || 5091);   // 5072/5073 đã có solver cũ (api.py, native_server.py) của user
const TASKS = new Map();
let chain = Promise.resolve();

function runSolve(sitekey) {
  return new Promise((resolve) => {
    execFile(process.execPath, [path.join(__dirname, 'cf_solve.js')], {
      cwd: __dirname, timeout: 120000, maxBuffer: 64 << 20,
      env: { ...process.env, CF_SITEKEY: sitekey || process.env.CF_SITEKEY || '' },
    }, (err, stdout) => {
      const m = String(stdout).match(/\*\*\* TOKEN \*\*\*\s*\n(\S+)/);
      if (m) return resolve({ token: m[1] });
      const f = String(stdout).match(/\[!\] FAILED (.*)/);
      resolve({ error: f ? f[1].slice(0, 300) : (err ? err.message : 'no token') });
    });
  });
}

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  const out = (o) => { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(o)); };
  if (u.pathname === '/turnstile') {
    const id = crypto.randomUUID(), sitekey = u.searchParams.get('sitekey') || '';
    TASKS.set(id, { status: 'processing' });
    console.log(`[api] task ${id.slice(0, 8)} sitekey=${sitekey} url=${u.searchParams.get('url')}`);
    // ponytail: một solve tại một thời điểm (bridge dùng 1 session curl_cffi chung); muốn song song thì mỗi task một bridge (BRIDGE_PORT)
    chain = chain.then(async () => {
      const t0 = Date.now(), r = await runSolve(sitekey);
      TASKS.set(id, r.token ? { status: 'ready', token: r.token } : { status: 'error', error: r.error });
      console.log(`[api] task ${id.slice(0, 8)} ${r.token ? 'TOKEN len=' + r.token.length : 'FAIL ' + r.error} (${Date.now() - t0}ms)`);
    });
    return out({ errorId: 0, taskId: id });
  }
  if (u.pathname === '/result') {
    const t = TASKS.get(u.searchParams.get('id') || '');
    if (!t) return out({ errorId: 1, errorDescription: 'unknown task' });
    if (t.status === 'processing') return out({ status: 'processing' });
    TASKS.delete(u.searchParams.get('id'));
    return t.token ? out({ errorId: 0, status: 'ready', solution: { token: t.token } }) : out({ errorId: 1, errorDescription: t.error });
  }
  res.writeHead(404); res.end();
}).listen(PORT, () => console.log(`[api] Turnstile solver (browserless) :${PORT}`));
