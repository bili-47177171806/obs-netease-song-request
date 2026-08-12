# -*- coding: utf-8 -*-
"""提取全部 At.call 原生方法名（修正正则）。"""
import sys
import json
import re
from backend.cloudmusic.cdp import CDP, first_page

JS = [
    "orpheus://orpheus/pub/vendor/@cloudmusic-desktop/vendors-rudio@0.1.x/vendors-rudio.pc-new.production.js",
    "orpheus://orpheus/pub/hybrid/11.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/vendors~app.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/vendors~app~subApp.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/66.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/6.chunk.2b4bcc2.js",
]


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    expr = ("""
(async () => {
  const urls = %s;
  const cache = (window.__bc = window.__bc || {});
  const methods = {};
  const rx = /At\\.call\\("([^"]+)"/g;
  for (const u of urls) {
    let t = cache[u];
    if (t === undefined) { try { t = await (await fetch(u)).text(); cache[u] = t; } catch (e) { continue; } }
    let m;
    while ((m = rx.exec(t)) !== null) { if (m[1].indexOf('.') > 0) methods[m[1]] = 1; }
  }
  return { total: Object.keys(methods).length, keys: Object.keys(methods).sort() };
})()
""" % json.dumps(JS))

    raw = c.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    res = raw.get("result", {}).get("result", {})
    if "exceptionDetails" in res or "exceptionDetails" in raw.get("result", {}):
        print("JS 异常:", json.dumps(raw, ensure_ascii=False)[:800])
        return
    keys = res.get("value", {}).get("keys", [])
    print("全部原生方法名（共", len(keys), "）:")
    for k in keys:
        print("  ", k)
    print("\n==== 播放/队列/插入相关 ====")
    for k in keys:
        if re.search(r"play|queue|list|insert|song|next|track|position|seq", k, re.I):
            print("  ", k)
    c.close()


if __name__ == "__main__":
    sys.exit(main())