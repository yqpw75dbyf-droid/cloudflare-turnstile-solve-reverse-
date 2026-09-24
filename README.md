# cf_turnstile_js — solver Cloudflare Turnstile không trình duyệt (bản đang chạy được)

Bản sao sạch của `cf_native/browserless`: chỉ gồm file cần để chạy. Đã kiểm trên thư mục này:
6/7 lần `cf_solve.js` ra TOKEN (lần hỏng là CF bắt click), qua API 1/1 (2026-09-24).

Chạy bằng jsdom (không mở Chrome), mạng đi thẳng qua bridge curl_cffi (TLS giống Chrome, không proxy).

## Cài
```
npm install                      # jsdom 29.1.1
pip install -r requirements.txt  # flask, curl_cffi
```

## Chạy
```
cd solver
python net_bridge_server.py      # bridge :8901  (BRIDGE_PORT=... để đổi)
node solver_api.js               # API :5091     (node solver_api.js <port>)
```
Giải thử 1 lần không qua API: `node cf_solve.js` → in `*** TOKEN ***` + token.

Dùng với Roblox login:
```
python roblox_login.py --solver http://127.0.0.1:5091
```
API: `GET /turnstile?url=&sitekey=` → `{taskId}`; `GET /result?id=` → `{status:"processing"}` | `{status:"ready", solution:{token}}`.
Mỗi lần giải ~5–8 giây, API chạy tuần tự từng task (bridge dùng 1 phiên curl_cffi chung).

## File
| File | Vai trò |
|---|---|
| `cf_solve.js` | giải 1 lần: api.js → HTML challenge → jsdom chạy orchestrate/VM của CF → token |
| `cf_dom.js`, `cf_media.js`, `cf_canvas.js`, `cf_jsengine.js`, `cf_surface.js`, `cf_temporal.js`, `cf_worker.js` | môi trường trình duyệt giả (DOM, ảnh, canvas/WebGL, worker…) |
| `cf_fohook.js`, `tp_lib.js` | thay field fingerprint tĩnh trong payload bằng giá trị Chrome thật (`chrome_profile_b.json`) |
| `net_bridge.js`, `net_bridge_server.py` | mọi request đi qua curl_cffi (impersonate chrome146) |
| `solver_api.js` | API cho `roblox_login.py` |
| `chrome_profile_b.json` | profile Chrome **theo build CF `b`** (ghi offline). CF đổi build → cần ghi lại |
| `parent_ctx.json`, `../captured_env.json`, các `*.json` còn lại | ngữ cảnh trang Roblox + dữ liệu fingerprint của máy |

## Giới hạn
- Phụ thuộc build CF hiện tại (`/turnstile/v0/b/...`); build mới cần profile mới.
- Roblox có acc bị hỏi `captchav2` (HUMAN/PerimeterX) thay vì Turnstile — bản này không giải loại đó.
