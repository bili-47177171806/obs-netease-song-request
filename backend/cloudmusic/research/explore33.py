# -*- coding: utf-8 -*-
"""挖 action_id 消费逻辑 + emitEvent kind + channel.call 用法。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    for kw, maxh, back, fwd in [(".action_id", 3, 260, 400), ("emitEvent", 3, 220, 260),
                                ("clearPlaylist", 2, 240, 200), ("doAdapter", 2, 260, 360),
                                ("channel.call", 2, 260, 300), ("addToPlayList", 4, 200, 220)]:
        r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s; const back = %s; const fwd = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push({ i, c: t.slice(Math.max(0, i - back), i + fwd).replace(/\n/g, ' ') });
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxh, back, fwd), await_promise=True)
        print(f"\n########## 『{kw}』 ##########")
        for s in r:
            print(f"[@{s['i']}]", s["c"][:780])
    c.close()


if __name__ == "__main__":
    sys.exit(main())