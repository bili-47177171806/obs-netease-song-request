# -*- coding: utf-8 -*-
"""把指定 action 名在 bundle 里的上下文源码切出来，用于确认载荷字段。

    python -m backend.cloudmusic.research.explore55 [--before N] [--after N] [名字 ...]

默认查删除 / 跳歌 / 清空三个 action。注意 `on` 前缀的多半是**空生成器通知钩子**
（`*onRemoveItemFromCurPlayingListByIds(){}`），真正干活的 saga 在它上游——
用 `--before 3000` 往前挖调用它的那个函数名。
"""
import json
import sys

from backend.cloudmusic.cdp import CDP, first_page
from backend.cloudmusic.research.explore54 import _js_urls

DEFAULT_NAMES = [
    "onRemoveItemFromCurPlayingListByIds",
    "jump2Track",
    "clearCurPlayingList",
]

EXPR = r"""
(async () => {
  const urls = %s, names = %s, before = %d, after = %d;
  const out = [];
  for (const u of urls) {
    let text;
    try { text = await (await fetch(u)).text(); } catch (e) { continue; }
    for (const name of names) {
      let from = 0;
      while (true) {
        const i = text.indexOf(name, from);
        if (i < 0) break;
        from = i + name.length;
        out.push({
          name,
          url: u.split('/').pop(),
          at: i,
          code: text.slice(Math.max(0, i - before), i + after),
        });
        if (out.length > 60) return out;
      }
    }
  }
  return out;
})()
"""


def main():
    argv = sys.argv[1:]
    before, after = 120, 900
    names = []
    while argv:
        arg = argv.pop(0)
        if arg == "--before":
            before = int(argv.pop(0))
        elif arg == "--after":
            after = int(argv.pop(0))
        else:
            names.append(arg)
    names = names or DEFAULT_NAMES

    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    urls = _js_urls(c)
    raw = c.call("Runtime.evaluate", {
        "expression": EXPR % (json.dumps(urls), json.dumps(names), before, after),
        "returnByValue": True,
        "awaitPromise": True,
    })
    res = raw.get("result", {})
    if "exceptionDetails" in res:
        print(json.dumps({"err": str(res["exceptionDetails"])[:400]}, ensure_ascii=False))
        return
    hits = res.get("result", {}).get("value") or []
    print(f"命中 {len(hits)} 处\n")
    for hit in hits:
        print(f"--- {hit['name']} @ {hit['url']}:{hit['at']} ---")
        print(hit["code"])
        print()


if __name__ == "__main__":
    main()
