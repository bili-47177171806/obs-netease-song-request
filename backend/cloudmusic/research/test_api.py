# -*- coding: utf-8 -*-
"""测试页面内是否能用官方 song/detail 接口取完整歌曲对象。"""
import sys
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    r = c.evaluate(r"""
fetch('https://music.163.com/api/song/detail/?ids=[3384055850]')
  .then(r => r.json())
  .then(d => d.songs && d.songs[0] ? { id: d.songs[0].id, name: d.songs[0].name,
    artists: (d.songs[0].artists || []).map(a => a.name),
    album: d.songs[0].album && d.songs[0].album.name } : { noSongs: true })
  .catch(e => ({ err: String(e) }))
""", await_promise=True)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    c.close()


if __name__ == "__main__":
    sys.exit(main())