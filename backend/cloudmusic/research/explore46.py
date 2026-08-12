# -*- coding: utf-8 -*-
"""看 addListElement / removeAll / setCurrentPlay 上下文，找本地队列维护与插入语义。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    for kw, maxh, back, fwd in [("addListElement", 3, 900, 260), ("removeAll", 2, 300, 200),
                                ("setCurrentPlay", 2, 300, 300), ("\"network.fetch\"", 2, 300, 500)]:
        r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push({ i, c: t.slice(Math.max(0, i - %s), i + %s).replace(/\n/g, ' ') });
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxh, back, fwd), await_promise=True)
        print(f"\n########## 『{kw}』 ##########")
        for s in r:
            print(f"\n--- [@{s['i']}] ---")
            print(s["c"][:1100])
    c.close()


if __name__ == "__main__":
    sys.exit(main())