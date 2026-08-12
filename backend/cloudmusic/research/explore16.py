# -*- coding: utf-8 -*-
"""打开播放队列面板，dump 队列内容，确认『IF Else』是否已插入。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 底部栏找按钮/图标，候选：queue/list/order/播放队列
    r = c.evaluate(r"""
(() => {
  const h = window.innerHeight;
  const cands = [];
  document.querySelectorAll('[role=button], button, [class*=queue], [class*=list], [class*=order]').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.top < h - 130 || r.height === 0 || r.width === 0) return;
    cands.push({ cls: ('' + (e.className || '')).slice(0, 50), tag: e.tagName,
                 title: e.getAttribute('title') || '', aria: e.getAttribute('aria-label') || '',
                 txt: (e.innerText || '').slice(0, 20),
                 rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] });
  });
  return { height: h, cands: cands.slice(0, 30) };
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:3000])

    # 尝试点击最像队列按钮的（class 含 queue 且在底部）
    tgt = c.evaluate(r"""
(() => {
  const h = window.innerHeight;
  const all = [...document.querySelectorAll('[role=button], button, [class*=queue], [class*=list], [class*=order]')];
  let best = null;
  all.forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.top < h - 130 || r.height === 0 || r.width === 0) return;
    const cls = ('' + (e.className || ''));
    const score = (cls.indexOf('queue') !== -1 ? 10 : 0) + (cls.indexOf('list') !== -1 ? 3 : 0) + (cls.indexOf('order') !== -1 ? 3 : 0);
    if (score && (!best || score > best.score)) best = { score, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2), cls: cls.slice(0, 50) };
  });
  return best;
})()
""")
    print("\n候选队列按钮:", tgt)
    if tgt:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": tgt["x"], "y": tgt["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": tgt["x"], "y": tgt["y"], "button": "left", "buttons": 1, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tgt["x"], "y": tgt["y"], "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(1.5)

    # dump 可能的播放队列面板内容
    r2 = c.evaluate(r"""
(() => {
  const out = { text: '' };
  // 找含『IF Else』且看起来是列表容器的节点（排除隐藏菜单）
  const body = document.body.innerText;
  out.text = body.slice(-700);
  return out;
})()
""")
    print("\n==== 底部区域文本 ====")
    print(r2["text"])

    c.close()


if __name__ == "__main__":
    sys.exit(main())