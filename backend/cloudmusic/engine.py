# -*- coding: utf-8 -*-
"""网易云音乐 PC 客户端 · 注入「下一首播放」

通过 CDP(Chrome DevTools Protocol) 注入到客户端的渲染进程，直接调用它自己的
redux action（playingList/addItemToCurPlayingList + options.offset），把歌插到
当前播放曲之后 —— 等价于右键菜单的「下一首播放」，纯程序化、无需 UI 点击。

用法:
  python -m backend.cloudmusic.engine "歌名"                         # 选择 API 第一条插入
  python -m backend.cloudmusic.engine "歌名" --classic-search        # 按标题/歌手文字匹配插入
  python -m backend.cloudmusic.engine 3384055850 --id                 # 直接按 songId 插入
  python -m backend.cloudmusic.engine "歌名" --artist mochari --json # 机器可读输出

前提:
  - 网易云 PC 客户端已安装。（若 9222 调试口没开会自动带参重启客户端，登录态保留）
"""
import os
import sys
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.parse

from .cdp import CDP, first_page

PORT = 9222
APP = r"C:\Program Files\NetEase\CloudMusic\cloudmusic.exe"
SEARCH_API = "https://music.163.com/api/cloudsearch/pc"
SEQUENTIAL_PLAY_MODES = ("playOrder", "playCycle")
PLAY_MODES = ("playOrder", "playCycle", "playRandom", "playOneCycle")


def log(msg):
    print(f"[cloudmusic] {msg}", flush=True)


# ---------------------------------------------------------------- 端口与连接
def ensure_cdp():
    """确保 9222 调试口可用；不可用则带参重启客户端。"""
    if _port_alive():
        return True
    log(f"本地调试口 127.0.0.1:{PORT} 未开，正在带参重启客户端…（登录态会保留）")
    if not os.path.exists(APP):
        log(f"找不到客户端: {APP}，请手动以 {APP} --remote-debugging-port={PORT} 启动")
        return False
    try:
        subprocess.Popen([APP, f"--remote-debugging-port={PORT}"])
    except Exception as e:
        log(f"启动失败: {e}")
        return False
    for _ in range(60):  # 最多等 30s
        time.sleep(0.5)
        if _port_alive():
            log("调试口已就绪")
            return True
    return False


def _port_alive():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1.5)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 注入工具集
def js(c, expr, await_promise=False):
    return c.evaluate(expr, await_promise=await_promise)


def install_mode_observer(c):
    """记录用户手动切换的播放模式；程序触发的非可信 click 不计入。"""
    return js(c, r"""
(() => {
  if (window.__POINT_BOT_MODE_OBSERVER__) return true;
  window.__POINT_BOT_MODE_OBSERVER__ = true;
  window.__POINT_BOT_MANUAL_MODE__ = null;
  window.__POINT_BOT_MANUAL_MODE_VERSION__ = 0;
  document.addEventListener('click', event => {
    if (!event.isTrusted) return;
    const button = event.target && event.target.closest && event.target.closest('button');
    if (!button) return;
    const icon = button.querySelector('span[aria-label]');
    const labels = ['shuffle', 'order', 'singleloop', 'loop'];
    if (!icon || !labels.includes(icon.getAttribute('aria-label'))) return;
    setTimeout(() => {
      const st = window.__STORE__;
      if (!st) return;
      window.__POINT_BOT_MANUAL_MODE__ = st.getState().playing.playingMode;
      window.__POINT_BOT_MANUAL_MODE_VERSION__ += 1;
    }, 150);
  }, true);
  return true;
})()
""")


def _click_playing_mode(c):
    return js(c, r"""
(() => {
  const labels = ['shuffle', 'order', 'singleloop', 'loop'];
  const icon = [...document.querySelectorAll('span[aria-label]')]
    .find(e => labels.includes(e.getAttribute('aria-label')));
  const button = icon && icon.closest('button');
  if (!button) return false;
  button.click();
  return true;
})()
""")


def set_playing_mode(c, target_mode):
    """通过客户端自身控件切换到指定播放模式。"""
    if target_mode not in PLAY_MODES:
        return {"ok": False, "err": f"不支持的播放模式: {target_mode}"}
    mode = js(c, "window.__STORE__ && window.__STORE__.getState().playing.playingMode")
    previous = mode
    if mode == target_mode:
        return {"ok": True, "playingMode": mode, "previousPlayingMode": previous,
                "changed": False}
    for _ in range(8):
        if not _click_playing_mode(c):
            break
        time.sleep(0.35)
        mode = js(c, "window.__STORE__.getState().playing.playingMode")
        if mode == target_mode:
            return {"ok": True, "playingMode": mode,
                    "previousPlayingMode": previous, "changed": True}
    return {"ok": False, "err": f"无法切换播放模式到 {target_mode}",
            "playingMode": mode, "previousPlayingMode": previous}


def ensure_order_mode(c):
    """确保按列表顺序播放，不依赖屏幕坐标。"""
    mode = js(c, "window.__STORE__ && window.__STORE__.getState().playing.playingMode")
    previous = mode
    if mode in SEQUENTIAL_PLAY_MODES:
        return {"ok": True, "playingMode": mode, "previousPlayingMode": previous,
                "changed": False}

    for _ in range(8):
        if not _click_playing_mode(c):
            break
        time.sleep(0.35)
        mode = js(c, "window.__STORE__.getState().playing.playingMode")
        if mode in SEQUENTIAL_PLAY_MODES:
            return {"ok": True, "playingMode": mode,
                    "previousPlayingMode": previous, "changed": True}
    return {"ok": False, "err": "无法切换到顺序播放", "playingMode": mode,
            "previousPlayingMode": previous}


def ensure_order_playing():
    """建立短连接并确保客户端处于顺序播放模式。"""
    if not ensure_cdp():
        return {"ok": False, "err": "CDP 不可用"}
    c = CDP(first_page()["webSocketDebuggerUrl"])
    try:
        c.call("Runtime.enable")
        if not find_store(c):
            return {"ok": False, "err": "未找到客户端内部 store"}
        return ensure_order_mode(c)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        c.close()


def set_playing_mode_value(mode):
    """建立短连接并切换到指定播放模式。"""
    if not ensure_cdp():
        return {"ok": False, "err": "CDP 不可用"}
    c = CDP(first_page()["webSocketDebuggerUrl"])
    try:
        c.call("Runtime.enable")
        if not find_store(c):
            return {"ok": False, "err": "未找到客户端内部 store"}
        install_mode_observer(c)
        return set_playing_mode(c, mode)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        c.close()


def find_store(c):
    """在渲染进程里沿 React fiber 链定位 redux store，缓存到 window.__STORE__。"""
    r = js(c, r"""
(() => {
  if (window.__STORE__ && typeof window.__STORE__.dispatch === 'function') return 'cached';
  // 找任意带 fiber 的元素，沿 return 链向上找 Provider(memoizedProps.store) 或 Context(_currentValue.store)
  const all = document.querySelectorAll('*');
  for (const el of all) {
    const k = Object.keys(el).find(k => k.startsWith('__reactInternalInstance$') || k.startsWith('__reactFiber$'));
    if (!k) continue;
    let f = el[k];
    for (let i = 0; i < 400 && f; i++) {
      const mp = f.memoizedProps || {};
      if (mp.store && typeof mp.store.dispatch === 'function' && typeof mp.store.getState === 'function') {
        window.__STORE__ = mp.store; return 'store';
      }
      const t = f.type;
      if (t && typeof t === 'object' && t._currentValue && t._currentValue.store) {
        window.__STORE__ = t._currentValue.store; return 'ctx';
      }
      f = f.return;
    }
  }
  return null;
})()
""")
    return r == 'store' or r == 'ctx' or r == 'cached'


def _click_by_text(c, text):
    """在页面里找到文本为 text 的叶子并受信任点击。返回是否成功。"""
    info = js(c, r"""
(() => {
  const h = [...document.querySelectorAll('*')].find(e => e.children.length === 0 && (e.textContent || '').trim() === %s);
  if (!h) return null;
  const r = h.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
})()
""" % json.dumps(text))
    if not info or "x" not in info:
        return False
    c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": info["x"], "y": info["y"]})
    c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": info["x"], "y": info["y"], "button": "left", "buttons": 1, "clickCount": 1})
    c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": info["x"], "y": info["y"], "button": "left", "buttons": 0, "clickCount": 1})
    return True


def search_song(c, title, artist=None):
    """驱动客户端内建搜索：输入歌名 -> Enter -> 切到『单曲』标签 -> 取第一首(可匹配歌手)的 resource。"""
    info = js(c, r"""
(() => {
  const inp = document.querySelector('input[type=search]');
  if (!inp) return null;
  inp.focus();
  inp.select();           // 全选旧内容，打字时直接替换
  return { ph: inp.placeholder };
})()
""")
    if not info:
        return None
    c.call("Input.insertText", {"text": title})
    time.sleep(1.2)
    for _ in range(2):
        c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
        c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    # 等搜索页出来
    for _ in range(30):
        time.sleep(0.5)
        if js(c, r"document.body.innerText && document.body.innerText.indexOf('单曲') !== -1"):
            break
    # 切到单曲标签（综合视图的行结构不稳定）
    if not js(c, r"!!document.querySelector('div.tr')"):
        _click_by_text(c, "单曲")
        for _ in range(30):
            time.sleep(0.5)
            if js(c, r"!!document.querySelector('div.tr')"):
                break
    # 在单曲结果行里抓 resource
    return _extract_first_resource(c, title, artist)


def _extract_first_resource(c, title, artist=None):
    row_sel = r"""
(() => {
  const rows = [...document.querySelectorAll('div.tr')].filter(e => {
    const t = e.innerText || '';
    return t.indexOf('#') === -1 && e.getBoundingClientRect().height > 0;
  });
  if (artist) {
    const hit = rows.find(e => {
      const t = e.innerText || '';
      return t.indexOf(%s) !== -1 && (%s === '' || t.toLowerCase().indexOf(%s.toLowerCase()) !== -1);
    });
    return hit || rows[0] || null;
  }
  return rows[0] || null;
})()
"""
    js_expr = r"""
(() => {
  const artist = %s;
  const keyword = %s;
  const rows = [...document.querySelectorAll('div.tr')].filter(e => {
    const t = e.innerText || '';
    return t.indexOf('#') === -1 && t.indexOf(keyword) !== -1 && e.getBoundingClientRect().height > 0;
  });
  let hit = rows[0];
  if (artist) hit = rows.find(e => (e.innerText || '').toLowerCase().indexOf(artist.toLowerCase()) !== -1) || rows[0];
  if (!hit) return null;
  const ik = Object.keys(hit).find(k => k.startsWith('__reactInternalInstance$') || k.startsWith('__reactFiber$'));
  let f = ik ? hit[ik] : null;
  for (let i = 0; i < 10 && f; i++) {
    const mp = f.memoizedProps || {};
    if (mp.resource && typeof mp.resource === 'object' && mp.resource.id) return mp.resource;
    f = f.return;
  }
  return null;
})()
""" % (json.dumps(artist or ""), json.dumps(title, ensure_ascii=False))

    for _ in range(20):
        time.sleep(0.5)
        r = js(c, js_expr)
        if isinstance(r, dict) and r.get("id"):
            return r
        if r and isinstance(r, dict) and "error" in r:
            time.sleep(0.3)
    return None


def _search_norm(value):
    """用于搜索结果匹配：忽略大小写、空白和常见标点。"""
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _result_artists(song):
    artists = song.get("artists") or song.get("ar") or []
    return [a.get("name", "") for a in artists if isinstance(a, dict)]


def select_search_result(songs, title, artist="", strategy="first"):
    """按指定策略从 API 结果中选歌：first 取首条，classic 做文字匹配。"""
    if not songs:
        return None
    if strategy == "first":
        return songs[0]
    if strategy != "classic":
        raise ValueError(f"未知搜索策略: {strategy}")

    wanted_title = _search_norm(title)
    wanted_artist = _search_norm(artist)

    def score(item):
        name = _search_norm(item.get("name"))
        names = [_search_norm(x) for x in _result_artists(item)]
        value = 0
        if name == wanted_title:
            value += 100
        elif wanted_title and wanted_title in name:
            value += 40
        if wanted_artist:
            if wanted_artist in names:
                value += 50
            elif any(wanted_artist in name for name in names):
                value += 20
        return value

    # API 返回顺序作为同分时的稳定兜底，避免随机选中翻唱/现场版。
    return max(enumerate(songs), key=lambda pair: (score(pair[1]), -pair[0]))[1]


def search_song_api_candidates(title, limit=20):
    """通过网易云搜索接口取得候选歌曲；接口失败时返回空列表。"""
    params = urllib.parse.urlencode({
        "s": title,
        "type": 1,
        "offset": 0,
        "limit": limit,
        "total": "true",
        "csrf_token": "",
    }).encode("utf-8")
    request = urllib.request.Request(
        SEARCH_API,
        data=params,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return ((data.get("result") or {}).get("songs") or [])


def search_song_api(title, artist="", strategy="first"):
    """通过网易云搜索接口取得 songId；接口失败时返回 None。

    该接口属于客户端使用的非正式接口，因此调用失败不能阻断后面的 UI 搜索回退。
    """
    songs = search_song_api_candidates(title)
    best = select_search_result(songs, title, artist, strategy)
    if not best:
        return None
    song_id = best.get("id")
    return str(song_id) if song_id else None


def _split_artist_song(value):
    """解析“歌手的歌曲”；两侧为空或没有“的”时返回 None。"""
    if "的" not in value:
        return None
    artist, song = value.split("的", 1)
    artist, song = artist.strip(), song.strip()
    return (artist, song) if artist and song else None


def _title_matches_query(song, query):
    title = _search_norm(song.get("name"))
    wanted = _search_norm(query)
    return bool(title and wanted and (title == wanted or title in wanted or wanted in title))


def resolve_song_api(title, artist="", strategy="first"):
    """解析 API 歌曲 ID，并处理“歌手的歌曲”格式。

    返回 (song_id, info)，info 记录实际搜索词和是否触发了反转搜索。
    """
    info = {"searchQuery": title, "possessiveFallback": False}
    songs = search_song_api_candidates(title)

    if strategy == "first" and not artist:
        parts = _split_artist_song(title)
        if parts:
            artist_hint, song_hint = parts
            direct = next((item for item in songs if _title_matches_query(item, title)), None)
            if direct and direct.get("id"):
                return str(direct["id"]), info

            fallback_query = f"{song_hint} {artist_hint}"
            fallback_songs = search_song_api_candidates(fallback_query)
            if fallback_songs and fallback_songs[0].get("id"):
                info.update({"searchQuery": fallback_query, "possessiveFallback": True})
                return str(fallback_songs[0]["id"]), info

    best = select_search_result(songs, title, artist, strategy)
    if not best or not best.get("id"):
        return None, info
    return str(best["id"]), info


def insert_next(c, resource, after_song_id=None):
    """注入：把 resource 插到当前曲或指定锚点之后。返回结果 dict。"""
    r = js(c, r"""
(() => {
  const st = window.__STORE__;
  if (!st) return { err: 'no store' };
  const pl = st.getState()['playingList'] || {};
  const list = pl.curPlayingList || [];
  const cur = st.getState()['playing'] && st.getState()['playing'].curPlaying;
  const curId = cur ? String(cur.id) : null;
  let idx = -1;
  if (curId) idx = list.findIndex(x => String(x.resourceId || x.id) === curId);
  const anchorId = %s;
  let anchorIdx = -1;
  if (anchorId) {
    if (idx >= 0 && curId === anchorId) {
      anchorIdx = idx;
    } else {
      const minIdx = idx >= 0 ? idx + 1 : 0;
      for (let i = list.length - 1; i >= minIdx; i--) {
        if (String(list[i].resourceId || list[i].id) === anchorId) {
          anchorIdx = i; break;
        }
      }
    }
    if (anchorIdx < 0) return { err: 'anchor not found', anchorId };
  }
  const offset = anchorId ? anchorIdx : (idx >= 0 ? idx : Math.max(0, list.length - 1));
  const resource = %s;
  const payload = {
    trackList: [resource],
    trackFrom: { scene: 'search', resourceType: 'track', fromInfo: {} },
    options: { clear: false, play: false, playId: undefined, offset },
    triggerScene: 'search',
    triggerAction: 'nextPlay'
  };
  try {
    st.dispatch({ type: 'playingList/addItemToCurPlayingList', payload });
  } catch (e) { return { err: String(e) }; }
  return { ok: true, songId: String(resource.id), name: resource.name || (resource.album && resource.album.name) || '',
           offset, currentIdx: idx, queueLenBefore: list.length,
           anchorId, anchorFound: anchorId ? anchorIdx >= 0 : null };
})()
""" % (json.dumps(str(after_song_id)) if after_song_id else "null",
       json.dumps(resource, ensure_ascii=False)))
    if isinstance(r, dict) and r.get("ok"):
        return r
    return r if isinstance(r, dict) else {"err": str(r)}


def verify_insert(c, song_id, window_s=5, after_song_id=None, expected_offset=None):
    """轮询确认 songId 已出现在当前播放曲或指定锚点之后。"""
    for _ in range(window_s * 2):
        time.sleep(0.5)
        r = js(c, r"""
(() => {
  const st = window.__STORE__; if (!st) return null;
  const pl = st.getState()['playingList'] || {};
  const list = pl.curPlayingList || [];
  const cur = st.getState()['playing'] && st.getState()['playing'].curPlaying;
  const curId = cur ? String(cur.id) : null;
  const idx = curId ? list.findIndex(x => String(x.resourceId || x.id) === curId) : -1;
  const anchorId = %s;
  const expectedOffset = %s;
  let insertAfterIdx = Number.isInteger(expectedOffset) ? expectedOffset : idx;
  if (anchorId && !Number.isInteger(expectedOffset)) {
    insertAfterIdx = -1;
    const minIdx = idx >= 0 ? idx + 1 : 0;
    for (let i = list.length - 1; i >= minIdx; i--) {
      if (String(list[i].resourceId || list[i].id) === anchorId) {
        insertAfterIdx = i; break;
      }
    }
  }
  const sid = %s;
  const where = insertAfterIdx >= 0 ? list[insertAfterIdx + 1] : null;
  const succeeded = insertAfterIdx >= 0 && where && String(where.resourceId || where.id) === sid;
  const after = list.slice(idx >= 0 ? idx : 0, idx + 4)
    .map(x => String(x.resourceId || x.id));
  return { succeeded, curId, idx, insertAfterIdx, anchorId, after, len: list.length };
})()
""" % (json.dumps(str(after_song_id)) if after_song_id else "null",
       json.dumps(expected_offset) if expected_offset is not None else "null",
       json.dumps(str(song_id))))
        if isinstance(r, dict) and r.get("succeeded"):
            return True, r
    return False, (r if isinstance(r, dict) else None)


def remove_from_queue(c, song_ids):
    """从当前播放队列里按 songId 删除，返回结果 dict。

    走 `playingList/removeItemFromCurPlayingListByIds`（**不带 on 前缀**）。
    带 on 前缀的那个是空生成器通知钩子，dispatch 它不会改队列。
    该 saga 内部会 replaceCurPlayingList → syncCurPlayingListToNative，
    和插入共用同一条同步链；删到正在播的那首时客户端会自动跳下一首。
    """
    wanted = [str(s) for s in song_ids if str(s or "").strip()]
    if not wanted:
        return {"ok": False, "err": "没有要删除的 songId"}
    r = js(c, r"""
(() => {
  const st = window.__STORE__;
  if (!st) return { err: 'no store' };
  const ids = %s;
  const pl = st.getState()['playingList'] || {};
  const list = pl.curPlayingList || [];
  const lenBefore = list.length;
  const cur = st.getState()['playing'] && st.getState()['playing'].curPlaying;
  const curId = cur ? String(cur.resourceId || cur.id) : null;
  // saga 内部用严格相等过滤 resourceId，必须原样回传队列里的值（可能是 number）。
  const hits = ids.map(id => list.find(x => String(x.resourceId || x.id) === id)).filter(Boolean);
  if (!hits.length) return { err: 'not in queue', ids, queueLenBefore: lenBefore };
  const present = hits.map(x => String(x.resourceId || x.id));
  try {
    st.dispatch({
      type: 'playingList/removeItemFromCurPlayingListByIds',
      payload: {
        removeIds: hits.map(x => ({ resourceId: x.resourceId, resourceType: x.resourceType })),
        triggerScene: 'playingList'
      }
    });
  } catch (e) { return { err: String(e) }; }
  return { ok: true, removed: present, skipped: ids.filter(id => !present.includes(id)),
           queueLenBefore: lenBefore, removedCurrent: present.includes(curId),
           idType: typeof (hits[0] && hits[0].resourceId) };
})()
""" % json.dumps(wanted))
    return r if isinstance(r, dict) else {"err": str(r)}


def verify_removal(c, song_ids, window_s=5):
    """轮询确认这些 songId 已从队列消失。"""
    wanted = [str(s) for s in song_ids]
    r = None
    for _ in range(window_s * 2):
        time.sleep(0.5)
        r = js(c, r"""
(() => {
  const st = window.__STORE__; if (!st) return null;
  const list = (st.getState()['playingList'] || {}).curPlayingList || [];
  const ids = %s;
  const still = ids.filter(id => list.some(x => String(x.resourceId || x.id) === id));
  return { gone: still.length === 0, still, len: list.length };
})()
""" % json.dumps(wanted))
        if isinstance(r, dict) and r.get("gone"):
            return True, r
    return False, (r if isinstance(r, dict) else None)


def jump_track(c, flag=None, song_id=None):
    """跳歌：flag=1 下一首 / -1 上一首，或 song_id 直接跳到队列里的某一首。"""
    r = js(c, r"""
(() => {
  const st = window.__STORE__;
  if (!st) return { err: 'no store' };
  const flag = %s, assignedResourceId = %s;
  const list = (st.getState()['playingList'] || {}).curPlayingList || [];
  if (assignedResourceId && !list.some(x => String(x.resourceId || x.id) === assignedResourceId)) {
    return { err: 'not in queue', assignedResourceId };
  }
  const payload = { type: 'call' };
  if (assignedResourceId) payload.assignedResourceId = assignedResourceId;
  else payload.flag = flag;
  try {
    st.dispatch({ type: 'playingList/jump2Track', payload });
  } catch (e) { return { err: String(e) }; }
  return { ok: true, flag: payload.flag ?? null, assignedResourceId: assignedResourceId || null };
})()
""" % (json.dumps(int(flag) if flag is not None else 1),
       json.dumps(str(song_id)) if song_id else "null"))
    return r if isinstance(r, dict) else {"err": str(r)}


def _with_store(fn):
    """建立短连接、定位 store 后执行 fn(c)，统一错误处理。"""
    if not ensure_cdp():
        return {"ok": False, "err": "CDP 不可用"}
    c = CDP(first_page()["webSocketDebuggerUrl"])
    try:
        c.call("Runtime.enable")
        if not find_store(c):
            return {"ok": False, "err": "未找到客户端内部 store"}
        return fn(c)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        c.close()


def remove_songs(song_ids):
    """建立短连接并从播放队列删除指定歌曲。"""
    def run(c):
        out = remove_from_queue(c, song_ids)
        if out.get("ok"):
            verified, detail = verify_removal(c, out.get("removed") or [])
            out = {**out, "verified": verified, "around": detail}
        return out
    return _with_store(run)


def jump_to(flag=None, song_id=None):
    """建立短连接并跳歌。"""
    return _with_store(lambda c: jump_track(c, flag=flag, song_id=song_id))


def fetch_song_by_id(c, song_id):
    """在页面内调官方 song/detail 接口取完整歌曲对象。"""
    return js(c, r"""
(async () => {
  try {
    const d = await fetch('https://music.163.com/api/song/detail/?ids=[' + %s + ']').then(r => r.json());
    return d.songs && d.songs[0] ? d.songs[0] : null;
  } catch (e) { return null; }
})()
""" % json.dumps(str(song_id)), await_promise=True)


def get_now_playing():
    """读取当前播放歌曲；不启动客户端、不修改播放状态。"""
    if not _port_alive():
        return {"ok": False, "err": "CDP 不可用"}
    c = CDP(first_page()["webSocketDebuggerUrl"])
    try:
        c.call("Runtime.enable")
        if not find_store(c):
            return {"ok": False, "err": "未找到客户端内部 store"}
        install_mode_observer(c)
        result = js(c, r"""
(() => {
  const p = window.__STORE__.getState().playing || {};
  const current = p.curPlaying || {};
  const track = current.track || p.curTrack || {};
  const artists = track.artists || p.resourceArtists || [];
  const album = track.album || {};
  const songId = track.id || current.resourceId || p.resourceTrackId || '';
  const durationMs = track.duration || (Number(p.resourceDuration) || 0) * 1000;
  const durationSec = durationMs / 1000;
  const progressInput = [...document.querySelectorAll('input[type="range"]')].find(input => {
    const max = Number(input.max);
    const value = Number(input.value);
    return Number.isFinite(max) && Number.isFinite(value) && max > 0
      && Math.abs(max - durationSec) <= Math.max(2, durationSec * 0.02)
      && value >= 0 && value <= max + 2;
  });
  return {
    songId: songId ? String(songId) : '',
    name: track.name || p.resourceName || '',
    artists: artists.map(x => typeof x === 'string' ? x : (x.name || '')),
    album: album.name || '',
    durationMs,
    currentPositionMs: progressInput ? Math.round(Number(progressInput.value) * 1000) : null,
    coverUrl: album.picUrl || album.blurPicUrl || p.resourceCoverUrl || '',
    playingState: p.playingState,
    playingMode: p.playingMode,
    volumePercent: Number.isFinite(Number(p.playingVolume)) ? Number(p.playingVolume) : 0,
    manualPlayingMode: window.__POINT_BOT_MANUAL_MODE__ || null,
    manualModeVersion: window.__POINT_BOT_MANUAL_MODE_VERSION__ || 0,
    resourceType: current.resourceType || p.resourceType || ''
  };
})()
""")
        if not isinstance(result, dict):
            return {"ok": False, "err": "读取当前播放状态失败"}
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        c.close()


def insert_song(song, artist="", id_mode=False, search_strategy="first",
                after_song_id=None):
    """一键插入：确保端口 -> 定位 store -> 搜索/取歌 -> 插入 -> 验证。返回结果 dict。"""
    if not ensure_cdp():
        return {"ok": False, "err": "CDP 不可用"}
    c = CDP(first_page()["webSocketDebuggerUrl"])
    try:
        c.call("Runtime.enable")
        c.call("Page.enable")
        time.sleep(0.5)
        c.evaluate("window.__STORE__ = null")
        if not find_store(c):
            return {"ok": False, "err": "未找到客户端内部 store"}
        install_mode_observer(c)
        search_mode = None
        search_info = {}
        if id_mode:
            resource = fetch_song_by_id(c, song)
            if not resource:
                return {"ok": False, "err": f"按 id {song} 取不到歌曲信息"}
        else:
            # 先走轻量 API 搜索；API 不稳定或拿不到详情时回退到客户端 UI 搜索。
            api_song_id, search_info = resolve_song_api(song, artist, strategy=search_strategy)
            resource = fetch_song_by_id(c, api_song_id) if api_song_id else None
            if resource:
                search_mode = "api"
            else:
                ui_query = search_info.get("searchQuery") or song
                resource = search_song(c, ui_query, artist)
                search_mode = "ui"
            if not resource:
                return {"ok": False, "err": f"搜不到『{song}』的单曲结果"}
        mode_result = ensure_order_mode(c)
        if not mode_result.get("ok"):
            return mode_result
        res = insert_next(c, resource, after_song_id=after_song_id)
        verified, around = False, None
        if res.get("ok"):
            verified, around = verify_insert(
                c, res.get("songId"), after_song_id=after_song_id,
                expected_offset=res.get("offset")
            )
        return {**res, **search_info, "playingMode": mode_result.get("playingMode"),
                "previousPlayingMode": mode_result.get("previousPlayingMode"),
                "playingModeChanged": bool(mode_result.get("changed")),
                "verified": bool(verified), "around": around,
                **({"searchMode": search_mode, "searchStrategy": search_strategy}
                   if search_mode else {})}
    except Exception as e:
        return {"ok": False, "err": str(e)}
    finally:
        try:
            c.close()
        except Exception:
            pass


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="网易云 PC 注入『下一首播放』")
    ap.add_argument("song", help="歌名，或 --id 模式下的 songId")
    ap.add_argument("--artist", default="", help="歌手名（配合 --classic-search 精确匹配，可选）")
    ap.add_argument("--id", action="store_true", help="直接按 songId 插入（跳过搜索）")
    ap.add_argument("--classic-search", action="store_true",
                    help="使用标题/歌手文字匹配，而不是直接选择 API 第一条")
    ap.add_argument("--json", action="store_true", help="仅输出 JSON 结果（机器可读）")
    args = ap.parse_args()

    if not assert_args(args):
        ap.error("需要歌名或 --id 的 songId")

    try:
        strategy = "classic" if args.classic_search else "first"
        res = insert_song(args.song, artist=args.artist, id_mode=args.id,
                          search_strategy=strategy)
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "err": "interrupted"}, ensure_ascii=False))
        return 1
    if not args.json:
        if res.get("ok"):
            log("已插入: %s (位置 %s, 队列 %s->%s)"
                % (res.get("name") or res.get("songId"), res.get("offset"),
                   res.get("queueLenBefore"), _len_of(res)))
            if res.get("verified"):
                log("验证: ✅ 已排在当前播放曲之后 %s" % (res.get("around") or {}).get("after", []))
            else:
                log("验证: ⚠ 未确认（可打开播放列表查看）")
        else:
            log("失败: %s" % res.get("err"))
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("verified") else 2


def assert_args(args):
    if not args.id and not args.song.strip():
        return False
    return True


def _len_of(res):
    a = res.get("around") or {}
    return a.get("len") if a.get("len") is not None else "?"


if __name__ == "__main__":
    sys.exit(main())
