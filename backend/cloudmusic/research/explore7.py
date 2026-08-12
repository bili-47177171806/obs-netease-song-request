# -*- coding: utf-8 -*-
"""用受信任的 CDP 右键事件唤起上下文菜单，dump 菜单 DOM 并截屏。
Input 域使用页面 CSS 像素坐标（与 getBoundingClientRect 一致）。
"""
import sys
import time
import base64
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    page = first_page()
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    info = c.evaluate(r"""
(() => {
  const item = document.querySelector('ul.songs li.item');
  if (!item) return null;
  const r = item.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
           text: item.innerText.slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) };
})()
""")
    print("目标行:", info)
    x, y = info["x"], info["y"]

    # 受信任鼠标事件：移动到目标 -> 右键按下 -> 右键抬起
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(0.8)

    menu = c.evaluate(r"""
(() => {
  const hits = [...document.querySelectorAll('*')].filter(e =>
    (e.textContent || '').indexOf('下一首播放') !== -1 && (e.textContent || '').indexOf('下一首播放') !== e.textContent.length);
  // 取包含该文案的最深元素：children 全部都不是包含者
  const deepest = hits.filter(h => ![].some.call(h.children, ch => (ch.textContent||'').indexOf('下一首播放') !== -1));
  return deepest.slice(0, 5).map(h => {
    const r = h.getBoundingClientRect();
    return { text: h.textContent.trim().slice(0, 30), cls: ('' + (h.className || '')).slice(0, 80),
             rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } };
  });
})()
""")
    print("\n菜单命中(下一首播放):", json.dumps(menu, ensure_ascii=False, indent=1))

    # 截屏确认
    shot = c.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    with open("menu_preview.png", "wb") as f:
        f.write(base64.b64decode(shot["result"]["data"]))
    print("\n截图已保存 menu_preview.png")

    c.close()


if __name__ == "__main__":
    sys.exit(main())