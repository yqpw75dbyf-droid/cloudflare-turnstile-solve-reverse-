# cf_turnstile_js — browserless Cloudflare Turnstile solver

Solves Cloudflare Turnstile without a browser: the challenge page and Cloudflare's own orchestrate/VM run inside
jsdom, and all network traffic goes through a curl_cffi bridge (Chrome TLS fingerprint, direct connection, no proxy).
No Chrome is launched at solve time.

Tested live on the Roblox login widget: most runs return a token, ~5–8 s per solve.

## Install
```
npm install                      # jsdom 29.1.1
pip install -r requirements.txt  # flask, curl_cffi
```

## Run
```
cd solver
python net_bridge_server.py      # bridge on :8901  (BRIDGE_PORT=... to change)
node solver_api.js               # API on :5091     (node solver_api.js <port>)
```
Single solve without the API: `node cf_solve.js` → prints `*** TOKEN ***` followed by the token.

With the Roblox login script:
```
python roblox_login.py --solver http://127.0.0.1:5091
```

API:
- `GET /turnstile?url=&sitekey=` → `{errorId: 0, taskId}`
- `GET /result?id=` → `{status: "processing"}` | `{errorId: 0, status: "ready", solution: {token}}` | `{errorId: 1, errorDescription}`

Tasks are solved one at a time (the bridge uses a single curl_cffi session).

## Files
| File | Role |
|---|---|
| `cf_solve.js` | one solve: api.js → challenge HTML → jsdom runs Cloudflare's orchestrate/VM → token |
| `cf_dom.js`, `cf_media.js`, `cf_canvas.js`, `cf_jsengine.js`, `cf_surface.js`, `cf_temporal.js`, `cf_worker.js` | emulated browser environment (DOM, images, canvas/WebGL, workers, …) |
| `cf_fohook.js`, `tp_lib.js` | replace static fingerprint fields in the payload with real Chrome values from `chrome_profile_b.json` |
| `net_bridge.js`, `net_bridge_server.py` | every request goes through curl_cffi (impersonate chrome146) |
| `solver_api.js` | HTTP API used by `roblox_login.py` |
| `chrome_profile_b.json` | Chrome fingerprint profile **for Cloudflare build `b`** (captured offline) |
| `parent_ctx.json`, `../captured_env.json`, other `*.json` | parent page context and machine fingerprint data |

## Limitations
- Tied to the current Cloudflare build (`/turnstile/v0/b/...`); a new build needs a new `chrome_profile_<build>.json`.
