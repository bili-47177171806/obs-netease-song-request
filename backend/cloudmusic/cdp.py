# -*- coding: utf-8 -*-
"""极简 CDP (Chrome DevTools Protocol) 客户端，用于驱动网易云音乐 PC 客户端。
用法见同目录其他脚本；主要暴露 CDP 类与 list_pages()。
"""
import json
import threading
import time
import urllib.request
import websocket  # websocket-client


def list_pages(port=9222):
    """返回 http://127.0.0.1:9222/json 里的 page 目标列表（dict list）。"""
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as r:
        return json.load(r)


def first_page(port=9222):
    """取第一个 type=='page' 的目标；找不到则抛错。"""
    for t in list_pages(port):
        if t.get("type") == "page":
            return t
    raise RuntimeError(f"port {port} 上没有 page 目标")


class CDP:
    def __init__(self, ws_url, timeout=60):
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self._mid = 0
        self._resp = {}
        self._lock = threading.Lock()
        self._events = []
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                break
            if "id" in msg:
                self._resp[msg["id"]] = msg
            else:
                self._events.append(msg)

    def call(self, method, params=None, timeout=30):
        with self._lock:
            self._mid += 1
            mid = self._mid
            self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if mid in self._resp:
                return self._resp.pop(mid)
            time.sleep(0.02)
        raise TimeoutError(method)

    def evaluate(self, expr, await_promise=False):
        """求值 JS，返回返回值的 JSON 值；JS 抛错时返回带 'error' 的 dict。"""
        r = self.call("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
        })
        res = r.get("result", {})
        if "exceptionDetails" in res:
            return {"error": res["exceptionDetails"].get("text",
                    str(res["exceptionDetails"].get("exception", {}))[:300]),
                    "result": res.get("result", {}).get("value")}
        return res.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass