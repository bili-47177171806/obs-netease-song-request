# -*- coding: utf-8 -*-
"""判定菜单是原生还是 DOM：MutationObserver 观察右键瞬间；并尝试手动显示+受信任点击，读队列变化。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 1) 注入观察者
    c.evaluate(r"""
window.__mutLog = [];
try {
  const mo = new MutationObserver(muts => {
    for (const m of muts) {
      window.__mutLog.push({
        type: m.type,
        targetId: m.target.id || m.target.className ? ('' + (m.target.tagName || '') + '.' + ('' + (m.target.className || '')).slice(0, 30)) : (m.target.tagName || ''),
        added: m.addedNodes.length,
        attr: m.attributeName,
        toStr: ('' + (m.target.getAttribute && m.target.getAttribute('style') || '')).slice(0, 50)
      });
    }
  });
  mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class', 'hidden'] });
} catch (e) { window.__mutLog.push({ err: String(e) }); }
""")

    # 2) 右键第一行
    row = c.evaluate("""(() => { const e=document.querySelector('div.tr'); if(!e) return null;
        const r=e.getBoundingClientRect(); return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })()""")
    print("右键:", row)
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": row["x"], "y": row["y"], "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": row["x"], "y": row["y"], "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(1.2)

    print("\n==== 右键瞬间的 DOM 变化（前 40 条）==== ")
    log = c.evaluate("window.__mutLog")
    for m in log[:40]:
        print(m)

    # 3) 手动把菜单 ul 显示出来，再看 ul 的 rect 与菜单项位置
    r = c.evaluate(r"""
(() => {
  const ul = document.querySelector('#dawn-mock-meau ul');
  if (!ul) return 'no ul';
  ul.style.position = 'fixed';
  ul.style.left = '300px';
  ul.style.top = '300px';
  ul.style.zIndex = '99999';
  ul.style.display = 'block';
  const li = document.getElementById('cell_common_right_button_optionnextPlay');
  const rr = li.getBoundingClientRect();
  return { liRect: [Math.round(rr.x), Math.round(rr.y), Math.round(rr.width), Math.round(rr.height)],
           ulDisplay: getComputedStyle(ul).display };
})()
""")
    print("\n手动显示菜单:", r)

    c.close()


if __name__ == "__main__":
    sys.exit(main())