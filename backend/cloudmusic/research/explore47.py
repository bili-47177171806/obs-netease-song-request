# -*- coding: utf-8 -*-
"""枚举 window.channel 的全部原生方法名，找队列/插入相关。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"""
(() => {
  const ch = window.channel;
  if (!ch) return 'no channel';
  const names = Object.getOwnPropertyNames(ch);
  const rel = names.filter(n => /player|play|list|queue|insert|next|song|track/i.test(n));
  const rel2 = rel.filter(n => /insert|queue|next|list|play|set|add|del|remove/i.test(n));
  return { total: names.length, playerish: rel.slice(0, 120), mostRel: rel2.slice(0, 60) };
})()
""")
    print("channel 方法总数:", r["total"])
    print("\n==== 播放相关原生方法 ====")
    for m in r["playerish"]:
        print("  ", m)
    print("\n==== 最相关（insert/queue/next/list）====")
    for m in r["mostRel"]:
        print("  ", m)
    c.close()


if __name__ == "__main__":
    sys.exit(main())