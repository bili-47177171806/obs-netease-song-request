# -*- coding: utf-8 -*-
"""打桩监听 channel.call / fetch，dispatch 插队，看命令发往何处。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  window.__callLog = [];
  window.__fetchLog = [];
  try {
    const orig = window.channel.call;
    window.channel.call = function (method, params, opts) {
      let s = null;
      try { s = typeof params === 'string' ? params.slice(0, 1200) : JSON.stringify(params).slice(0, 1200); } catch (e) { s = String(params); }
      window.__callLog.push({ m: method, p: s });
      return orig.apply(this, arguments);
    };
  } catch (e) { window.__callLog.push({ patchErr: String(e) }); }
  try {
    const of = window.fetch;
    window.fetch = function () {
      try { window.__fetchLog.push(String(arguments[0]).slice(0, 300)); } catch (e) {}
      return of.apply(this, arguments);
    };
  } catch (e) {}
  return 'patched';
})()
""")
    print("patch:", r)

    # 重新 dispatch 一次（用最小载荷）
    r = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  st.dispatch({ type: 'playingList/onAddItemToCurPlayingList',
    payload: { triggerAction: 'nextPlay', triggerScene: 'search',
               trackList: [{ id: '3384055850', name: 'IF Else' }],
               options: { clear: false },
               trackFrom: { fromInfo: {}, scene: 'detail', resourceType: 'track' } } });
  return 'dispatched';
})()
""")
    print(r)
    time.sleep(3.5)

    out = c.evaluate(r"({ calls: window.__callLog, fetches: window.__fetchLog })")
    print("\n==== channel.call 日志 ====")
    for x in (out.get("calls") or []):
        print(f"  {x['m']}  |  {str(x['p'])[:600]}")
    print("\n==== fetch 日志 ====")
    for u in (out.get("fetches") or [])[-20:]:
        print(" ", u)
    c.close()


if __name__ == "__main__":
    sys.exit(main())