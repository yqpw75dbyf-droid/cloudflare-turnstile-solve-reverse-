"""
net_bridge_server.py — HTTP proxy bridge on port 8901.

Accepts POST /req with JSON {method, url, headers, body(base64), impersonate, proxy}
Uses curl_cffi Session (TLS impersonate=chrome136) so CF sees correct JA3.
Persists cookies across requests in a single Session (cf_chl_* survive between XHR calls).

POST /reset  — replace the session (new solve attempt with fresh cookies)
GET  /ping   — health check
"""

import base64
import os
import time
import warnings
from flask import Flask, request, jsonify
from curl_cffi.requests import Session, ExtraFingerprints

# suppress curl_cffi SSL verify=False warnings
warnings.filterwarnings("ignore")

app = Flask(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)
DEFAULT_IMP = "chrome146"   # profile curl_cffi mới nhất gần Chrome 153 nhất
# Chrome 153 vs chrome146: cipher list giống nhau (15 ciphers), 1 ext khác (0xCA34 ALPS — không fix được qua ExtraFingerprints)
# ExtraFingerprints: http2_no_priority đã có trong chrome146 native; header_order cho đúng thứ tự Chrome XHR POST
_CHROME_EXTRA_FP = ExtraFingerprints(
    http2_no_priority=True,
    # thứ tự header Chrome XHR POST: pseudo > content-type > JS-set > accept > sec-ch-ua* > ua > origin > sec-fetch-* > ae > al > cookie
    header_order='content-type,accept,sec-ch-ua,sec-ch-ua-mobile,sec-ch-ua-platform,user-agent,origin,sec-fetch-site,sec-fetch-mode,sec-fetch-dest,accept-encoding,accept-language,cookie',
)

# ponytail: global session — single CF solve at a time; per-caller sessions if concurrent
_session: Session | None = None


def _make_session(impersonate: str = DEFAULT_IMP, proxy: str | None = None, headers: dict | None = None) -> Session:
    # headers (UA, sec-ch-ua*, Accept-Language) do runner gửi từ fingerprint → khớp JS env
    kw: dict = dict(
        impersonate=impersonate,
        verify=False,
        headers=headers or {"User-Agent": UA},
        timeout=30,
    )
    p = proxy or os.environ.get("CF_PROXY", "").strip()
    if p:
        kw["proxies"] = {"http": p, "https": p}
    return Session(**kw)


def get_session(impersonate: str = DEFAULT_IMP, proxy: str | None = None) -> Session:
    global _session
    if _session is None:
        _session = _make_session(impersonate, proxy)
    return _session


@app.route("/ping", methods=["GET"])
def ping():
    return "ok"


@app.route("/reset", methods=["POST"])
def reset():
    global _session
    data = request.json or {}
    _session = _make_session(
        data.get("impersonate", DEFAULT_IMP),
        data.get("proxy") or os.environ.get("CF_PROXY", "").strip() or None,
        data.get("headers"),
    )
    return jsonify({"ok": True})


@app.route("/req", methods=["POST"])
def handle_req():
    data = request.json
    method = (data.get("method") or "GET").upper()
    url = data["url"]
    headers = data.get("headers") or {}
    body_b64 = data.get("body")
    body = base64.b64decode(body_b64) if body_b64 else None
    impersonate = data.get("impersonate") or os.environ.get("CF_IMP", DEFAULT_IMP)
    proxy = data.get("proxy") or os.environ.get("CF_PROXY", "").strip() or None

    sess = get_session(impersonate, proxy)
    t0 = time.time()

    try:
        resp = sess.request(
            method,
            url,
            headers=headers,
            content=body,
            verify=False,
            allow_redirects=True,
            timeout=150,
            extra_fp=_CHROME_EXTRA_FP,
        )
        print(f"[req] {method} {resp.status_code} {int((time.time()-t0)*1000)}ms len={len(resp.content)} {url[:120]}", flush=True)
        return jsonify({
            "status": resp.status_code,
            "url": str(resp.url),
            "headers": dict(resp.headers),
            "body": base64.b64encode(resp.content).decode(),
        })
    except Exception as exc:
        print(f"[req] {method} ERR {int((time.time()-t0)*1000)}ms {url[:120]} :: {exc}", flush=True)
        return jsonify({"error": str(exc), "status": 0, "headers": {}, "body": ""}), 500


if __name__ == "__main__":
    port = int(os.environ.get("BRIDGE_PORT", 8901))
    print(f"[net_bridge_server] listening on 0.0.0.0:{port}")
    # threaded=False: requests are sync curl_cffi calls; no GIL issue with single thread
    app.run(host="0.0.0.0", port=port, threaded=True)   # XHR async song song như Chrome; Session dùng curl thread-local
