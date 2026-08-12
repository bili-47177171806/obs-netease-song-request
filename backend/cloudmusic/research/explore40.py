# -*- coding: utf-8 -*-
"""沿 fiber 链找 Provider 的 store，并取歌曲行 props。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const rows = [...document.querySelectorAll('div.tr')];
  const hit = rows.find(e => { const t = e.innerText || ''; return t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('#') === -1; });
  if (!hit) return { err: 'no row' };
  const k = Object.keys(hit).find(k => k.startsWith('__react'));
  const instanceKey = Object.keys(hit).find(k => k.startsWith('__reactInternalInstance$'));
  let f = hit[instanceKey];

  // 1) 向上找 store
  const path = [];
  let storeInfo = null;
  for (let i = 0; i < 60 && f; i++) {
    const mp = f.memoizedProps;
    const st = mp && mp.store;
    if (st && typeof st.dispatch === 'function' && typeof st.getState === 'function') {
      storeInfo = { depth: i, hasGetState: true, stateKeys: Object.keys(st.getState()).slice(0, 30) };
      path.push({ depth: i, hasStore: true, comp: (f.type && (f.type.name || f.type.displayName)) || '?', stateKeys: Object.keys(st.getState()).slice(0, 15) });
      window.__STORE__ = st;   // 缓存为全局引用
      break;
    }
    path.push({ depth: i, hasStore: false, comp: (f.type && (f.type.name || f.type.displayName)) || '?' });
    f = f.return;
  }

  // 2) 取歌曲行 props 里的数据
  let rowFiber = hit[instanceKey];
  let songData = null;
  for (let i = 0; i < 8 && rowFiber && !songData; i++) {
    const mp = rowFiber.memoizedProps;
    if (mp) {
      const probe = [];
      for (const key of Object.keys(mp)) {
        const v = mp[key];
        if (v && typeof v === 'object' && (v.id !== undefined && (v.name !== undefined || v.trackId !== undefined))) {
          const vv = {...v};
          ['albumId','artists','albumName','ar','al','duration','name','id','feat'].forEach(zz => {
            if (vv[zz] && typeof vv[zz] === 'object') vv[zz] = '[obj]';
          });
          let s; try { s = JSON.stringify(mp[key]).slice(0, 500); } catch (e) { s = String(v); }
          probe.push({ key, sample: s });
        }
        if (probe.length) { songData = probe; break; }
      }
    }
    rowFiber = rowFiber.return;
  }

  return { path: path.slice(-12), storeInfo, viewportW: window.innerWidth, songData };
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:6000])
    c.close()


if __name__ == "__main__":
    sys.exit(main())