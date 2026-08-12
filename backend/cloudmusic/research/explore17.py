# -*- coding: utf-8 -*-
"""验证『IF Else』在播放队列中的位置。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    # 1) 全文找 IF Else 出现的上下文
    r = c.evaluate(r"""
(() => {
  const body = document.body.innerText;
  const idxs = [];
  let i = -1;
  while ((i = body.indexOf('IF Else', i + 1)) !== -1) idxs.push(i);
  return { total: body.length, idxs: idxs.slice(0, 20) };
})()
""")
    print("『IF Else』出现位置:", r)

    # 2) 找播放队列面板容器
    r2 = c.evaluate(r"""
(() => {
  // 找含『播放队列』或当前播放歌名的可见面板
  let panel = null;
  document.querySelectorAll('*').forEach(e => {
    const cls = ('' + (e.className || ''));
    const rect = e.getBoundingClientRect();
    if (rect.width < 150 || rect.height < 200) return;
    const t = e.innerText || '';
    if (!panel && /播放队列|正在播放|队列/i.test(t) && /君の神様|酔いどれ/.test(t)) {
      if (/queue|playlist|panel|drawer|pop/i.test(cls)) panel = e;
    }
  });
  if (!panel) return { found: false };
  const lines = panel.innerText.split('\n').filter(s => s.trim());
  return { found: true, cls: ('' + (panel.className || '')).slice(0, 60), lines: lines.slice(0, 40) };
})()
""")
    print(json.dumps(r2, ensure_ascii=False, indent=1)[:3000])

    # 3) 底部栏当前歌曲/状态
    r3 = c.evaluate(r"""
(() => {
  const els = [...document.querySelectorAll('*')].filter(e =>
    !e.childElementCount && /酔いどれ知らず|IF Else/.test(e.textContent || '') && e.textContent.trim().length < 60);
  return els.map(e => ({ txt: e.textContent.trim(), rect: (() => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)]; })() })).slice(0, 15);
})()
""")
    print("\n含歌名的叶子节点:", json.dumps(r3, ensure_ascii=False, indent=1))

    c.close()


if __name__ == "__main__":
    sys.exit(main())