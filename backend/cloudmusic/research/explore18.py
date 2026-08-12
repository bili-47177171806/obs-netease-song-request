# -*- coding: utf-8 -*-
"""dump 当前整页文本与 URL，弄清界面状态。"""
import sys
import base64
import json
from backend.cloudmusic.cdp import CDP, first_page


def main():
    c = CDP(first_page()["webSocketDebuggerUrl"])
    c.call("Runtime.enable")

    r = c.evaluate(r"({ href: location.href, title: document.title, text: document.body.innerText })")
    print("URL:", r["href"])
    print("TITLE:", r["title"])
    print("---- 全文 ----")
    print(r["text"])

    # JPEG 截屏（可能可读）
    shot = c.call("Page.captureScreenshot", {"format": "jpeg", "quality": 70, "captureBeyondViewport": False})
    with open("state_preview.jpeg", "wb") as f:
        f.write(base64.b64decode(shot["result"]["data"]))
    print("\n截图:", "state_preview.jpeg")

    c.close()


if __name__ == "__main__":
    sys.exit(main())