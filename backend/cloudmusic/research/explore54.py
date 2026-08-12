# -*- coding: utf-8 -*-
"""动态枚举 playingList / playing 命名空间的全部 redux action 类型。

与 explore50 的区别：不硬编码 chunk hash，改为从 Page.getResourceTree 拿当前所有
JS 资源再逐个扫描，所以客户端升级后仍然可用。找「删除队列项」这类 action 时先跑这个。

    python -m backend.cloudmusic.research.explore54
"""
import json

from backend.cloudmusic.cdp import CDP, first_page

EXPR = r"""
(async () => {
  const urls = %s;
  const set = new Set();
  for (const u of urls) {
    let text;
    try {
      text = await (await fetch(u)).text();
    } catch (e) {
      continue;
    }
    const rx = /["'](playingList|playing)\/[A-Za-z0-9_]+["']/g;
    let m;
    while ((m = rx.exec(text)) !== null) set.add(m[0].slice(1, -1));
  }
  return [...set].sort();
})()
"""


def _js_urls(c):
    """资源树（含子 frame）→ performance/DOM 兜底，返回去重后的 JS URL。"""
    urls = []

    def walk(node):
        frame = node.get("frame") or {}
        if frame.get("url"):
            urls.append(frame["url"])
        for r in node.get("resources", []):
            if r.get("url"):
                urls.append(r["url"])
        for child in node.get("childFrames", []):
            walk(child)

    tree = c.call("Page.getResourceTree").get("result", {}).get("frameTree")
    if tree:
        walk(tree)

    if not any(u.endswith(".js") for u in urls):
        fallback = c.evaluate(
            "JSON.stringify([...performance.getEntriesByType('resource').map(e=>e.name),"
            "...[...document.scripts].map(s=>s.src)])"
        )
        try:
            urls += json.loads(fallback or "[]")
        except Exception:
            pass

    seen, out = set(), []
    for u in urls:
        if u and u.endswith(".js") and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Page.enable")

    urls = _js_urls(c)
    print(json.dumps({"jsResources": len(urls)}, ensure_ascii=False))
    if not urls:
        print(json.dumps({"err": "没有拿到 JS 资源，先跑 explore24 看资源树"}, ensure_ascii=False))
        return

    raw = c.call("Runtime.evaluate", {
        "expression": EXPR % json.dumps(urls),
        "returnByValue": True,
        "awaitPromise": True,
    })
    res = raw.get("result", {})
    if "exceptionDetails" in res:
        print(json.dumps({"err": str(res["exceptionDetails"])[:400]}, ensure_ascii=False))
        return
    actions = res.get("result", {}).get("value") or []
    print(json.dumps({"count": len(actions), "actions": actions}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
