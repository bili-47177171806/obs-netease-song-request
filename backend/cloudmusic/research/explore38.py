# -*- coding: utf-8 -*-
"""枚举 player. 原生方法 + 定位 Jg 上传函数。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(async () => {
  const u = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf('"player.', i + 1)) !== -1 && out.length < 40) {
    out.push(t.slice(i + 1, i + 70));
    i += 1;
  }
  return [...new Set(out)];
})()
""" % json.dumps(APP), await_promise=True)
    print("==== 原生方法 player.* ====")
    for m in r:
        print(" ", m)

    for kw, maxh in [(".Jg", 4), ("Jg=", 3), ("Jg = ", 2)]:
        r2 = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push({ i, c: t.slice(Math.max(0, i - 200), i + 500).replace(/\n/g, ' ') });
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxh), await_promise=True)
        print(f"\n########## 『{kw}』 ##########")
        for s in r2:
            print(f"\n--- [@{s['i']}] ---")
            print(s["c"][:1000])
    c.close()


if __name__ == "__main__":
    sys.exit(main())