# -*- coding: utf-8 -*-
"""网易云注入『下一首播放』· HTTP 服务（供其他应用接入）

在 127.0.0.1:8866 上监听，收到 POST JSON 就把指定歌曲插入当前播放队列。

只读接口:
  GET /health
  GET /now-playing

用法:
  python -m backend.cloudmusic.server [--port 8866]

请求示例:
  {"song": "IF Else"}                                # 选择 API 第一条插入
  {"song": "IF Else", "artist": "mochari",
   "searchStrategy": "classic"}                      # 经典文字匹配
  {"song": "IF Else"}                             # 按歌名搜索插入
  {"id": "3384055850"}                            # 直接按网易云 songId 插入
  {"track": {...完整歌曲对象...}}                  # 传完整歌曲对象插入（最精确）
  {"id": "3384055850", "afterSongId": "123"}   # 插到指定池尾歌曲之后

返回:
  {"ok": true, "songId": ..., "name": ..., "offset": ..., "verified": true, ...}
"""
import json
import time
import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .cdp import CDP, first_page
from . import engine


# 网易云客户端的搜索页面和 Redux store 是共享状态，点歌请求必须串行执行。
REQUEST_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _reply(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/health":
            return self._reply({
                "ok": True,
                "service": "cloudmusic-cdp",
                "busy": REQUEST_LOCK.locked(),
            })
        if path == "/now-playing":
            with REQUEST_LOCK:
                result = engine.get_now_playing()
            return self._reply(result, 200 if result.get("ok") else 503)
        self._reply({"ok": False, "err": "not found"}, 404)

    def do_POST(self):
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.loads(raw) if raw else {}
        except Exception as e:
            return self._reply({"ok": False, "err": f"bad body: {e}"}, 400)

        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/play-mode/order":
            with REQUEST_LOCK:
                out = engine.ensure_order_playing()
            return self._reply(out, 200 if out.get("ok") else 503)
        if path == "/play-mode":
            mode = str(body.get("mode") or "")
            if mode not in engine.PLAY_MODES:
                return self._reply({"ok": False, "err": "无效播放模式"}, 400)
            with REQUEST_LOCK:
                out = engine.set_playing_mode_value(mode)
            return self._reply(out, 200 if out.get("ok") else 503)
        if path == "/remove":
            raw_ids = body.get("ids")
            if raw_ids is None:
                raw_ids = [body.get("id")] if body.get("id") else []
            ids = [str(i).strip() for i in raw_ids if str(i or "").strip()]
            if not ids:
                return self._reply({"ok": False, "err": "需要 id / ids 字段"}, 400)
            with REQUEST_LOCK:
                out = engine.remove_songs(ids)
            return self._reply(out, 200 if out.get("ok") else 503)
        if path == "/jump":
            song_id = str(body.get("id") or "").strip() or None
            flag = body.get("flag")
            if song_id is None and flag is None:
                return self._reply({"ok": False, "err": "需要 id 或 flag 字段"}, 400)
            if flag is not None and int(flag) not in (1, -1):
                return self._reply({"ok": False, "err": "flag 只能是 1 / -1"}, 400)
            with REQUEST_LOCK:
                out = engine.jump_to(flag=flag, song_id=song_id)
            return self._reply(out, 200 if out.get("ok") else 503)

        try:
            # 即使 HTTP 层是多线程的，也不要让多个请求同时操作同一个客户端页面。
            with REQUEST_LOCK:
                after_song_id = body.get("afterSongId")
                if after_song_id is not None:
                    after_song_id = str(after_song_id).strip() or None
                if body.get("track") and isinstance(body["track"], dict) and body["track"].get("id"):
                    # 传完整歌曲对象直插（最精确，免搜索）
                    out = _insert_object(body["track"], after_song_id=after_song_id)
                elif body.get("id"):
                    out = engine.insert_song(
                        str(body["id"]), id_mode=True, after_song_id=after_song_id
                    )
                else:
                    song = str(body.get("song") or body.get("title") or "").strip()
                    if not song:
                        return self._reply({"ok": False, "err": "需要 song / id / track 字段"}, 400)
                    strategy = str(body.get("searchStrategy") or "first")
                    if strategy not in ("first", "classic"):
                        return self._reply({"ok": False, "err": "searchStrategy 只能是 first / classic"}, 400)
                    out = engine.insert_song(
                        song,
                        artist=str(body.get("artist") or ""),
                        search_strategy=strategy,
                        after_song_id=after_song_id,
                    )
        except Exception as e:
            out = {"ok": False, "err": str(e)}
        self._reply(out)


def _insert_object(track, after_song_id=None):
    """传完整歌曲对象直插 的『下一首播放』。"""
    if not engine.ensure_cdp():
        return {"ok": False, "err": "CDP 不可用"}
    c = CDP(first_page()["webSocketDebuggerUrl"])
    try:
        c.call("Runtime.enable")
        c.call("Page.enable")
        time.sleep(0.5)
        c.evaluate("window.__STORE__ = null")
        if not engine.find_store(c):
            return {"ok": False, "err": "未找到 store"}
        engine.install_mode_observer(c)
        mode_result = engine.ensure_order_mode(c)
        if not mode_result.get("ok"):
            return mode_result
        res = engine.insert_next(c, track, after_song_id=after_song_id)
        verified, around = False, None
        if res.get("ok"):
            verified, around = engine.verify_insert(
                c, res.get("songId"), after_song_id=after_song_id,
                expected_offset=res.get("offset")
            )
        return {**res, "playingMode": mode_result.get("playingMode"),
                "previousPlayingMode": mode_result.get("previousPlayingMode"),
                "playingModeChanged": bool(mode_result.get("changed")),
                "verified": bool(verified), "around": around}
    finally:
        try:
            c.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="网易云注入服务")
    ap.add_argument("--port", type=int, default=8866)
    args = ap.parse_args()

    # 预热：确保客户端调试口可用（首个请求也能启动）
    engine.ensure_cdp()

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[server] 网易云『下一首播放』注入服务：http://127.0.0.1:{args.port}  "
          f"(POST {{'song': '歌名'}} / {{'id': songId}} / {{'track': 完整对象}})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] 已停止", flush=True)


if __name__ == "__main__":
    main()
