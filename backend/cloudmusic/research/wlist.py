# -*- coding: utf-8 -*-
"""列出 cloudmusic 进程的所有顶层窗口（handle/class/title/rect）——用于确认原生菜单弹窗。"""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EnumWindows = user32.EnumWindows
EnumWindows.restype = wt.BOOL
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.restype = wt.DWORD
GetClassNameW = user32.GetClassNameW
GetWindowTextW = user32.GetWindowTextW
GetWindowRect = user32.GetWindowRect
IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.restype = wt.BOOL
GetAncestor = user32.GetAncestor
GW_OWNER = 4
OpenProcess = kernel32.OpenProcess
OpenProcess.restype = wt.HANDLE
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

rows = []
@EnumWindowsProc
def cb(hwnd, lparam):
    pid = wt.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    rows.append((hwnd, pid.value))
    return True
EnumWindows(cb, 0)

def exe_name(pid):
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        sz = wt.DWORD(1024)
        ok = QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
        return buf.value.split("\\")[-1] if ok else None
    finally:
        kernel32.CloseHandle(h)

cloud_wins = []
for hwnd, pid in rows:
    name = exe_name(pid)
    if name not in ("cloudmusic.exe", "cloudmusic_reporter.exe"):
        continue
    cls = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, cls, 256)
    title = ctypes.create_unicode_buffer(512)
    GetWindowTextW(hwnd, title, 512)
    r = wt.RECT()
    GetWindowRect(hwnd, ctypes.byref(r))
    owner = GetAncestor(hwnd, GW_OWNER)
    cloud_wins.append({
        "pid": pid, "hwnd": hwnd, "cls": cls.value[:44], "title": title.value[:70],
        "rect": (r.left, r.top, r.right, r.bottom), "vis": bool(IsWindowVisible(hwnd)), "owner": owner,
    })

cloud_wins.sort(key=lambda w: (w["pid"], w["rect"][1]))
for w in cloud_wins:
    print(f"pid={w['pid']:<6} hwnd=0x{w['hwnd']:x} vis={int(w['vis'])} owner=0x{w['owner']:x} "
          f"cls={w['cls']:<36} rect={w['rect']} title={w['title']!r}")
print(f"--- total {len(cloud_wins)} windows ---")