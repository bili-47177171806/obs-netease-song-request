# -*- coding: utf-8 -*-
"""深挖 MNB / __mnb_globals__ 桥的结构。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== MNB 全部自有键及类型 ====")
    r = c.evaluate(r"""
(() => {
  const o = window.MNB;
  const ks = o == null ? [] : Object.getOwnPropertyNames(o);
  return ks.map(k => {
    let v; try { v = o[k]; } catch (e) { return { k, t: 'getter-throw' }; }
    let t = typeof v;
    let len = -1;
    if (v != null && (t === 'object' || t === 'function')) {
      try { len = Object.keys(v).length; } catch (e) {}
    }
    if (t === 'function') len = v.length;
    return { k, t, len };
  });
})()
""")
    for row in r:
        print(row)

    print("\n==== MNB 原型方法 ====")
    r = c.evaluate(r"""
(() => {
  const proto = window.MNB && window.MNB.prototype;
  if (!proto) return [];
  return Object.getOwnPropertyNames(proto);
})()
""")
    print(r)

    print("\n==== __mnb_globals__ 内容 ====")
    r = c.evaluate(r"""
(() => {
  const o = window.__mnb_globals__;
  const out = {};
  for (const k of Object.keys(o || {})) {
    let v = o[k];
    let s;
    try { s = JSON.stringify(v); } catch (e) { s = String(v); }
    out[k] = s.slice(0, 400);
  }
  return out;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    c.close()


if __name__ == "__main__":
    sys.exit(main())