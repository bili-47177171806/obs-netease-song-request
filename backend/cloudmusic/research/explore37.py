# -*- coding: utf-8 -*-
"""找 uploadPlayingCommands / playingCommands 的最终原生调用。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    for kw, maxh, back, fwd in [("uploadPlayingCommands", 6, 260, 500),
                                ("playingCommands", 4, 200, 400),
                                ("addCommand", 4, 260, 400)]:
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
            print(s["c"][:1000])
    c.close()


if __name__ == "__main__":
    sys.exit(main())