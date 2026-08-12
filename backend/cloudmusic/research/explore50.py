# -*- coding: utf-8 -*-
"""列出 playingList / playing 命名空间的所有 redux action 类型。"""
import sys
import json
import re
from backend.cloudmusic.cdp import CDP, first_page

APP = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    expr = r"""
(async () => {
  const u = %s;
  const t = window.__bc[u] || (window.__bc[u] = await (await fetch(u)).text());
  const set = new Set();
  const rx = /"(playingList|playing)\/[A-Za-z0-9_]+"/g;
  let m;
  while ((m = rx.exec(t)) !== null) set.add(m[0]);
  const rx2 = /'(playingList|playing)\/[A-Za-z0-9_]+'/g;
  while ((m = rx2.exec(t)) !== null) set.add(m[0]);
  return [...set].sort();
})()
"""
    raw = c.call("Runtime.evaluate", {"expression": expr % json.dumps(APP), "returnByValue": True, "awaitPromise": True})
    res = raw.get("result", {}).get("result", {})
    if "exceptionDetails" in res:
        print("异常:", json.dumps(raw, ensure_ascii=False)[:500])
        return
    for a in res.get("value", []):
        print("  ", a)
    c.close()


if __name__ == "__main__":
    sys.exit(main())