# -*- coding: utf-8 -*-
"""再探：window.api 现状 / __mnb_globals__ 调用历史 / 加载的 JS 资源清单。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const api = window.api || {};
  const out = { apiType: typeof window.api, apiKeys: Object.keys(api).slice(0, 60) };
  if (Object.keys(api).length) {
    out.apiSample = {};
    Object.keys(api).slice(0, 8).forEach(k => { const v = api[k]; out.apiSample[k] = typeof v; });
  }
  out.globs = window.__mnb_globals__ || {};
  return out;
})()
""")
    print("window.api:", json.dumps({"apiType": r.get("apiType"), "keys": r.get("apiKeys"), "sample": r.get("apiSample")}, ensure_ascii=False, indent=1))
    print("\n__mnb_globals__ 现状:")
    for k, v in list(r["globs"].items()):
        s = json.dumps(v, ensure_ascii=False)
        print(f"  {k}: {s[:300]}")

    print("\n==== 已加载的脚本资源 ====")
    r = c.evaluate(r"""
(() => performance.getEntriesByType('resource').filter(e => e.name && !/\.(png|jpg|jpeg|gif|svg|woff2?|ttf|mp3|m4a|css)/i.test(e.name))
  .map(e => e.name)).slice(0, 40)
""")
    for u in r:
        print(u[:150])

    c.close()


if __name__ == "__main__":
    sys.exit(main())