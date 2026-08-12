# -*- coding: utf-8 -*-
"""在 app.chunk 里挖 nextPlay / 播放列表 / queue 相关代码上下文。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    for kw, maxhits in [("nextPlay", 14), ("播放列表", 10), ("addQueue", 8), ("insertQueue", 8), ("queue", 8)]:
        r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push(t.slice(Math.max(0, i - 220), i + 260).replace(/\n/g, ' '));
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxhits), await_promise=True)
        print(f"\n########## 『{kw}』 上下文（{len(r)} 条）##########")
        for j, s in enumerate(r):
            print(f"\n--- [{j}] ---")
            print(s[:520])

    c.close()


if __name__ == "__main__":
    sys.exit(main())