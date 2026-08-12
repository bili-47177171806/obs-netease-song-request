# -*- coding: utf-8 -*-
"""查 window.channel 等运行时桥对象 + bundle 里 At 的定义。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== window 上疑似原生桥对象 ====")
    r = c.evaluate(r"""
(() => {
  const names = ['channel','MusicCorona','_MusicCorona','MNB','api','navigator','cef'];
  const out = {};
  for (const n of names) {
    const v = window[n];
    if (v == null) { out[n] = 'null'; continue; }
    let k = [];
    try { k = Object.keys(v); } catch (e) {}
    out[n] = { type: typeof v, keys: k.slice(0, 25) };
  }
  return out;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    # 找 bundle 里 At 的定义
    for kw, maxh in [("At=", 3), ("At =", 2), ("var At", 2), ("_Adapter", 2), (".Adapter", 2)]:
        r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push(t.slice(Math.max(0, i - 160), i + 320).replace(/\n/g, ' '));
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxh), await_promise=True)
        print(f"\n########## 『{kw}』 ##########")
        for s in r:
            print("---")
            print(s[:500])

    c.close()


if __name__ == "__main__":
    sys.exit(main())