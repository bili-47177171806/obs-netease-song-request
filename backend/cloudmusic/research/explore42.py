# -*- coding: utf-8 -*-
"""决定性测试：通过 store.dispatch 触发『下一首播放』，验证队列插入。"""
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
  if (!st) return 'no store';
  const h = st.getState()['async:playingListHandoff'] || {};
  const pl = st.getState()['playingList'] || {};
  return { playingSource: h.playingSource, shouldUpload: h.shouldUpload,
           currentPlayingItemId: h.playingState && h.playingState.currentPlayingItem && h.playingState.currentPlayingItem.id,
           commands: (h.playingCommands || []).length,
           curPlayingListLen: (pl.curPlayingList || []).length,
           firstOfList: (pl.curPlayingList || [])[0] && (pl.curPlayingList[0].name || pl.curPlayingList[0].id) };
})()
""")
    print("分发前状态:", json.dumps(pre, ensure_ascii=False, indent=1))

    r = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  const hit = [...document.querySelectorAll('div.tr')].find(e => {
    const t = e.innerText || '';
    return t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('#') === -1;
  });
  if (!hit) return 'no row';
  const ik = Object.keys(hit).find(k => k.startsWith('__reactInternalInstance$'));
  let f = hit[ik], resource = null;
  for (let i = 0; i < 8 && f; i++) {
    const mp = f.memoizedProps;
    if (mp && mp.resource && typeof mp.resource === 'object' && mp.resource.id) { resource = mp.resource; break; }
    f = f.return;
  }
  if (!resource) return 'no resource';
  const payload = {
    triggerAction: 'nextPlay',
    triggerScene: 'search',
    trackList: [resource],
    options: { clear: false, playId: undefined, play: false },
    trackFrom: { fromInfo: {}, scene: 'detail', resourceType: 'track' }
  };
  try {
    st.dispatch({ type: 'playingList/onAddItemToCurPlayingList', payload });
    return { dispatched: true, songId: resource.id, name: resource.name };
  } catch (e) {
    return { dispatched: false, err: String(e), songId: resource.id };
  }
})()
""")
    print("dispatch:", json.dumps(r, ensure_ascii=False, indent=1))
    time.sleep(3.0)

    post = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  const h = st.getState()['async:playingListHandoff'] || {};
  const pl = st.getState()['playingList'] || {};
  return { commands: (h.playingCommands || []),
           curPlayingListTop: (pl.curPlayingList || []).slice(0, 3).map(x => x.name || x.id) };
})()
""")
    print("\n分发后 handoff.commands:", json.dumps(post.get("commands", []), ensure_ascii=False, indent=1)[:1200])
    print("curPlayingList 顶部:", json.dumps(post.get("curPlayingListTop"), ensure_ascii=False))

    c.close()


if __name__ == "__main__":
    sys.exit(main())