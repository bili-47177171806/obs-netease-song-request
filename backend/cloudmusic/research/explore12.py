# -*- coding: utf-8 -*-
"""修正版：input[type=search] 定位 -> 输入歌名 -> Enter -> 结果页右键 -> dump 菜单。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const inp = document.querySelector('input[type=search]');
  if (!inp) return 'no search input';
  const r = inp.getBoundingClientRect();
  inp.focus();
  return { found: true, ph: inp.placeholder, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2) };
})()
""")
    print("搜索框:", r)
    if not isinstance(r, dict) or not r.get("found"):
        return
    c.call("Input.insertText", {"text": "IF Else"})
    time.sleep(1.5)
    c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    time.sleep(3.0)

    print("\n==== 搜索后页面（前 700 字）====")
    r = c.evaluate(r"document.body.innerText.slice(0, 700)")
    print(r)

    # 找所有带 data-id 或可点击的行（搜索结果里的歌曲行一般有 id）
    r = c.evaluate(r"""
(() => {
  const out = { rows: [], dataRows: [] };
  document.querySelectorAll('li.item, [data-song], [data-id]').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    out.rows.push({ tag: e.tagName, cls: ('' + (e.className || '')).slice(0, 50),
                    id: e.getAttribute('data-id') || '', txt: e.innerText.slice(0, 40).split('\n').slice(0,2).join(' | '),
                    rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] });
  });
  return out;
})()
""")
    print("\n可点击行:", json.dumps(r, ensure_ascii=False, indent=1)[:2500])

    # 右键第一个搜索结果行
    target = c.evaluate(r"""
(() => {
  const e = document.querySelector('li.item');
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return { x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2), txt: e.innerText.slice(0, 40) };
})()
""")
    print("\n右键目标:", target)
    if target:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": target["x"], "y": target["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": target["x"], "y": target["y"], "button": "right", "buttons": 2, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": target["x"], "y": target["y"], "button": "right", "buttons": 0, "clickCount": 1})
        time.sleep(1.2)

    print("\n==== 右键后所有菜单 UL ====")
    r = c.evaluate(r"""
(() => {
  const out = [];
  document.querySelectorAll('ul').forEach(u => {
    const st = getComputedStyle(u);
    const li = [...u.querySelectorAll('li')].map(x => x.innerText.trim()).filter(Boolean).slice(0, 14);
    if (!li.length) return;
    out.push({ ulStyle: ('' + (u.getAttribute('style') || '')).slice(0, 60), display: st.display,
               position: st.position, parentId: u.parentElement ? u.parentElement.id : '',
               parentCls: ('' + (u.parentElement ? u.parentElement.className : '')).slice(0, 60),
               items: li });
  });
  return out;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4500])

    c.close()


if __name__ == "__main__":
    sys.exit(main())