# -*- coding: utf-8 -*-
"""切到搜索『单曲』标签，抓结果行结构并右键验证菜单。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 1) 找『单曲』标签并点击
    r = c.evaluate(r"""
(() => {
  const hits = [...document.querySelectorAll('*')].filter(e =>
    e.children.length === 0 && (e.textContent || '').trim() === '单曲');
  if (!hits.length) return 'no tab';
  const h = hits[0];
  const r = h.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
           txt: h.parentElement ? ('' + (h.parentElement.className || '')).slice(0, 60) : '' };
})()
""")
    print("单曲标签:", r)
    if isinstance(r, dict) and "x" in r:
        c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"], "y": r["y"]})
        c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": r["x"], "y": r["y"], "button": "left", "buttons": 1, "clickCount": 1})
        c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": r["x"], "y": r["y"], "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(2.0)

    print("\n==== 单曲页文本（前 600）====")
    r = c.evaluate(r"document.body.innerText.slice(0, 600)")
    print(r)

    print("\n==== 歌曲行结构 ====")
    r = c.evaluate(r"""
(() => {
  // 找含具体歌曲名的叶子节点，向上找行容器
  const out = [];
  ['IF Else', 'Neko Hacker', 'mochari'].forEach(kw => {
    const tn = [...document.querySelectorAll('*')].find(e => e.children.length === 0 && (e.textContent || '').trim() === kw);
    if (!tn) { out.push({ kw, hit: false }); return; }
    const chain = [];
    let p = tn;
    for (let i = 0; i < 7 && p; i++) {
      const r = p.getBoundingClientRect();
      chain.push({ tag: p.tagName, cls: ('' + (p.className || '')).slice(0, 60),
                   rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                   txt: (p.innerText || '').slice(0, 20) });
      p = p.parentElement;
    }
    out.push({ kw, hit: true, chain });
  });
  return out;
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])

    c.close()


if __name__ == "__main__":
    sys.exit(main())