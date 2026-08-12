# -*- coding: utf-8 -*-
"""定位原生 bridge 入口 At 的定义与原生类/方法注册。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def ctx(kw, maxhits=3, back=300, fwd=300, url=APP):
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s; const back = %s; const fwd = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push(t.slice(Math.max(0, i - back), i + fwd).replace(/\n/g, ' '));
  }
  return out;
})()
""" % (json.dumps(url), json.dumps(kw, ensure_ascii=False), maxhits, back, fwd), await_promise=True)
    c.close()
    return r


def main():
    for kw, maxh in [("winhelper", 3), ("At.call", 2), ("JsBridge", 3), ("coreBridge", 3),
                     ("callNative", 3), ("NativeBridge", 3), ("postMessage", 2)]:
        r = ctx(kw, maxh)
        print(f"\n########## 『{kw}』 ##########")
        for s in r:
            print("---")
            print(s[:640])
    sys.exit(0)


if __name__ == "__main__":
    main()