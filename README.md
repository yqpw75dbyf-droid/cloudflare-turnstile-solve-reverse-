# cf_turnstile_js — browserless Cloudflare Turnstile solver

Solves Cloudflare Turnstile without a browser: the challenge page and Cloudflare's own orchestrate/VM run inside
jsdom, and all network traffic goes through a curl_cffi bridge (Chrome TLS fingerprint, direct connection, no proxy).
No Chrome is launched at solve time. ~5–8 s per solve.

## Install
```
npm install                      # jsdom 29.1.1
pip install -r requirements.txt  # flask, curl_cffi
```

## Start the solve server
```
cd solver
python net_bridge_server.py      # network bridge on :8901  (BRIDGE_PORT=... to change)
node solver_api.js               # solve API on :5091       (node solver_api.js <port>)
```
Single solve from the command line (no server): `node cf_solve.js` → prints `*** TOKEN ***` followed by the token.

## API
Two calls: create a task, then poll for the result.

**1. Create task** — `GET /turnstile?url=<page url>&sitekey=<sitekey>`
```json
{ "errorId": 0, "taskId": "5568a982-ba67-4744-9b00-0c0e538886a5" }
```

**2. Poll result** — `GET /result?id=<taskId>` (every ~2 s)
```json
{ "status": "processing" }
{ "errorId": 0, "status": "ready", "solution": { "token": "1.ta4rB4uZ..." } }
{ "errorId": 1, "errorDescription": "..." }
```
A finished task is removed after its result is read once. Tasks run one at a time (the bridge uses a single
curl_cffi session), so a task queued behind others stays `processing` longer.

### curl
```
curl "http://127.0.0.1:5091/turnstile?url=https://example.com/login&sitekey=0x4AAAAAAA..."
curl "http://127.0.0.1:5091/result?id=<taskId>"
```

### Python
```python
import time, requests

API = "http://127.0.0.1:5091"

def solve(url: str, sitekey: str, timeout: int = 120) -> str:
    task = requests.get(f"{API}/turnstile", params={"url": url, "sitekey": sitekey}).json()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        r = requests.get(f"{API}/result", params={"id": task["taskId"]}).json()
        if r.get("status") == "processing":
            continue
        if r.get("errorId"):
            raise RuntimeError(r.get("errorDescription"))
        return r["solution"]["token"]
    raise TimeoutError("solve timed out")
```

### Node.js
```js
const API = 'http://127.0.0.1:5091';
async function solve(url, sitekey) {
  const { taskId } = await (await fetch(`${API}/turnstile?url=${encodeURIComponent(url)}&sitekey=${sitekey}`)).json();
  for (;;) {
    await new Promise((r) => setTimeout(r, 2000));
    const r = await (await fetch(`${API}/result?id=${taskId}`)).json();
    if (r.status === 'processing') continue;
    if (r.errorId) throw new Error(r.errorDescription);
    return r.solution.token;
  }
}
```

## Configuration
- `sitekey` from the request is passed to the solver (`CF_SITEKEY`).
- The embedding page context (parent origin, page URL, referrer) comes from `solver/parent_ctx.json`; the
  browser/machine fingerprint comes from `captured_env.json` and `solver/chrome_profile_b.json`.
- Environment: `BRIDGE_PORT` (bridge port, default 8901), `CF_TIMEOUT` (ms per solve, default 90000).

## Files
| File | Role |
|---|---|
| `cf_solve.js` | one solve: api.js → challenge HTML → jsdom runs Cloudflare's orchestrate/VM → token |
| `cf_dom.js`, `cf_media.js`, `cf_canvas.js`, `cf_jsengine.js`, `cf_surface.js`, `cf_temporal.js`, `cf_worker.js` | emulated browser environment (DOM, images, canvas/WebGL, workers, …) |
| `cf_fohook.js`, `tp_lib.js` | replace static fingerprint fields in the payload with real Chrome values from `chrome_profile_b.json` |
| `net_bridge.js`, `net_bridge_server.py` | every request goes through curl_cffi (impersonate chrome146) |
| `solver_api.js` | HTTP solve API |
| `chrome_profile_b.json` | Chrome fingerprint profile **for Cloudflare build `b`** (captured offline) |
| `parent_ctx.json`, `../captured_env.json`, other `*.json` | parent page context and machine fingerprint data |

## Limitations
- Tied to the current Cloudflare build (`/turnstile/v0/b/...`); a new build needs a new `chrome_profile_<build>.json`.
