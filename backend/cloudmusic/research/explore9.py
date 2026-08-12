# -*- coding: utf-8 -*-
"""打印隐藏菜单 UL 的结构：祖先链、菜单项文本与 class，供后续直接触发。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  // 找到那个隐藏的、含『下一首播放』的 UL
  let ul = null;
  document.querySelectorAll('ul').forEach(u => {
    if (!ul && (u.textContent || '').indexOf('下一首播放') !== -1 && getComputedStyle(u).display === 'none') ul = u;
  });
  if (!ul) return 'not found';

  // 祖先链（含属性）
  const chain = [];
  let p = ul;
  for (let i = 0; i < 8 && p; i++) {
    const r = p.getBoundingClientRect();
    chain.push({ tag: p.tagName, cls: ('' + (p.className || '')).slice(0, 80),
                 id: p.id || '', style: ('' + (p.getAttribute('style') || '')).slice(0, 100),
                 display: getComputedStyle(p).display, rect: { x: Math.round(r.x), y: Math.round(r.y) } });
    p = p.parentElement;
  }

  // UL 里所有 LI
  const items = [...ul.querySelectorAll('li')].map(li => ({
    cls: ('' + (li.className || '')).slice(0, 60),
    txt: (li.innerText || '').trim().slice(0, 25),
    atoms: li.querySelectorAll('i, span, em').length
  }));

  // 该 UL 的容器 outerHTML 摘要
  const wrap = ul.parentElement;
  const html = wrap ? wrap.outerHTML.slice(0, 6000) : '';

  return { chain, items, html };
})()
""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:9000])

    c.close()


if __name__ == "__main__":
    sys.exit(main())