# -*- coding: utf-8 -*-
"""缓存全 bundle，多 token 搜索，找出菜单/队列相关代码。"""
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

    toks = ["dawn-mock-meau", "cell_common_right_button_optionnextPlay",
            "播放队列", "nextPlay", "addToQueue", "insertQueue", "queuePush",
            "contextmenu", "ContextMenu", "MenuManager"]
    tj = json.dumps(toks)

    r = c.evaluate(r"""
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
""" % (json.dumps(js_urls), tj), await_promise=True)

    for f in r:
        hitstr = " ".join(f"{k}:{v}" for k, v in f["hits"].items()) or "(no hits)"
        print(f"{f['u']:46} {f['size']:>8}  {hitstr}")

    # 对命中 dawn-mock-meau 的文件给出一段上下文
    ctx = c.evaluate(r"""
(async () => {
  const urls = %s;
  const kw = 'dawn-mock-meau';
  const out = [];
  for (const u of urls) {
    const t = window.__bc[u];
    if (!t) continue;
    const i = t.indexOf(kw);
    if (i === -1) continue;
    out.push({ u: u.slice(-42), ctx: t.slice(Math.max(0, i - 300), i + 300).replace(/\n/g, ' ') });
  }
  return out;
})()
""" % json.dumps(js_urls), await_promise=True)
    print("\n==== dawn-mock-meau 上下文 ====")
    for x in ctx:
        print("\n---", x["u"])
        print(x["ctx"][:800])

    c.close()


if __name__ == "__main__":
    sys.exit(main())