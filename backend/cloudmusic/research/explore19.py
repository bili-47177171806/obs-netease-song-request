# -*- coding: utf-8 -*-
"""拿到『下一首播放』li 的 React fiber，dump onClick 闭包与菜单组件 props；尝试直接调用。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 右键第一行设置上下文
    row = c.evaluate("""(() => { const e=document.querySelector('div.tr'); if(!e) return null;
        const r=e.getBoundingClientRect(); return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })()""")
    if not row:
        print("无 div.tr")
        return
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": row["x"], "y": row["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": row["x"], "y": row["y"], "button": "right", "buttons": 2, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": row["x"], "y": row["y"], "button": "right", "buttons": 0, "clickCount": 1})
    time.sleep(0.7)

    info = c.evaluate(r"""
(() => {
  const li = document.getElementById('cell_common_right_button_optionnextPlay');
  if (!li) return { err: 'no li' };
  const own = Object.keys(li).filter(k => k.startsWith('__react'));
  const getFiber = () => { const k = Object.keys(li).find(k => k.startsWith('__reactFiber$')); return k ? li[k] : null; };
  const fiber = getFiber();
  const mp = fiber ? fiber.memoizedProps : null;
  const out = { ownKeys: own };
  // 找最近有 song 数据的祖先组件 props
  let chain = [];
  let f = fiber;
  const songData = [];
  for (let i = 0; i < 12 && f; i++) {
    const p = f.memoizedProps || {};
    const t = Object.keys(p).filter(k => k && typeof p[k] !== 'object' && !k.startsWith('on'));
    const hasSong = JSON.stringify(p).slice(0, 300);
    const hit = {};
    if (p.song || p.data && p.data.id) hit.songId = (p.song ? p.song.id : p.data.id);
    if (p.song) hit.songName = p.song.name;
    if (Object.keys(hit).length) songData.push({ depth: i, ...hit });
    chain.push({ depth: i, tag: (f.type && f.type.name) || String(f.elementType || f.type || '').slice(0, 40), keys: t.slice(0, 12) });
    f = f.return;
  }
  out.chain = chain;
  out.songData = songData;
  // onClick 源码
  out.onClickSrc = mp && mp.onClick ? mp.onClick.toString().slice(0, 800) : null;
  out.nextPlayLiClick = li.onclick ? li.onclick.toString().slice(0, 300) : null;
  return out;
})()
""")
    print(json.dumps(info, ensure_ascii=False, indent=1)[:5000])

    c.close()


if __name__ == "__main__":
    sys.exit(main())