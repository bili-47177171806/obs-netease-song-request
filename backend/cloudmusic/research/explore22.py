# -*- coding: utf-8 -*-
"""可靠管线版：定位数据行->右键->显菜单->点下一首播放->读抽屉队列。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def read_drawer(c):
    return c.evaluate(r"""
(() => {
  let pane = null;
  document.querySelectorAll('*').forEach(e => {
    const t = e.innerText || '';
    if (!pane && t.indexOf('在列表下方推荐你喜欢的相似歌曲') !== -1 && t.indexOf('播放列表') !== -1) {
      pane = e;
    }
  });
  if (!pane) return null;
  // 取最小包含者（越深层越接近正文）
  let cur = pane;
  for (let i = 0; i < 5; i++) {
    if (cur.children.length === 0) break;
    const kids = [...cur.children].filter(k => (k.innerText || '').indexOf('播放列表') !== -1);
    cur = kids[0] || cur;
  }
  return cur.innerText.split('\n').filter(s => s.trim()).slice(0, 30);
})()
""")


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("抽屉现状(操作前):", read_drawer(c))

    # 1) 精确选第一首数据行
    row = c.evaluate(r"""
(() => {
  const rows = [...document.querySelectorAll('div.tr')];
  const hit = rows.find(e => { const t = e.innerText || '';
    return t.indexOf('IF Else') !== -1 && t.indexOf('mochari') !== -1 && t.indexOf('#') === -1; });
  if (!hit) return null;
  const r = hit.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), txt: hit.innerText.slice(0, 40) };
})()
""")
    print("目标行:", row)
    if not row:
        print("无目标行")
        return
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": row["x"], "y": row["y"], "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": row["x"], "y": row["y"], "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(0.7)

    # 2) 显示菜单 + 点击下一首播放
    r = c.evaluate(r"""
(() => {
  const ul = document.querySelector('#dawn-mock-meau ul');
  const li = document.getElementById('cell_common_right_button_optionnextPlay');
  if (!ul || !li) return null;
  ul.style.position='fixed'; ul.style.left='40px'; ul.style.top='200px'; ul.style.zIndex='999999'; ul.style.display='block';
  const rr = li.getBoundingClientRect();
  return [Math.round(rr.x+rr.width/2), Math.round(rr.y+rr.height/2)];
})()
""")
    print("菜单项列表:", c.evaluate(r"(x=>x?[...x.querySelectorAll('li')].map(x=>x.innerText.trim()).slice(0,8):null)(document.querySelector('#dawn-mock-meau ul'))"))
    print("nextPlay 坐标:", r)
    if r:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": r[0], "y": r[1], "button": "left", "buttons": 1, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": r[0], "y": r[1], "button": "left", "buttons": 0, "clickCount": 1})
    time.sleep(1.5)

    # 3) Toast 扫描
    toast = c.evaluate(r"""
(() => [...document.querySelectorAll('*')].filter(e =>
  !e.childElementCount && /已加入播放|已插入|插播|下一首播放/.test(e.textContent || '') && e.textContent.trim().length < 40)
    .map(e => ({ t: e.textContent.trim(), cls: ('' + (e.className || '')).slice(0, 40),
                 r: (() => { const x = e.getBoundingClientRect(); return [Math.round(x.x), Math.round(x.y)]; })() })))().slice(0, 8)
""")
    print("toast:", toast)

    print("\n抽屉现状(点击后):", read_drawer(c))

    c.close()


if __name__ == "__main__":
    sys.exit(main())