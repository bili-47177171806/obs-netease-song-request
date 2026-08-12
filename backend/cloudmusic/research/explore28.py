# -*- coding: utf-8 -*-
"""逐步调试：js_urls 数量 + 硬编码 fetch 状态。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    tree = c.call("Page.getResourceTree")
    print("tree keys:", list(tree.get("result", {}).keys()))
    ft = tree["result"]["frameTree"]
    urls = []
    def walk(f):
        urls.append(f["frame"]["url"])
        for r in f.get("resources", []):
            urls.append(r["url"])
        for ch in f.get("childFrames", []):
            walk(ch)
    walk(ft)
    js_urls = [u for u in urls if u and u.endswith(".js")]
    print("total urls:", len(urls), "js:", len(js_urls))
    for u in js_urls:
        print("  ", u[:110])

    test = "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js"
    r = c.evaluate(f"fetch({json.dumps(test)}).then(r=>r.status + ':' + r.ok).catch(e=>'ERR:'+String(e))", await_promise=True)
    print("fetch app.chunk ->", r)
    r = c.evaluate(f"fetch({json.dumps(test)}).then(r=>r.text()).then(t=>t.length).catch(e=>'ERR:'+String(e))", await_promise=True)
    print("app.chunk 文本长度 ->", r)

    c.close()


if __name__ == "__main__":
    sys.exit(main())