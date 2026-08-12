# -*- coding: utf-8 -*-
"""看 handoff 管线后续：insertTracks(非clear) 的原生调用。"""
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
  return t.slice(4239880 - 200, 4239880 + 4600).replace(/\n/g, ' ');
})()
""" % json.dumps(APP), await_promise=True)
    print("==== handoff 管线全文 ====")
    print(r[:4800])

    print("\n\n==== startPlayNewSource 处理 ====")
    for kw, maxh, back, fwd in [("startPlayNewSource", 4, 300, 700)]:
        r2 = c.evaluate(r"""
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
        for s in r2:
            print(f"\n--- [@{s['i']}] ---")
            print(s["c"][:1000])
    c.close()


if __name__ == "__main__":
    sys.exit(main())