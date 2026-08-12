# -*- coding: utf-8 -*-
"""验证核心动作：右键行设置上下文 -> 直接 click 隐藏的『下一首播放』li -> 观察队列变化。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 记录点击前队列相关 localStorage
    before = c.evaluate(r"""
(() => {
  const g = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  return { playingListSheet: (g('playingListSheet') || '').slice(0, 400),
           lastPlaying: (g('lastPlaying') || '').slice(0, 400) };
})()
""")

    # 1) 右键第一首歌曲行，设置右键上下文
    row = c.evaluate(r"""
(() => {
  const e = document.querySelector('div.tr');
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
})()
""")
    if not row:
        print("没有歌曲行，中止")
        return
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": row["x"], "y": row["y"], "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": row["x"], "y": row["y"], "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(0.8)

    # 2) 确认菜单内容已刷新为单曲菜单
    menu_now = c.evaluate(r"""
(() => {
  const u = document.querySelector('#dawn-mock-meau ul');
  return u ? [...u.querySelectorAll('li')].map(x => x.innerText.trim()).slice(0, 10) : null;
})()
""")
    print("点击前菜单项:", menu_now)

    # 3) 直接 click 下一首播放
    r = c.evaluate(r"""
(() => {
  const li = document.getElementById('cell_common_right_button_optionnextPlay');
  if (!li) return 'no li';
  li.click();
  return 'clicked';
})()
""")
    print("click 结果:", r)
    time.sleep(2.0)

    # 4) 观察变化
    after = c.evaluate(r"""
(() => {
  const g = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const body = document.body.innerText;
  const toast = [...document.querySelectorAll('*')].filter(e =>
    !e.childElementCount && /已加入|播放队列|下一首|已添加/i.test((e.textContent || ''))).map(e => e.textContent.trim()).slice(0, 5);
  return { bodyTail: body.slice(-500),
           playingListSheet: (g('playingListSheet') || '').slice(0, 600),
           lastPlaying: (g('lastPlaying') || '').slice(0, 400),
           toast };
})()
""")
    print("\n==== 点击后观察 ====")
    print(json.dumps(after, ensure_ascii=False, indent=1)[:2500])
    print("\n==== 点击前对比 ====")
    print(json.dumps(before, ensure_ascii=False, indent=1)[:900])

    c.close()


if __name__ == "__main__":
    sys.exit(main())