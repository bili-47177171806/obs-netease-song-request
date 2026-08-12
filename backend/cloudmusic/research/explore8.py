# -*- coding: utf-8 -*-
"""深挖：右键后所有含『下一首播放』的节点 + 可能的弹出层容器 + 完整 DOM 快照局部。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 再触发一次右键（确保有新鲜菜单状态）
    c.evaluate(r"""
(() => {
  const item = document.querySelector('ul.songs li.item');
  const r = item.getBoundingClientRect();
  window.__x = Math.round(r.left + r.width / 2);
  window.__y = Math.round(r.top + r.height / 2);
  return window.__x + ',' + window.__y;
})()
""")
    x, y = c.evaluate("window.__x"), c.evaluate("window.__y")
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(1.5)

    print("==== 所有含『下一首播放』的节点 ====")
    r = c.evaluate(r"""
(() => {
  const out = [];
  document.querySelectorAll('*').forEach(e => {
    if ((e.textContent || '').indexOf('下一首播放') === -1) return;
    const cs = getComputedStyle(e);
    const rect = e.getBoundingClientRect();
    out.push({
      cls: ('' + (e.className || '')).slice(0, 60),
      display: cs.display, visibility: cs.visibility, position: cs.position,
      rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
      kind: e.tagName
    });
  });
  return out.slice(0, 15);
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    print("\n==== class 含 menu/pop/context 且定位/可见的容器 ====")
    r = c.evaluate(r"""
(() => {
  const out = [];
  document.querySelectorAll('*').forEach(e => {
    const cls = ('' + (e.className || ''));
    if (!/menu|pop|context|dropdown|overlay/i.test(cls)) return;
    const cs = getComputedStyle(e);
    const rect = e.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return;
    out.push({ cls: cls.slice(0, 80), display: cs.display, pos: cs.position,
               rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
               txt: e.innerText.slice(0, 60) });
  });
  return out.slice(0, 15);
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1))

    # 保存整页 JS 视图快照，供后续定位
    c.evaluate(r"window.__snap = document.body.innerHTML.slice(0, 400000)")
    print("\n已存 body innerHTML 快照（window.__snap）")

    c.close()


if __name__ == "__main__":
    sys.exit(main())