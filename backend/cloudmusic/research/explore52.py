# -*- coding: utf-8 -*-
"""本地插入测试：用 addItemToCurPlayingList + options.offset，验证队列变化。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    pre = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  const pl = st.getState()['playingList'] || {};
  const cur = st.getState()['playing'] && st.getState()['playing'].curPlaying;
  const list = pl.curPlayingList || [];
  const curId = cur ? String(cur.id) : null;
  const idx = curId ? list.findIndex(x => String(x.resourceId || x.id) === curId) : -1;
  return { curId, idx, len: list.length,
           around: list.slice(Math.max(0, idx - 1), idx + 4).map(x => x.name || x.id) };
})()
""")
    print("插入前:", json.dumps(pre, ensure_ascii=False, indent=1))

    r = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  const hit = [...document.querySelectorAll('div.tr')].find(e => {
    const t = e.innerText || '';
    return t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('#') === -1;
  });
  if (!hit) return { err: 'no row' };
  const ik = Object.keys(hit).find(k => k.startsWith('__reactInternalInstance$'));
  let f = hit[ik], resource = null;
  for (let i = 0; i < 8 && f; i++) { const mp = f.memoizedProps; if (mp && mp.resource && typeof mp.resource === 'object' && mp.resource.id) { resource = mp.resource; break; } f = f.return; }
  if (!resource) return { err: 'no resource' };

  const pl = st.getState()['playingList'] || {};
  const cur = st.getState()['playing'] && st.getState()['playing'].curPlaying;
  const list = pl.curPlayingList || [];
  const curId = cur ? String(cur.id) : null;
  const idx = curId ? list.findIndex(x => String(x.resourceId || x.id) === curId) : -1;
  if (idx < 0) return { err: 'current not in list', curId };

  const payload = {
    trackList: [resource],
    trackFrom: { scene: 'search', resourceType: 'track', fromInfo: {} },
    options: { clear: false, play: false, playId: undefined, offset: idx },
    triggerScene: 'search',
    triggerAction: 'nextPlay'
  };
  try { st.dispatch({ type: 'playingList/addItemToCurPlayingList', payload }); return { ok: true, idx, songId: resource.id, name: resource.name }; }
  catch (e) { return { err: String(e) }; }
})()
""")
    print("dispatch:", json.dumps(r, ensure_ascii=False, indent=1))
    time.sleep(3.0)

    post = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  const pl = st.getState()['playingList'] || {};
  const cur = st.getState()['playing'] && st.getState()['playing'].curPlaying;
  const list = pl.curPlayingList || [];
  const curId = cur ? String(cur.id) : null;
  const idx = curId ? list.findIndex(x => String(x.resourceId || x.id) === curId) : -1;
  const ts = pl.updateNumber;
  return { len: list.length, curId, idx,
           around: list.slice(Math.max(0, idx - 1), idx + 6).map(x => ({ n: x.name, id: x.resourceId || x.id })),
           updateNumber: ts };
})()
""")
    print("\n插入后 curPlayingList 当前曲附近:", json.dumps(post, ensure_ascii=False, indent=1))
    c.close()


if __name__ == "__main__":
    sys.exit(main())