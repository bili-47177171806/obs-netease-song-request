# -*- coding: utf-8 -*-
"""全量扫 window 下挂了播放/队列方法的对象；并看 _MusicCorona 原型。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== _MusicCorona / MusicCorona 原型方法 ====")
    r = c.evaluate(r"""
(() => {
  const out = {};
  for (const g of ['_MusicCorona', 'MusicCorona']) {
    const fn = window[g];
    if (typeof fn !== 'function') { out[g] = 'not function'; continue; }
    const p = fn.prototype;
    out[g] = { own: Object.getOwnPropertyNames(p || {}).slice(0, 80),
               staticKeys: Object.keys(fn).slice(0, 40) };
  }
  return out;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    print("\n==== 全 window 扫描：含播放/队列方法的对象 ====")
    r = c.evaluate(r"""
(() => {
  const rel = /play|queue|song|next|insert|schedule|player|list|music/i;
  const found = [];
  const names = Object.getOwnPropertyNames(window);
  for (const n of names) {
    let v;
    try { v = window[n]; } catch (e) { continue; }
    if (v == null) continue;
    const t = typeof v;
    if (t === 'object' || t === 'function') {
      let ks = [];
      try { ks = Object.keys(v); } catch (e) {}
      if (ks.length === 0) continue;
      const m = ks.filter(k => rel.test(k));
      if (m.length) found.push({ name: n, type: t, matched: m.slice(0, 25) });
    }
  }
  return found.sort((a,b) => a.matched.length - b.matched.length).slice(0, 40);
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    print("\n==== require 是否存在 ====")
    r = c.evaluate(r"({ hasRequire: typeof require, hasModule: typeof module, hasProcess: typeof process })")
    print(r)

    c.close()


if __name__ == "__main__":
    sys.exit(main())