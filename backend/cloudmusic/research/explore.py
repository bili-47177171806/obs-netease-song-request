# -*- coding: utf-8 -*-
"""探查网易云客户端当前页面：标题 / 可见文本 / 带 data-id 的行节点结构。"""
import sys
from backend.cloudmusic.cdp import CDP, first_page


def main():
    page = first_page()
    print("target url:", page.get("url"))
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    info = c.evaluate(r"""
(() => {
  const rows = [...document.querySelectorAll('[data-id]')].slice(0, 25)
    .map(e => ({ tag: e.tagName,
                 cls: ('' + (e.className || '')).slice(0, 70),
                 id: e.getAttribute('data-id'),
                 txt: (e.innerText || '').split('\n')[0].slice(0, 40) }));
  return { title: document.title,
           url: location.href,
           bodyText: (document.body && document.body.innerText || '').slice(0, 1500),
           dataIdRows: rows };
})()
""")
    c.close()
    if isinstance(info, dict) and "error" in info:
        print("JS ERROR:", info["error"])
        return
    print("TITLE:", info["title"])
    print("URL:", info["url"])
    print("---- body innerText (前1500字) ----")
    print(info["bodyText"])
    print("---- 带 data-id 的元素 (前25) ----")
    for row in info["dataIdRows"]:
        print(row)


if __name__ == "__main__":
    sys.exit(main())