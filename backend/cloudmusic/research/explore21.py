# -*- coding: utf-8 -*-
"""最终判定：右键设置上下文 -> 手动显示菜单 -> 受信任点击下一首播放 -> 读队列顶部。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 0) 关闭可能开着的抽屉：按一次 Esc
    c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27})
    c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27})
    time.sleep(0.4)

    # 1) 右键第一行歌曲
    row = c.evaluate("""(() => { const e=document.querySelector('div.tr'); if(!e) return null;
        const r=e.getBoundingClientRect(); return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), txt:e.innerText.slice(0,30)}; })()""")
    print("行:", row)
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": row["x"], "y": row["y"], "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": row["x"], "y": row["y"], "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(0.6)

    # 2) 确认菜单项内容（判断上下文是否为单曲）
    items = c.evaluate(r"""(x => x ? [...x.querySelectorAll('li')].map(x=>x.innerText.trim()).slice(0,10) : null)
        (document.querySelector('#dawn-mock-meau ul'))""")
    print("菜单项:", items)

    # 3) 手动显示菜单
    r = c.evaluate(r"""
(() => {
  const ul = document.querySelector('#dawn-mock-meau ul');
  if (!ul) return 'no ul';
  ul.style.position='fixed'; ul.style.left='40px'; ul.style.top='200px'; ul.style.zIndex='999999'; ul.style.display='block';
  const li = document.getElementById('cell_common_right_button_optionnextPlay');
  const rr = li.getBoundingClientRect();
  return [Math.round(rr.x+rr.width/2), Math.round(rr.y+rr.height/2)];
})()
""")
    print("下一首播放 li 坐标:", r)
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": r[0], "y": r[1], "button": "left", "buttons": 1, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": r[0], "y": r[1], "button": "left", "buttons": 0, "clickCount": 1})
    time.sleep(1.5)

    # 4) 打开播放列表抽屉（底部 playlist 图标）
    tgt = c.evaluate(r"""
(() => {
  const e = document.querySelector('[class*=cmd-icon-playlist]');
  if (!e) return null;
  const r = e.getBoundingClientRect();
  if (r.height === 0) return null;
  return { x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2) };
})()
""")
    print("队列按钮:", tgt)
    if tgt:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": tgt["x"], "y": tgt["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": tgt["x"], "y": tgt["y"], "button": "left", "buttons": 1, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tgt["x"], "y": tgt["y"], "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(1.0)

    # 5) 读播放列表抽屉顶部
    r2 = c.evaluate(r"""
(() => {
  const els = [...document.querySelectorAll('*')].filter(e => {
    const t = e.innerText || '';
    return /播放列表/.test(t) && /收藏全部/.test(t);
  });
  const panel = els.sort((a,b)=>b.offsetHeight-a.offsetHeight)[0];
  if (!panel) return 'no drawer';
  const lines = panel.innerText.split('\n').filter(s => s.trim());
  return lines.slice(0, 25);
})()
""")
    print("\n==== 播放列表抽屉顶部 ====")
    for ln in (r2 if isinstance(r2, list) else [r2]):
        print(ln)

    c.close()


if __name__ == "__main__":
    sys.exit(main())