# -*- coding: utf-8 -*-
"""验证命令是否上传成功：读 handoff.commands 余额 + 队列抽屉里有无 IF Else。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  if (!st) return 'no store';
  const h = st.getState()['async:playingListHandoff'] || {};
  const pl = st.getState()['playingList'] || {};

  // 找含 IF Else 且长度合适的叶子文本
  const leaves = [...document.querySelectorAll('*')].filter(e =>
    !e.childElementCount && (e.textContent || '').trim() === 'IF Else' && e.getBoundingClientRect().width > 0);
  return { commandsLeft: (h.playingCommands || []).length,
           commands: (h.playingCommands || []).slice(0, 5),
           curPlayingListLen: (pl.curPlayingList || []).length,
           ifElseVisibleLeaves: leaves.length };
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])

    # 打开抽屉读
    tgt = c.evaluate(r"""
(() => {
  const e = document.querySelector('[class*=cmd-icon-playlist]');
  if (!e) return null;
  const r = e.getBoundingClientRect();
  if (r.height === 0 || r.width === 0) return null;
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
})()
""")
    if tgt:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": tgt["x"], "y": tgt["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": tgt["x"], "y": tgt["y"], "button": "left", "buttons": 1, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tgt["x"], "y": tgt["y"], "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(1.2)

    d = c.evaluate(r"""
(() => {
  let pane = null;
  document.querySelectorAll('*').forEach(e => {
    const t = e.innerText || '';
    if (!pane && t.indexOf('在列表下方推荐你喜欢的相似歌曲') !== -1 && t.indexOf('播放列表') !== -1) pane = e;
  });
  if (!pane) return 'no drawer';
  let cur = pane;
  for (let i = 0; i < 5; i++) {
    if (cur.children.length === 0) break;
    cur = [...cur.children].find(k => (k.innerText || '').indexOf('播放列表') !== -1) || cur;
  }
  const lines = cur.innerText.split('\n').filter(s => s.trim());
  return { lines: lines.slice(0, 12), hasIfElse: lines.includes('IF Else') };
})()
""")
    print("\n抽屉:", json.dumps(d, ensure_ascii=False, indent=1)[:1500])
    c.close()


if __name__ == "__main__":
    sys.exit(main())