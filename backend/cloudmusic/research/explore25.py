# -*- coding: utf-8 -*-
"""抓 bundle 搜『下一首播放』上下文，定位处理函数。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    tree = c.call("Page.getResourceTree")
    urls = []
    def walk(f):
        urls.append(f["frame"]["url"])
        for r in f.get("resources", []):
            urls.append(r["url"])
        for ch in f.get("childFrames", []):
            walk(ch)
    walk(tree["result"]["frameTree"])
    js_urls = [u for u in urls if u and u.endswith(".js")]

    r = c.evaluate(r"""
(async () => {
  const urls = %s;
  const kw = '下一首播放';
  const out = [];
  for (const u of urls) {
    let t;
    try { t = await (await fetch(u)).text(); } catch (e) { out.push({ u: u.slice(-40), err: String(e) }); continue; }
    const hits = [];
    let i = -1;
    while ((i = t.indexOf(kw, i + 1)) !== -1 && hits.length < 12) {
      hits.push(t.slice(Math.max(0, i - 260), i + 300).replace(/\n/g, ' '));
    }
    out.push({ u: u.slice(-46), size: t.length, hits });
  }
  return out;
})()
""" % json.dumps(js_urls), await_promise=True)
    for f in r:
        print("\n====", f["u"], "(", f.get("size", "?"), ")")
        for h in f.get("hits", []):
            print("---")
            print(h[:700])

    c.close()


if __name__ == "__main__":
    sys.exit(main())