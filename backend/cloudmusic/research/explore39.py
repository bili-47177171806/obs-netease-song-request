# -*- coding: utf-8 -*-
"""查运行时 store 全局 + 从歌曲行 fiber 取完整歌曲对象。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== window 上的 store/dispatch/redux 相关 ====")
    r = c.evaluate(r"""
(() => {
  const names = Object.getOwnPropertyNames(window);
  const rel = names.filter(n => /store|dispatch|getState|redux|saga|__redux/i.test(n));
  const out = {};
  for (const n of rel.slice(0, 25)) {
    let t; try { t = typeof window[n]; } catch (e) { t = '?'; }
    out[n] = t;
  }
  return { rel: out, hasReactDevHook: typeof window.__REACT_DEVTOOLS_GLOBAL_HOOK__ };
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    print("\n==== 第一首数据行的 React fiber props（找歌曲对象）====")
    r = c.evaluate(r"""
(() => {
  const rows = [...document.querySelectorAll('div.tr')];
  const hit = rows.find(e => { const t = e.innerText || ''; return t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('#') === -1; });
  if (!hit) return 'no row';
  const k = Object.keys(hit).find(k => k.startsWith('__reactFiber$'));
  if (!k) return 'no fiber keys: ' + Object.keys(hit).join(',');
  let f = hit[k];
  const seen = [];
  for (let i = 0; i < 10 && f; i++) {
    const mp = f.memoizedProps;
    if (mp) {
      const t = Object.keys(mp);
      const songish = t.filter(key => /song|data|track|item|resource/i.test(key));
      seen.push({ depth: i, allKeys: t.slice(0, 25), songish, type: (f.type && (f.type.name || f.type.displayName)) || '?' });
      // 若 props 里有直接含 id/name 的对象就跳出来
    }
    f = f.return;
  }
  return seen;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])

    c.close()


if __name__ == "__main__":
    sys.exit(main())