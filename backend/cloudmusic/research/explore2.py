# -*- coding: utf-8 -*-
"""第二次探查：class 布局 / 歌曲行的元素层级 / window 全局里可能的 API。"""
import sys
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== 出现最多的 class（前 45 个）====")
    r = c.evaluate(r"""
(() => {
  const m = {};
  document.querySelectorAll('*').forEach(e => {
    const c = ('' + (e.className || '')).trimgroed = 0; // noop
    const cc = ('' + (e.className || '')).split(/\s+/).filter(Boolean);
    cc.forEach(x => m[x] = (m[x] || 0) + 1);
  });
  return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,45);
})()
""")
    for k, v in r:
        print(f"{v:5d}  {k}")

    print("\n==== 歌曲「IF Else」所在元素的祖先链 ====")
    r = c.evaluate(r"""
(() => {
  const hit = [...document.querySelectorAll('*')].find(e =>
    e.children.length === 0 && (e.textContent || '').trim() === 'IF Else');
  if (!hit) return '未找到 IF Else';
  const out = [];
  let p = hit;
  for (let i = 0; i < 8 && p; i++) {
    out.push({ i, tag: p.tagName, cls: ('' + (p.className || '')).slice(0, 90),
               id: p.id || '', txt: (p.innerText || '').slice(0, 25) });
    p = p.parentElement;
  }
  return out;
})()
""")
    for row in r:
        print(row)

    print("\n==== window 上疑似 API 的全局名 ====")
    r = c.evaluate(r"""
(() => Object.keys(window).filter(k => /netease|music|orpheus|player|api|app$/i.test(k)).slice(0, 60))()
""")
    print(r)

    c.close()


if __name__ == "__main__":
    sys.exit(main())