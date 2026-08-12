# -*- coding: utf-8 -*-
"""探查 window.api / MusicCorona 的结构，找播放队列相关的可用方法。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== window.api 的类型与键 ====")
    r = c.evaluate(r"""
(() => {
  const ks = Object.keys(window.api || {});
  return { type: typeof window.api, total: ks.length, keys: ks };
})()
""")
    if isinstance(r, dict) and "error" in r:
        print("ERR", r["error"])
    else:
        keys = r["keys"]
        print("type:", r["type"], " total:", r["total"])
        print("全部键:", json.dumps(keys, ensure_ascii=False)[:4000])

    print("\n==== api 中疑似播放/队列/歌单相关键 ====")
    c.evaluate(r"window.__k = Object.keys(window.api||{})")
    r = c.evaluate(r"""
(() => {
  const ks = window.__k || [];
  const rel = ks.filter(k => /play|queue|song|list|next|insert|schedule|player|add/i.test(k));
  return rel;
})()
""")
    print(r)

    print("\n==== MusicCorona / _MusicCorona ====")
    r = c.evaluate(r"""
(() => {
  const out = {};
  for (const g of ['MusicCorona', '_MusicCorona', 'MusicAPM']) {
    const o = window[g];
    if (o == null) { out[g] = 'null'; continue; }
    let keys = [];
    try { keys = Object.keys(o).slice(0, 40); } catch (e) { keys = ['<no keys>']; }
    out[g] = { type: typeof o, proto: Object.getPrototypeOf(o) ? Object.getPrototypeOf(o).constructor.name : '?',
               keys: keys };
  }
  return out;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    c.close()


if __name__ == "__main__":
    sys.exit(main())