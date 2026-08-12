# -*- coding: utf-8 -*-
"""最终验证：抽屉里 IF Else 紧跟当前曲，且同步到原生。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 打开播放列表抽屉
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
  return { header: lines.slice(0, 6), hasIfElse: lines.includes('IF Else'), idxIfElse: lines.indexOf('IF Else'),
           context: lines.slice(Math.max(0, lines.indexOf('IF Else') - 8), lines.indexOf('IF Else') + 6) };
})()
""")
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
    c.close()


if __name__ == "__main__":
    sys.exit(main())