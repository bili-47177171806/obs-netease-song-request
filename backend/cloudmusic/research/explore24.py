# -*- coding: utf-8 -*-
"""枚举渲染进程脚本资源 + 尝试同源 fetch，为抓 bundle 里的队列逻辑做准备。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    tree = c.call("Page.getResourceTree")
    frames = [tree["result"]["frameTree"]]
    urls = []
    def walk(f):
        urls.append(f["frame"]["url"])
        for r in f.get("resources", []):
            urls.append(r["url"])
        for ch in f.get("childFrames", []):
            walk(ch)
    walk(frames[0])
    js_urls = [u for u in urls if u and (u.endswith(".js") or "js/" in u)]

    print(f"总资源 {len(urls)} / JS {len(js_urls)}")
    for u in js_urls[:40]:
        print(u[:160])

    # 测试同源 fetch
    if js_urls:
        sample = js_urls[0]
        r = c.evaluate(f"fetch({json.dumps(sample)}).then(r=>r.status).catch(e=>'ERR:'+String(e))", await_promise=True)
        print("\nfetch 测试", sample[:80], "->", r)

    c.close()


if __name__ == "__main__":
    sys.exit(main())