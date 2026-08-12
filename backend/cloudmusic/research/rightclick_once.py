# -*- coding: utf-8 -*-
"""对搜索页第一行执行一次右键（配合 window_list.ps1 前后对比）。"""
import sys
import time
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    row = c.evaluate(r"""(() => { const rows=[...document.querySelectorAll('div.tr')];
        const h=rows.find(e=>{const t=e.innerText||''; return t.indexOf('IF Else')!==-1 && t.indexOf('mochari')!==-1 && t.indexOf('#')===-1;});
        if(!h) return null; const r=h.getBoundingClientRect(); return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })()""")
    print("row:", row)
    if row:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": row["x"], "y": row["y"], "button": "right", "buttons": 2, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": row["x"], "y": row["y"], "button": "right", "buttons": 0, "clickCount": 1})
        print("right-clicked; menu should be up for ~2s")
        time.sleep(2.0)
    c.close()


if __name__ == "__main__":
    sys.exit(main())