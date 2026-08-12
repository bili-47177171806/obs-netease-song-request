# -*- coding: utf-8 -*-
"""调试版：打印多 token 搜索的原始返回。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    toks = ["dawn-mock-meau", "cell_common_right_button_optionnextPlay", "播放队列", "nextPlay",
            "addToQueue", "insertQueue", "queuePush", "contextmenu", "MenuManager"]
    js_urls = []
    tree = c.call("Page.getResourceTree")
    def walk(f):
        js_urls.extend(rurl for rurl in [f["frame"]["url"]] + [r["url"] for r in f.get("resources", [])] if rurl.endswith(".js"))
        for ch in f.get("childFrames", []):
            walk(ch)
    walk(tree["result"]["frameTree"])

    expr = """
(async () => {
  const urls = %s;
  const toks = %s;
  const cache = (window.__bc = window.__bc || {});
  const out = [];
  for (const u of urls) {
    let t = cache[u];
    if (t === undefined) { try { t = await (await fetch(u)).text(); cache[u] = t; } catch (e) { continue; } }
    const row = { u: u.slice(-42), size: t.length, hits: {} };
    for (const k of toks) {
      let n = 0, i = -1;
      while ((i = t.indexOf(k, i + 1)) !== -1 && n < 30) n++;
      if (n) row.hits[k] = n;
    }
    out.push(row);
  }
  return out;
})()
""" % (json.dumps(js_urls), json.dumps(toks, ensure_ascii=False))

    raw = c.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    print("raw:", json.dumps(raw, ensure_ascii=False)[:2000])
    res = raw.get("result", {}).get("result", {}).get("value")
    if isinstance(res, list):
        for f in res:
            hitstr = " ".join(f"{k}:{v}" for k, v in f["hits"].items()) or "(no hits)"
            print(f"{f['u']:46} {f['size']:>8}  {hitstr}")
    else:
        print("非 list:", json.dumps(res, ensure_ascii=False)[:500])

    c.close()


if __name__ == "__main__":
    sys.exit(main())