# -*- coding: utf-8 -*-
"""完整闭环验证：驱动搜索框搜歌 -> 结果行右键 -> dump 单曲菜单 -> 找『下一首播放』。
"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 1) 找搜索输入框
    r = c.evaluate(r"""
(() => {
  const inputs = [...document.querySelectorAll('input')].map(i => ({
    ph: i.placeholder || '', type: i.type, cls: ('' + (i.className || '')).slice(0, 50),
    vis: getComputedStyle(i).display !== 'none' }));
  const candidates = inputs.filter(i => /搜索|search/i.test(i.ph) || /search/i.test(i.cls));
  return { all: inputs.slice(0, 8), candidates: candidates.slice(0, 5) };
})()
""")
    print("输入框:", json.dumps(r, ensure_ascii=False, indent=1)[:1500])

    # 聚焦候选框并输入
    typed = c.evaluate(r"""
(async () => {
  const inp = [...document.querySelectorAll('input')].find(i => /搜索|search/i.test(i.placeholder || '') || /search/i.test(i.className || ''));
  if (!inp) return 'no input';
  inp.focus();
  return 'focused: ' + (inp.placeholder || inp.className);
})()
""")
    print("\n聚焦:", typed)
    c.call("Input.insertText", {"text": "IF Else"})
    time.sleep(1.2)
    c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    time.sleep(2.5)

    # 2) dump 当前可见文本 + 找歌曲行
    r = c.evaluate(r"""
(() => {
  const rows = [...document.querySelectorAll('ul.songs li.item, li.item')].slice(0, 10)
    .map(e => ({ txt: e.innerText.slice(0, 60), rect: (() => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })() }));
  return { text: document.body.innerText.slice(0, 800), rows };
})()
""")
    print("\n搜索后页面:", json.dumps(r, ensure_ascii=False, indent=1)[:2500])

    # 3) 右键第一行（若存在）
    first = c.evaluate(r"""
(() => {
  const e = document.querySelector('li.item');
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
})()
""")
    if first:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": first["x"], "y": first["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": first["x"], "y": first["y"], "button": "right", "buttons": 2, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": first["x"], "y": first["y"], "button": "right", "buttons": 0, "clickCount": 1})
        time.sleep(1.0)

    # 4) dump 所有隐藏/可见菜单 UL
    r = c.evaluate(r"""
(() => {
  const out = [];
  document.querySelectorAll('ul').forEach(u => {
    const st = getComputedStyle(u);
    const li = [...u.querySelectorAll('li')].map(x => x.innerText.trim()).filter(Boolean).slice(0, 12);
    if (!li.length) return;
    out.push({ ulCls: ('' + (u.className || '')).slice(0, 40), ulStyle: ('' + (u.getAttribute('style') || '')).slice(0, 60),
               display: st.display, position: st.position, items: li,
               parentId: u.parentElement ? u.parentElement.id : '' });
  });
  return out;
})()
""")
    print("\n所有菜单 UL:", json.dumps(r, ensure_ascii=False, indent=1)[:4000])

    c.close()


if __name__ == "__main__":
    sys.exit(main())