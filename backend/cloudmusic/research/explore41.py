# -*- coding: utf-8 -*-
"""沿 fiber 链找 react-redux store（Context._currentValue 或 Provider prop）。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const hit = [...document.querySelectorAll('div.tr')].find(e => {
    const t = e.innerText || '';
    return t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('#') === -1;
  });
  if (!hit) return { err: 'no row' };
  const instanceKey = Object.keys(hit).find(k => k.startsWith('__reactInternalInstance$'));
  let f = hit[instanceKey];
  const path = [];
  let found = null;
  for (let i = 0; i < 400 && f; i++) {
    const type = f.type;
    // Context 对象挂 _currentValue
    if (type && typeof type === 'object' && type._currentValue) {
      const cv = type._currentValue;
      if (cv && cv.store && typeof cv.store.dispatch === 'function') {
        found = { via: 'context._currentValue', depth: i };
        window.__STORE__ = cv.store;
        break;
      }
    }
    // Provider 直接 prop
    const mp = f.memoizedProps;
    if (mp && mp.store && typeof mp.store.dispatch === 'function') {
      found = { via: 'Provider prop', depth: i };
      window.__STORE__ = mp.store;
      break;
    }
    // class 实例上挂 store
    if (f.stateNode && f.stateNode.store && typeof f.stateNode.store.dispatch === 'function') {
      found = { via: 'stateNode.store', depth: i };
      window.__STORE__ = f.stateNode.store;
      break;
    }
    path.push({ d: i, c: (type && (type.name || type.displayName)) ? String(type.name || type.displayName).slice(0, 20) : '?' });
    f = f.return;
  }
  return { found, topDepth: path.length, top: path.slice(-6) };
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    # 若找到 store，dump 状态结构
    if r.get("found"):
        st = c.evaluate(r"""
(() => {
  const s = window.__STORE__;
  if (!s) return null;
  const state = s.getState();
  const top = {};
  for (const k of Object.keys(state).slice(0, 60)) {
    const v = state[k];
    top[k] = (v && typeof v === 'object') ? Object.keys(v).slice(0, 12) : typeof v;
  }
  return { top, hasPlayingListHandoff: !!state['async:playingListHandoff'], dispatchIsFn: typeof s.dispatch };
})()
""")
        print("\nstore 状态结构:", json.dumps(st, ensure_ascii=False, indent=1)[:4000])
    c.close()


if __name__ == "__main__":
    sys.exit(main())