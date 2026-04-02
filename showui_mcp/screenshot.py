"""
Screenshot capture utilities.
Captures the entire screen or a specific window by title.
"""
import ctypes
import ctypes.wintypes
import logging
import os
import tempfile
import time
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Win32 API constants
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
SW_RESTORE = 9
DWMWA_EXTENDED_FRAME_BOUNDS = 9

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi

# Make process DPI-aware for correct coordinates
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.wintypes.LONG),
        ("biHeight", ctypes.wintypes.LONG),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.wintypes.DWORD * 3),
    ]


def _find_window(title: str) -> int:
    """Find a window by partial title match. Returns HWND or 0."""
    result = []

    @ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            window_title = buf.value
            if title.lower() in window_title.lower():
                result.append(hwnd)
        return True

    user32.EnumWindows(enum_cb, 0)
    return result[0] if result else 0


def _get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Get window rect using DWM extended frame bounds (accurate with DPI scaling)."""
    rect = ctypes.wintypes.RECT()
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
    )
    if hr != 0:
        # Fallback to GetWindowRect
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def capture_screen(save_path: str | None = None) -> str:
    """Capture the entire primary screen. Returns path to saved PNG."""
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return _capture_region(0, 0, w, h, save_path)


def capture_window(title: str, save_path: str | None = None) -> dict:
    """
    Capture a specific window by title (partial match).
    Returns dict with path, window dimensions, and position.
    """
    hwnd = _find_window(title)
    if not hwnd:
        return {"success": False, "error": f"Window not found: '{title}'"}

    # Bring window to foreground
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)  # Brief wait for window to render

    left, top, right, bottom = _get_window_rect(hwnd)
    w, h = right - left, bottom - top

    if w <= 0 or h <= 0:
        return {"success": False, "error": f"Invalid window size: {w}x{h}"}

    path = _capture_region(left, top, w, h, save_path)
    return {
        "success": True,
        "path": path,
        "width": w,
        "height": h,
        "x": left,
        "y": top,
    }


def _capture_region(x: int, y: int, w: int, h: int, save_path: str | None = None) -> str:
    """Capture a screen region using Win32 GDI."""
    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)
    gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, SRCCOPY)

    # Read pixels
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

    # Cleanup GDI
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)

    # Convert BGRA -> RGB
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    img = img.convert("RGB")

    if save_path is None:
        save_path = os.path.join(tempfile.gettempdir(), f"showui_screenshot_{int(time.time())}.png")

    img.save(save_path, "PNG")
    logger.info("Screenshot saved: %s (%dx%d)", save_path, w, h)
    return save_path
