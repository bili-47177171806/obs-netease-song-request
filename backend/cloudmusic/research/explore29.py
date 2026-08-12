# -*- coding: utf-8 -*-
"""硬编码 bundle URL 清单，搜索菜单/队列相关 token。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

JS = [
    "orpheus://orpheus/pub/vendor/@cloudmusic-desktop/vendors-rudio@0.1.x/vendors-rudio.pc-new.production.js",
    "orpheus://orpheus/pub/hybrid/11.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/vendors~app.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/app.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/vendors~app~subApp.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/66.chunk.2b4bcc2.js",
    "orpheus://orpheus/pub/hybrid/6.chunk.2b4bcc2.js",
]
TOKS = ["dawn-mock-meau", "cell_common_right_button_optionnextPlay", "播放队列",
        "nextPlay", "addToQueue", "insertQueue", "queuePush", "contextmenu",
        "MenuManager", "添加列表", "插播"]


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(async () => {
  const urls = %s;
  const toks = %s;
  const cache = (window.__bc = window.__bc || {});
  const out = [];
  for (const u of urls) {
    let t = cache[u];
    if (t === undefined) { try { t = await (await fetch(u)).text(); cache[u] = t; } catch (e) { continue; } }
    const row = { u: u.slice(-48), size: t.length, hits: {} };
    for (const k of toks) {
      let n = 0, i = -1;
      while ((i = t.indexOf(k, i + 1)) !== -1 && n < 30) n++;
      if (n) row.hits[k] = n;
    }
    out.push(row);
  }
  return out;
})()
""" % (json.dumps(JS), json.dumps(TOKS, ensure_ascii=False)), await_promise=True)

    for f in r:
        hitstr = " ".join(f"{k}:{v}" for k, v in f["hits"].items()) or "(no hits)"
        print(f"{f['u']:50} {f['size']:>8}  {hitstr}")

    # dawn-mock-meau 上下文（若有）
    ctx = c.evaluate(r"""
(async () => {
  const urls = %s;
  const kw = 'dawn-mock-meau';
  const out = [];
  for (const u of urls) {
    const t = window.__bc[u];
    if (!t) continue;
    let i = -1, n = 0;
    while ((i = t.indexOf(kw, i + 1)) !== -1 && n < 5) {
      out.push({ u: u.slice(-48), ctx: t.slice(Math.max(0, i - 260), i + 260).replace(/\n/g, ' ') });
      n++;
    }
  }
  return out;
})()
""" % json.dumps(JS), await_promise=True)
    print("\n==== dawn-mock-meau 上下文 ====")
    for x in ctx:
        print("\n---", x["u"])
        print(x["ctx"][:600])

    c.close()


if __name__ == "__main__":
    sys.exit(main())