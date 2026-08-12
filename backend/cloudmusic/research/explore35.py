# -*- coding: utf-8 -*-
"""找 emitEvent 消费端 和 kind→原生方法映射。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    for kw, maxh, back, fwd in [
        ("onAddItemToCurPlayingList", 1, 100, 3200),   # saga 完整体
        ("emitEvent\"", 5, 300, 700),                  # 消费端
        ("switchPlayMode", 4, 260, 420),               # kind 映射线索
    ]:
        r = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s; const max = %s; const back = %s; const fwd = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < max) {
    out.push({ i, c: t.slice(Math.max(0, i - back), Math.min(t.length, i + fwd)).replace(/\n/g, ' ') });
  }
  return out;
})()
""" % (json.dumps(APP), json.dumps(kw, ensure_ascii=False), maxh, back, fwd), await_promise=True)
        print(f"\n########## 『{kw}』 ##########")
        for s in r:
            print(f"\n--- [@{s['i']}] ---")
            print(s["c"][:3600])
    c.close()


if __name__ == "__main__":
    sys.exit(main())