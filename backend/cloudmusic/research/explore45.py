# -*- coding: utf-8 -*-
"""查 handoff playingState 全貌 + 在子 bundle 里找 Jg 实现。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page

VENDOR = "orpheus://orpheus/pub/hybrid/vendors~app~subApp.chunk.2b4bcc2.js"


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const st = window.__STORE__;
  const h = st.getState()['async:playingListHandoff'] || {};
  const pl = st.getState()['playingList'] || {};
  return { playingState: h.playingState,
           playingSource: h.playingSource,
           shouldUpload: h.shouldUpload,
           curPlaying: st.getState()['playing'] && st.getState()['playing'].curPlaying };
})()
""")
    print("handoff.playingState:", json.dumps(r, ensure_ascii=False, indent=1)[:2500])

    for url, kw in [(VENDOR, "Jg")]:
        r2 = c.evaluate(r"""
(async () => {
  const u = %s; const kw = %s;
  const cache = (window.__bc = window.__bc || {});
  let t = cache[u];
  if (t === undefined) { try { t = await (await fetch(u)).text(); cache[u] = t; } catch (e) { return { err: String(e) }; } }
  const out = [];
  let i = -1;
  while ((i = t.indexOf(kw, i + 1)) !== -1 && out.length < 8) {
    const seg = t.slice(Math.max(0, i - 120), i + 200).replace(/\n/g, ' ');
    if (/function|=>|player\.|fetch|request|call/.test(seg)) out.push({ i, c: seg });
    i += 1;
  }
  return out;
})()
""" % (json.dumps(url), json.dumps(kw, ensure_ascii=False)), await_promise=True)
        print(f"\n==== {url[-40:]} 里 Jg 候选 ====")
        for s in r2:
            print(f"\n[@{s['i']}] {s['c'][:360]}")
    c.close()


if __name__ == "__main__":
    sys.exit(main())