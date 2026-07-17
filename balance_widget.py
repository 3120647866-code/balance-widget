#!/usr/bin/env python3
"""
API Balance Desktop Widget — DeepSeek + 千问
磨玻璃质感 | 桌面右上角 | 最下层 | 开机自启
"""

import sys
import os
import json
import ctypes
import ctypes.wintypes
from ctypes import POINTER, Structure, c_int, c_bool, sizeof, byref, windll
from datetime import datetime
import threading
import traceback

import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QMenu, QGridLayout, QSizePolicy, QSpacerItem,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QAction, QCursor, QFontDatabase,
)

# ═══════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════
CONFIG = {
    "margin_right": 24,
    "margin_top": 24,
    "refresh_interval_ms": 30 * 1000,   # 每 30 秒刷新
    "widget_width": 268,
    "widget_height": 148,
}


# ═══════════════════════════════════════════════
#  Windows API
# ═══════════════════════════════════════════════
user32 = windll.user32
dwmapi = windll.dwmapi
kernel32 = windll.kernel32
shell32 = windll.shell32

# Monitor info
MONITOR_DEFAULTTONEAREST = 2

class RECT(Structure):
    _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]

class MONITORINFO(Structure):
    _fields_ = [("cbSize", c_int), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", c_int)]

# DWM attributes
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_MICA = 1029
DWMWA_WINDOW_CORNER_PREFERENCE = 33  # Win11 rounded corners

DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2
DWMSBT_ACRYLIC = 3
DWMSBT_TABBEDWINDOW = 4

# DWM corner preference
DWMWCP_ROUND = 2       # rounded corners
DWMWCP_ROUNDSMALL = 3  # small rounded corners

# Accent state
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLIC_BLUR = 4
ACCENT_ENABLE_GRADIENT = 2

class ACCENTPOLICY(Structure):
    _fields_ = [
        ("AccentState",  c_int),
        ("AccentFlags",  c_int),
        ("GradientColor", c_int),
        ("AnimationId",  c_int),
    ]

class WINDOWCOMPOSITIONATTRIBDATA(Structure):
    _fields_ = [
        ("Attribute",  c_int),
        ("Data",       POINTER(ACCENTPOLICY)),
        ("SizeOfData", c_int),
    ]

SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
SetWindowCompositionAttribute.argtypes = [c_int, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
SetWindowCompositionAttribute.restype = c_bool

WS_EX_LAYERED     = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW  = 0x00000080
WS_EX_NOACTIVATE  = 0x08000000
WS_EX_APPWINDOW   = 0x00040000
GWL_EXSTYLE       = -20

HWND_BOTTOM    = 1
HWND_TOPMOST   = -1
SWP_NOMOVE     = 0x0002
SWP_NOSIZE     = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER   = 0x0004


def apply_acrylic_backdrop(hwnd_int: int) -> bool:
    """Apply frosted glass: Win11 Mica → Win11 Acrylic → Win10 blur."""
    # ── Windows 11: try Mica first (lighter/whiter than Acrylic) ──
    try:
        result = dwmapi.DwmSetWindowAttribute(
            hwnd_int, DWMWA_SYSTEMBACKDROP_TYPE,
            byref(c_int(DWMSBT_MAINWINDOW)), sizeof(c_int)
        )
        if result == 0:
            return True
    except Exception:
        pass

    # ── Windows 11: try Acrylic ──
    try:
        result = dwmapi.DwmSetWindowAttribute(
            hwnd_int, DWMWA_SYSTEMBACKDROP_TYPE,
            byref(c_int(DWMSBT_ACRYLIC)), sizeof(c_int)
        )
        if result == 0:
            return True
    except Exception:
        pass

    # ── Windows 10: SetWindowCompositionAttribute with blur ──
    try:
        margins = c_int(-1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd_int, byref(margins))

        accent = ACCENTPOLICY()
        accent.AccentState = ACCENT_ENABLE_ACRYLIC_BLUR  # Win10 1803+ acrylic
        accent.AccentFlags = 2
        accent.GradientColor = 0xD0FFFFFF  # semi-transparent white (ABGR)
        accent.AnimationId = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = POINTER(ACCENTPOLICY)(accent)
        data.SizeOfData = sizeof(accent)

        SetWindowCompositionAttribute(hwnd_int, byref(data))

        # Also extend frame for DWM blur
        dwmapi.DwmExtendFrameIntoClientArea(hwnd_int, byref(margins))
        return True
    except Exception:
        pass

    return False


def pin_to_bottom(hwnd_int: int):
    """Force the window to the bottom of the Z-order."""
    user32.SetWindowPos(
        hwnd_int, HWND_BOTTOM,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    )


def get_work_area() -> QRect:
    """Get the work area of the primary monitor (excludes taskbar)."""
    monitor = user32.MonitorFromPoint(
        ctypes.wintypes.POINT(0, 0), MONITOR_DEFAULTTONEAREST
    )
    info = MONITORINFO()
    info.cbSize = sizeof(MONITORINFO)
    user32.GetMonitorInfoW(monitor, byref(info))
    rc = info.rcWork
    return QRect(rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)


# ═══════════════════════════════════════════════
#  API Helpers
# ═══════════════════════════════════════════════

def get_api_keys() -> dict:
    keys = {
        "deepseek": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "qwen":     os.environ.get("DASHSCOPE_API_KEY", ""),
    }
    settings_path = os.path.expanduser("~/.claude/settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            env = settings.get("env", {})
            if not keys["deepseek"]:
                keys["deepseek"] = env.get("ANTHROPIC_AUTH_TOKEN", "")
            if not keys["qwen"]:
                keys["qwen"] = env.get("DASHSCOPE_API_KEY", "")
        except Exception:
            pass
    return keys


def fetch_deepseek_balance(api_key: str) -> dict:
    try:
        resp = requests.get(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        data = resp.json()
        if data.get("is_available"):
            for info in data.get("balance_infos", []):
                if info.get("currency") == "CNY":
                    return {
                        "ok": True,
                        "total": float(info.get("total_balance", 0)),
                        "granted": float(info.get("granted_balance", 0)),
                        "topped_up": float(info.get("topped_up_balance", 0)),
                    }
        return {"ok": False, "error": f"API 返回异常: {resp.status_code}"}
    except requests.Timeout:
        return {"ok": False, "error": "请求超时"}
    except requests.ConnectionError:
        return {"ok": False, "error": "网络不通"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:40]}


def fetch_qwen_status(api_key: str) -> dict:
    try:
        resp = requests.get(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            model_count = len(data.get("data", []))
            return {"ok": True, "status": "正常", "models": model_count}
        elif resp.status_code in (401, 403):
            return {"ok": False, "error": "Key 失效"}
        elif resp.status_code == 429:
            return {"ok": False, "error": "请求过频"}
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except requests.Timeout:
        return {"ok": False, "error": "请求超时"}
    except requests.ConnectionError:
        return {"ok": False, "error": "网络不通"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:30]}


# ═══════════════════════════════════════════════
#  Main Widget
# ═══════════════════════════════════════════════

class BalanceWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.api_keys = get_api_keys()
        self.ds_data: dict = {"ok": False, "error": "加载中..."}
        self.qw_data: dict = {"ok": False, "error": "加载中..."}
        self._drag_pos: QPoint | None = None

        self._setup_window()
        self._setup_ui()
        self._apply_backdrop()
        self._position_window()
        self._pin_bottom()

        # 定时刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_all)
        self._timer.start(CONFIG["refresh_interval_ms"])

        # 首次立即刷新
        self._refresh_all()

        # 每 30 秒重新置底（防止被其他窗口行为挤出）
        self._pin_timer = QTimer(self)
        self._pin_timer.timeout.connect(self._pin_bottom)
        self._pin_timer.start(30_000)

    # ── Window setup ──────────────────────────

    def _setup_window(self):
        self.setWindowTitle("API 余额")
        self.setFixedSize(CONFIG["widget_width"], CONFIG["widget_height"])

        # 无边框 + 置底 + 无任务栏图标
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )

        # 确保不在任务栏显示、不接受焦点
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        # 窗口置顶策略
        hwnd = int(self.winId())
        try:
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            ex_style &= ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        except Exception:
            pass

    # ── Acrylic backdrop ─────────────────────

    def _apply_backdrop(self):
        hwnd = int(self.winId())

        # Win11 smooth rounded corners via DWM
        try:
            dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(c_int(DWMWCP_ROUND)), sizeof(c_int)
            )
        except Exception:
            pass

        success = apply_acrylic_backdrop(hwnd)
        if success:
            # 纯白磨玻璃：高不透明白底叠加背景模糊
            self.setStyleSheet("""
                BalanceWidget {
                    background-color: rgba(255, 255, 255, 0.82);
                    border-radius: 20px;
                    border: 1px solid rgba(255, 255, 255, 0.60);
                }
            """)
        else:
            # 无法启用磨玻璃时用纯白不透明降级
            self.setStyleSheet("""
                BalanceWidget {
                    background-color: rgba(255, 255, 255, 0.95);
                    border-radius: 20px;
                    border: 1px solid rgba(0, 0, 0, 0.06);
                }
            """)

    # ── Position ─────────────────────────────

    def _position_window(self):
        work = get_work_area()
        x = work.right() - CONFIG["widget_width"] - CONFIG["margin_right"]
        y = work.top() + CONFIG["margin_top"]
        self.move(x, y)

    def _pin_bottom(self):
        try:
            pin_to_bottom(int(self.winId()))
        except Exception:
            pass

    # ── UI ───────────────────────────────────

    def _setup_ui(self):
        # 主布局
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 14)
        root.setSpacing(0)

        # ── 标题行 ──
        title = QLabel("🔮  API 余额")
        title.setObjectName("title")
        root.addWidget(title)

        # ── 分隔线 ──
        sep = QLabel()
        sep.setObjectName("sep")
        sep.setFixedHeight(1)
        sep.setMaximumHeight(1)
        root.addSpacing(10)
        root.addWidget(sep)
        root.addSpacing(12)

        # ── DeepSeek 行 ──
        self.ds_label = self._make_row("DeepSeek", "—")
        root.addWidget(self.ds_label)
        root.addSpacing(8)

        # ── 千问 行 ──
        self.qw_label = self._make_row("千 问", "—")
        root.addWidget(self.qw_label)
        root.addSpacing(12)

        # ── 刷新时间 ──
        self.time_label = QLabel("")
        self.time_label.setObjectName("time")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.time_label)

        # ── 字体 ──
        self._apply_fonts()

        # ── 右键菜单 ──
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _apply_fonts(self):
        """设置美观中文字体。"""
        # 优先使用系统自带的好看字体
        families = [
            "Microsoft YaHei UI",   # Win11 优化版微软雅黑
            "Microsoft YaHei",
            "PingFang SC",
            "Noto Sans SC",
            "Segoe UI",
        ]
        available = QFontDatabase.families()
        chosen = next((f for f in families if f in available), families[-1])

        title_font = QFont(chosen, 13, QFont.Weight.DemiBold)
        row_font   = QFont(chosen, 11)
        time_font  = QFont(chosen, 9)
        value_font = QFont(chosen, 11, QFont.Weight.Medium)

        # Apply
        title = self.findChild(QLabel, "title")
        if title:
            title.setFont(title_font)
            title.setStyleSheet("color: #0f172a; letter-spacing: 0.5px;")

        sep = self.findChild(QLabel, "sep")
        if sep:
            sep.setStyleSheet(
                "background-color: rgba(0, 0, 0, 0.08);"
            )

        time_label = self.findChild(QLabel, "time")
        if time_label:
            time_label.setFont(time_font)
            time_label.setStyleSheet("color: #64748b;")

        self._row_font = row_font
        self._value_font = value_font

    def _make_row(self, name: str, value_text: str) -> QLabel:
        """Create a rich-text label for one provider row."""
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(self._row_html(name, value_text, "#94a3b8"))
        label.setObjectName(f"row_{name}")
        return label

    @staticmethod
    def _row_html(name: str, value: str, color: str) -> str:
        return (
            f'<span style="font-size:12px;color:#334155;font-weight:600;">{name}'
            f'</span>'
            f'<span style="float:right;font-size:13px;color:{color};font-weight:700;">'
            f'{value}</span>'
        )

    # ── Data refresh ─────────────────────────

    def _refresh_all(self):
        keys = get_api_keys()
        # 如果 env 变动了也更新
        self.api_keys = keys

        # 并行请求
        results = {}
        threads = []

        def _fetch(name, fn, key):
            try:
                results[name] = fn(key)
            except Exception:
                results[name] = {"ok": False, "error": "异常"}

        if keys.get("deepseek"):
            t = threading.Thread(target=_fetch, args=("deepseek", fetch_deepseek_balance, keys["deepseek"]))
            threads.append(t)
        if keys.get("qwen"):
            t = threading.Thread(target=_fetch, args=("qwen", fetch_qwen_status, keys["qwen"]))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        if "deepseek" in results:
            self.ds_data = results["deepseek"]
        else:
            self.ds_data = {"ok": False, "error": "未配置 Key"}

        if "qwen" in results:
            self.qw_data = results["qwen"]
        else:
            self.qw_data = {"ok": False, "error": "未配置 Key"}

        self._update_display()

    def _update_display(self):
        # DeepSeek
        if self.ds_data.get("ok"):
            total = self.ds_data["total"]
            self.ds_label.setText(
                self._row_html("DeepSeek", f"¥{total:.2f}", "#0d9488")
            )
        else:
            err = self.ds_data.get("error", "未知错误")
            self.ds_label.setText(
                self._row_html("DeepSeek", err, "#e11d48")
            )

        # Qwen
        if self.qw_data.get("ok"):
            self.qw_label.setText(
                self._row_html("千 问", "API 正常 ✓", "#0d9488")
            )
        else:
            err = self.qw_data.get("error", "未知错误")
            self.qw_label.setText(
                self._row_html("千 问", err, "#e11d48")
            )

        # 刷新时间
        now = datetime.now().strftime("刷新 %H:%M:%S")
        self.time_label.setText(now)

    # ── Right-click menu ────────────────────

    def _show_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(255,255,255,0.92);
                border: 1px solid rgba(0,0,0,0.08);
                border-radius: 8px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 28px 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(0,0,0,0.06);
            }
        """)

        refresh_action = menu.addAction("🔄  立即刷新")
        refresh_action.triggered.connect(self._refresh_all)

        menu.addSeparator()

        exit_action = menu.addAction("✕  退出")
        exit_action.triggered.connect(QApplication.quit)

        menu.exec(self.mapToGlobal(pos))

    # ── Drag support ────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── No custom paint — stylesheet + DWM acrylic handles the backdrop ──


# ═══════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════

def main():
    # 确保任务栏图标不显示
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BalanceWidget")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # 全局字体回退
    app.setStyleSheet("""
        * {
            font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
        }
    """)

    widget = BalanceWidget()
    widget.show()

    # 显示后立即置底一次
    QTimer.singleShot(100, widget._pin_bottom)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
