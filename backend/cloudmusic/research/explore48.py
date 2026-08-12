# -*- coding: utf-8 -*-
"""确认 channel 是否 Proxy + 提取全部原生方法名。"""
import sys
import json
import re
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


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const ch = window.channel;
  const probe = {};
  try { probe.isProxy = ch instanceof Proxy; } catch (e) { probe.isProxy = 'err'; }
  probe.toStringTag = Object.prototype.toString.call(ch);
  probe.sample = typeof ch['player.setCurrentTime'];
  probe.sampleLen = ch['player.setCurrentTime'] ? ch['player.setCurrentTime'].length : null;
  probe.desc = Object.getOwnPropertyDescriptor(ch, 'call') && Object.getOwnPropertyDescriptor(ch, 'call').value
    ? Object.getOwnPropertyDescriptor(ch, 'call').value.toString().slice(0, 120) : null;
  return probe;
})()
""")
    print("channel 探测:", json.dumps(r, ensure_ascii=False, indent=1))

    # 提取所有 At.call("method") 方法名
    expr = r"""
(async () => {
  const urls = %s;
  const cache = (window.__bc = window.__bc || {});
  const methods = {};
  const rx = /At\.call\\(\"([a-zA-Z]+\\.[A-Za-z0-9_]+)\"/g;
  for (const u of urls) {
    let t = cache[u];
    if (t === undefined) { try { t = await (await fetch(u)).text(); cache[u] = t; } catch (e) { continue; } }
    let m;
    while ((m = rx.exec(t)) !== null) methods[m[1]] = (methods[m[1]] || 0) + 1;
  }
  const keys = Object.keys(methods).sort();
  return { total: keys.length, keys };
})()
"""
    r2 = c.evaluate(expr % json.dumps(JS), await_promise=True)
    keys = r2["keys"]
    print("\n全部原生方法名（共", r2["total"], "）:")
    for k in keys:
        print("  ", k)
    print("\n==== 播放/队列/插入相关 ====")
    for k in keys:
        if re.search(r"play|queue|list|insert|song|next|track|position", k, re.I):
            print("  ", k)
    c.close()


if __name__ == "__main__":
    sys.exit(main())