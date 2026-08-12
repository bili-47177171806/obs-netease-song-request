# -*- coding: utf-8 -*-
"""定位单曲结果行 -> 右键 -> 抓单曲菜单。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 找到同时含 IF Else / mochari / 03:36 的最小行容器
    r = c.evaluate(r"""
(() => {
  let row = null;
  document.querySelectorAll('*').forEach(e => {
    const t = e.innerText || '';
    if (t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('03:36') !== -1) {
      const r = e.getBoundingClientRect();
      if (r.width > 100 && r.height > 20 && (row === null || r.height < row.getBoundingClientRect().height)) row = e;
    }
  });
  if (!row) return null;
  const r = row.getBoundingClientRect();
  return { cls: ('' + (row.className || '')).slice(0, 70), tag: row.tagName,
           x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
           w: Math.round(r.width), h: Math.round(r.height),
           chain: (() => { const a = []; let p = row; for (let i = 0; i < 5 && p; i++) { a.push(p.tagName + '.' + ('' + (p.className || '')).slice(0, 40)); p = p.parentElement; } return a; })() };
})()
""")
    print("歌曲行:", json.dumps(r, ensure_ascii=False, indent=1))
    if not r or "x" not in r:
        print("找不到行，中止")
        return

    # 右键
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"], "y": r["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": r["x"], "y": r["y"], "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": r["x"], "y": r["y"], "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(1.2)

    print("\n==== 右键后所有菜单 UL ====")
    r2 = c.evaluate(r"""
(() => {
  const out = [];
  document.querySelectorAll('ul').forEach(u => {
    const st = getComputedStyle(u);
    const li = [...u.querySelectorAll('li')].map(x => x.innerText.trim()).filter(Boolean).slice(0, 16);
    if (!li.length) return;
    out.push({ display: st.display, position: st.position,
               parentId: u.parentElement ? u.parentElement.id : '',
               parentCls: ('' + (u.parentElement ? u.parentElement.className : '')).slice(0, 70),
               ulCls: ('' + (u.className || '')).slice(0, 40),
               style: ('' + (u.getAttribute('style') || '')).slice(0, 80),
               items: li });
  });
  return out;
})()
""")
    print(json.dumps(r2, ensure_ascii=False, indent=1)[:5000])

    # 若找到『下一首播放』的 li，dump 它的信息
    print("\n==== 『下一首播放』li 详情 ====")
    r3 = c.evaluate(r"""
(() => {
  const lis = [...document.querySelectorAll('li')].filter(x => (x.innerText || '').trim() === '下一首播放');
  return lis.map(li => {
    const r = li.getBoundingClientRect();
    return { id: li.id, cls: ('' + (li.className || '')).slice(0, 60),
             rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
             display: getComputedStyle(li).display,
             parentStyle: ('' + (li.parentElement.getAttribute('style') || '')).slice(0, 60) };
  });
})()
""")
    print(json.dumps(r3, ensure_ascii=False, indent=1))

    c.close()


if __name__ == "__main__":
    sys.exit(main())