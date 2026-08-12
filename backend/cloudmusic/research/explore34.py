# -*- coding: utf-8 -*-
"""抠 playingList/onAddItemToCurPlayingList 的 saga 处理体 + insertTracks 相关调用。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    for kw, maxh, back, fwd in [
        ("onAddItemToCurPlayingList", 3, 200, 1200),
        ("insertTracks", 3, 300, 500),
        ("insertVoices", 2, 200, 400),
        ("emitEvent", 1, 0, 400),
    ]:
        r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s; const back = %s; const fwd = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    const start = Math.max(0, i - back);
    out.push({ i, c: t.slice(start, Math.min(t.length, i + fwd)).replace(/\n/g, ' ') });
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxh, back, fwd), await_promise=True)
        print(f"\n########## 『{kw}』 ##########")
        for s in r:
            print(f"\n--- [@{s['i']}] ---")
            print(s["c"][:1800])
    c.close()


if __name__ == "__main__":
    sys.exit(main())