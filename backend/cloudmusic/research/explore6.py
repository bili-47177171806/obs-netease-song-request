# -*- coding: utf-8 -*-
"""验证：DOM 派发右键事件能否唤出「下一首播放」菜单；并 dump MNB 事件注册表与调用源码。"""
import sys
import time
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    print("==== MNB._events（已注册事件）====")
    r = c.evaluate(r"JSON.stringify(Object.keys(window.MNB._events || {}))")
    print(r)

    print("\n==== MNB.register / _postMessage 源码（前 1200 字）====")
    r = c.evaluate(r"window.MNB.register.toString().slice(0,1200)")
    print(r)
    r = c.evaluate(r"window.MNB._postMessage.toString().slice(0,1500)")
    print(r)

    print("\n==== 在第一个歌曲行上派发 contextmenu 并查找菜单 ====")
    r = c.evaluate(r"""
(async () => {
  const item = document.querySelector('ul.songs li.item');
  if (!item) return '没有 li.item';
  const rect = item.getBoundingClientRect();
  const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
  const ev = new MouseEvent('contextmenu', { bubbles: true, cancelable: true,
                                             clientX: x, clientY: y, button: 2, buttons: 2 });
  const ret = item.dispatchEvent(ev);
  await new Promise(r => setTimeout(r, 400));
  const hits = [...document.querySelectorAll('*')].filter(e =>
    !(e.childElementCount) && (e.textContent || '').trim() === '下一首播放');
  const out = [];
  for (const h of hits.slice(0, 3)) {
    const chain = [];
    let p = h;
    for (let i = 0; i < 5 && p; i++) {
      chain.push({ tag: p.tagName, cls: ('' + (p.className || '')).slice(0, 70) });
      p = p.parentElement;
    }
    out.push({ text: h.textContent.trim(), chain });
  }
  return { dispatched: String(ret), x, y, menuHits: out };
})()
""", await_promise=True)
    print(json.dumps(r, ensure_ascii=False, indent=1))

    c.close()


if __name__ == "__main__":
    sys.exit(main())