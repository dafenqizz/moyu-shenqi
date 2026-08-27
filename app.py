import json
import os
import sys
import time
from pathlib import Path

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPixmap, QWindow
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

if sys.platform != "win32":
    raise SystemExit("This app is designed for Windows.")


APP_NAME = "MoyuAdMask"
ORGANIZATION = "MYSQ"
STATE_FILE = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME / "state.json"
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DEFAULT_AD_IMAGES = [
    RESOURCE_DIR / "assets" / "default_ad_1.png",
    RESOURCE_DIR / "assets" / "default_ad_2.png",
    RESOURCE_DIR / "assets" / "default_ad_3.png",
]
HOTKEY_ID_TOGGLE = 1
HOTKEY_ID_ESCAPE = 2
WM_HOTKEY = 0x0312
WM_NCHITTEST = 0x0084
WM_CLOSE = 0x0010
HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_ESCAPE = 0x1B
VK_M = 0x4D
VK_LBUTTON = 0x01
GA_ROOT = 2
BLOCKED_WINDOW_CLASSES = {
    "Progman",          # 桌面背景
    "WorkerW",          # 桌面图标层
    "Shell_TrayWnd",    # 任务栏
    "TrayNotifyWnd",    # 系统托盘
}
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000

user32 = ctypes.windll.user32


def ensure_state_dir():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state():
    ensure_state_dir()
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(data):
    ensure_state_dir()
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_demo_pixmap():
    pix = QPixmap(88, 88)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, 88, 88, 14, 14)
    p.setClipPath(path)
    p.fillRect(pix.rect(), QColor("#ff6a3d"))
    p.setPen(Qt.white)
    p.drawText(pix.rect(), Qt.AlignCenter, "商品图\n占位")
    p.end()
    return pix


class TitleButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(18, 18)
        self.setStyleSheet(
            """
            QPushButton {
                border: none;
                color: white;
                background: transparent;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #d9363e;
                border-radius: 3px;
            }
            """
        )


class ScalableAdLabel(QLabel):
    """不把原图尺寸反馈给布局，允许广告区缩小到很小。"""
    def minimumSizeHint(self):
        return QSize(1, 1)

    def sizeHint(self):
        return QSize(1, 1)


class AdView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = list(DEFAULT_AD_IMAGES)
        self.image_index = 0
        self.current_pixmap = QPixmap()
        self.setup_ui()

        self.rotate_timer = QTimer(self)
        self.rotate_timer.timeout.connect(self.rotate_ad)
        self.rotate_timer.start(3000)

        self.rotate_ad()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background: #111111;")
        self.image_label = ScalableAdLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(0, 0)
        self.image_label.setStyleSheet("background:#111111; color:#777;")
        outer.addWidget(self.image_label)

    def rotate_ad(self):
        if not self.image_paths:
            return
        self.current_pixmap = QPixmap(str(self.image_paths[self.image_index % len(self.image_paths)]))
        self.image_index = (self.image_index + 1) % len(self.image_paths)
        self.update_image()

    def set_images(self, paths):
        valid = [Path(path) for path in paths if QPixmap(str(path)).isNull() is False]
        if valid:
            self.image_paths = valid[:3]
            self.image_index = 0
            self.rotate_ad()

    def update_image(self):
        if self.current_pixmap.isNull():
            self.image_label.setText("未找到广告图片")
            return
        scaled = self.current_pixmap.scaled(
            self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()


class ResizeHandle(QWidget):
    """覆盖在外部窗口边缘的缩放热区，避免外部窗口吃掉鼠标事件。"""
    def __init__(self, owner, edge):
        super().__init__(owner)
        self.owner = owner
        self.edge = edge
        self.setMouseTracking(True)
        self.setCursor(Qt.SizeHorCursor if edge in (1, 2) else Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.owner.begin_handle_resize(self.edge, event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self.owner.handle_resizing:
            self.owner.move_handle_resize(event.globalPosition().toPoint())
            event.accept()

    def mouseReleaseEvent(self, event):
        self.owner.end_handle_resize()
        event.accept()


class ExternalWindowView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setStyleSheet("background: #202020;")
        self.target_hwnd = None
        self.embedded_window = None
        self.container = None
        self.selecting = False
        self.was_left_down = False
        self.handle_resizing = False
        self.handle_start = QPoint()
        self.handle_origin = QRect()
        self.handle_edge = 0

        self.prompt = QLabel("拖入一个视频软件或浏览器窗口")
        self.prompt.setAlignment(Qt.AlignCenter)
        self.prompt.setStyleSheet("color: #d5d5d5; font-size: 16px; font-weight: 700;")
        self.drop_hint = QLabel("按住下面按钮，然后把鼠标拖到目标窗口并松开")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        self.drop_hint.setStyleSheet("color: #858585; font-size: 12px;")
        self.pick_button = QPushButton("拖拽选择窗口")
        self.pick_button.setCursor(Qt.PointingHandCursor)
        self.pick_button.setStyleSheet(
            "QPushButton { background:#d9ad2b; color:#171717; border:0; border-radius:5px; padding:10px 22px; font-weight:700; }"
            "QPushButton:hover { background:#f0c83b; }"
        )
        self.pick_button.clicked.connect(self.begin_select)
        self.clear_button = QPushButton("清除当前窗口", self)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setStyleSheet(
            "QPushButton { background:#9b302c; color:#fff; border:0; border-radius:4px; padding:5px 9px; }"
            "QPushButton:hover { background:#c33b35; }"
        )
        self.clear_button.clicked.connect(self.clear_target)
        self.clear_button.hide()
        self.left_handle = ResizeHandle(self, 1)
        self.right_handle = ResizeHandle(self, 2)
        self.bottom_handle = ResizeHandle(self, 8)
        self.left_handle.hide()
        self.right_handle.hide()
        self.bottom_handle.hide()
        layout.addStretch(1)
        layout.addWidget(self.prompt)
        layout.addWidget(self.drop_hint)
        layout.addWidget(self.pick_button, 0, Qt.AlignHCenter)
        layout.addStretch(1)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_selection)

    def begin_select(self):
        self.selecting = True
        self.was_left_down = False
        self.prompt.setText("正在选择窗口...")
        self.drop_hint.setText("按住鼠标左键拖到目标窗口，松开后自动接入")
        self.pick_button.setEnabled(False)
        self.poll_timer.start(30)

    def poll_selection(self):
        left_down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        if left_down:
            self.was_left_down = True
            return
        if not self.was_left_down:
            return
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        hwnd = int(user32.WindowFromPoint(point))
        hwnd = int(user32.GetAncestor(hwnd, GA_ROOT))
        own = int(self.window().winId())
        if self.is_safe_target(hwnd, own):
            self.embed_window(hwnd)
        self.selecting = False
        self.poll_timer.stop()
        self.pick_button.setEnabled(True)

    @staticmethod
    def is_safe_target(hwnd, own):
        if not hwnd or hwnd == own or user32.IsChild(own, hwnd):
            return False
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        if class_name.value in BLOCKED_WINDOW_CLASSES:
            return False
        return bool(user32.IsWindowVisible(hwnd))

    def embed_window(self, hwnd):
        if self.target_hwnd:
            self.restore_window()
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        self.original_style = style
        self.original_parent = int(user32.GetParent(hwnd))
        user32.SetParent(hwnd, int(self.winId()))
        user32.SetWindowLongW(hwnd, GWL_STYLE, (style | WS_CHILD) & ~WS_POPUP)
        self.target_hwnd = hwnd
        self.embedded_window = QWindow.fromWinId(hwnd)
        container = QWidget.createWindowContainer(self.embedded_window, self)
        container.setFocusPolicy(Qt.StrongFocus)
        self.layout().addWidget(container)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setStretch(self.layout().count() - 1, 1)
        self.container = container
        self.prompt.hide()
        self.drop_hint.hide()
        self.pick_button.hide()
        self.clear_button.show()
        self.left_handle.show()
        self.right_handle.show()
        self.bottom_handle.show()
        self.raise_resize_controls()

    def raise_resize_controls(self):
        for control in (self.clear_button, self.left_handle, self.right_handle, self.bottom_handle):
            control.raise_()
        self.position_resize_controls()

    def position_resize_controls(self):
        if not self.container:
            return
        margin = 9
        self.left_handle.setGeometry(0, 28, margin, max(1, self.height() - 28 - margin))
        self.right_handle.setGeometry(self.width() - margin, 28, margin, max(1, self.height() - 28 - margin))
        self.bottom_handle.setGeometry(margin, self.height() - margin, max(1, self.width() - 2 * margin), margin)
        self.clear_button.adjustSize()
        self.clear_button.move(self.width() - self.clear_button.width() - 14, 10)

    def begin_handle_resize(self, edge, global_pos):
        self.handle_resizing = True
        self.handle_edge = edge
        self.handle_start = global_pos
        self.handle_origin = self.window().geometry()

    def move_handle_resize(self, global_pos):
        if not self.handle_resizing:
            return
        delta = global_pos - self.handle_start
        rect = QRect(self.handle_origin)
        minimum = self.window().min_size
        if self.handle_edge == 1:
            rect.setLeft(min(rect.right() - minimum.width() + 1, rect.left() + delta.x()))
        elif self.handle_edge == 2:
            rect.setWidth(max(minimum.width(), rect.width() + delta.x()))
        elif self.handle_edge == 8:
            rect.setHeight(max(minimum.height(), rect.height() + delta.y()))
        self.window().setGeometry(rect)

    def end_handle_resize(self):
        if self.handle_resizing:
            self.handle_resizing = False
            self.window().save_window_state()

    def clear_target(self):
        self.restore_window()
        self.layout().setContentsMargins(18, 18, 18, 18)
        self.prompt.setText("拖入一个视频软件或浏览器窗口")
        self.drop_hint.setText("按住下面按钮，然后把鼠标拖到目标窗口并松开")
        self.prompt.show()
        self.drop_hint.show()
        self.pick_button.show()
        self.clear_button.hide()
        self.left_handle.hide()
        self.right_handle.hide()
        self.bottom_handle.hide()

    def restore_embedded_geometry(self):
        """模式切换或从托盘恢复后，保持接入窗口填满当前区域。"""
        if self.container:
            self.container.setGeometry(self.rect())
            self.raise_resize_controls()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.restore_embedded_geometry)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.restore_embedded_geometry()
        self.position_resize_controls()

    def restore_window(self):
        if self.target_hwnd:
            user32.SetParent(self.target_hwnd, self.original_parent)
            user32.SetWindowLongW(self.target_hwnd, GWL_STYLE, self.original_style)
            user32.ShowWindow(self.target_hwnd, 5)
        if self.container:
            self.container.deleteLater()
        self.target_hwnd = None
        self.embedded_window = None
        self.container = None

    def close_target(self):
        if self.target_hwnd:
            user32.PostMessageW(self.target_hwnd, WM_CLOSE, 0, 0)
            self.target_hwnd = None

    def has_target(self):
        return bool(self.target_hwnd)


class FloatingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = load_state()
        self.mode = self.state.get("mode", "ad")
        self.custom_ad_images = self.state.get("custom_ad_images", [])
        # 广告和视频分别保存几何信息，切换模式不会覆盖用户刚调好的尺寸。
        self.mode_geometries = self.state.get("mode_geometries", {})
        self.dragging = False
        self.resizing = False
        self.resize_edges = 0
        self.resize_start_pos = QPoint()
        self.drag_offset = QPoint()
        self.resize_origin = QRect()
        self.resize_margin = 8
        # 不是固定窗口尺寸，只限制到一个不会让控件完全挤坏的最小值。
        self.min_size = QSize(120, 70)
        self.setMinimumSize(self.min_size)
        self.setWindowTitle("Moyu Mask")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._build_ui()
        self._apply_style()
        if self.custom_ad_images:
            self.ad_view.set_images(self.custom_ad_images)
        QApplication.instance().installEventFilter(self)
        self._restore_geometry()
        self._create_tray()
        self._register_hotkeys()
        self.show()

    def _begin_drag(self, global_pos):
        self.dragging = True
        self.drag_offset = global_pos - self.frameGeometry().topLeft()

    def _end_drag(self):
        self.dragging = False
        self.resizing = False
        self.save_window_state()

    def _build_ui(self):
        root = QFrame()
        root.setObjectName("RootFrame")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.titlebar = QFrame()
        self.titlebar.setFixedHeight(26)
        self.titlebar.setStyleSheet("background: #191919;")
        self.titlebar.setMouseTracking(True)
        self.titlebar.installEventFilter(self)
        title_layout = QHBoxLayout(self.titlebar)
        title_layout.setContentsMargins(4, 0, 4, 0)
        title_layout.setSpacing(2)

        self.mode_tag = QPushButton("广告")
        self.mode_tag.setCursor(Qt.PointingHandCursor)
        self.mode_tag.setFixedSize(32, 18)
        self.mode_tag.setStyleSheet(
            """
            QPushButton {
                background: #ffd633;
                color: #1a1a1a;
                border: none;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover { background: #ffe15d; }
            """
        )
        self.mode_tag.clicked.connect(self.toggle_mode)

        self.image_btn = QPushButton("图")
        self.image_btn.setCursor(Qt.PointingHandCursor)
        self.image_btn.setFixedSize(16, 18)
        self.image_btn.setStyleSheet(
            "QPushButton { color:#777; background:transparent; border:0; font-size:10px; }"
            "QPushButton:hover { color:#d9ad2b; background:#292929; border-radius:3px; }"
        )
        self.image_btn.clicked.connect(self.choose_ad_images)

        self.tagline = QLabel("限时清仓，手慢无")
        self.tagline.setStyleSheet("color: #b6b6b6; font-size: 11px;")
        self.tagline.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.min_btn = TitleButton("-")
        self.close_btn = TitleButton("X")
        self.min_btn.clicked.connect(self.hide_to_tray)
        self.close_btn.clicked.connect(self.close_requested)

        title_layout.addWidget(self.mode_tag)
        title_layout.addWidget(self.image_btn)
        title_layout.addWidget(self.tagline, 1)
        title_layout.addWidget(self.min_btn)
        title_layout.addWidget(self.close_btn)

        self.stack = QStackedWidget()
        self.stack.setMinimumSize(0, 0)
        self.stack.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.ad_view = AdView()
        self.browser_view = ExternalWindowView()
        self.stack.addWidget(self.ad_view)
        self.stack.addWidget(self.browser_view)

        root_layout.addWidget(self.titlebar)
        root_layout.addWidget(self.stack, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        root.setGraphicsEffect(shadow)
        self.setCentralWidget(root)

        self.taglines = [
            "今晚补贴力度拉满",
            "新款上架，先到先得",
            "活动火热进行中",
            "限量发售，立即参与",
        ]
        self.tag_timer = QTimer(self)
        self.tag_timer.timeout.connect(self.rotate_tagline)
        self.tag_timer.start(20000)

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow { background: transparent; }
            QFrame#RootFrame {
                background: #252525;
                border: 1px solid #101010;
                border-radius: 10px;
            }
            """
        )

    def _restore_geometry(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        saved = self.mode_geometries.get(self.mode, {})
        w = int(saved.get("width", self.state.get("width", 380)))
        h = int(saved.get("height", self.state.get("height", 320)))
        # 旧版本没有分模式尺寸；进入视频模式时给一次适合网页浏览的初始尺寸。
        if self.mode == "video" and not saved and w < 420:
            w, h = 520, 760
        w = max(self.min_size.width(), w)
        h = max(self.min_size.height(), h)
        x = saved.get("x", self.state.get("x"))
        y = saved.get("y", self.state.get("y"))
        if x is None or y is None:
            x = screen.right() - w - 20
            y = screen.bottom() - h - 20
        self.setGeometry(int(x), int(y), w, h)
        self._clamp_to_screen()
        self.switch_mode(self.mode, initial=True)

    def _create_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._tray_icon())
        self.tray.setToolTip("摸鱼神器")

        menu = QMenu()
        act_show = QAction("显示窗口", self)
        act_toggle = QAction("切换广告/视频模式", self)
        act_exit = QAction("退出程序", self)
        act_show.triggered.connect(self.show_from_tray)
        act_toggle.triggered.connect(self.toggle_mode)
        act_exit.triggered.connect(self.quit_app)
        menu.addAction(act_show)
        menu.addAction(act_toggle)
        menu.addSeparator()
        menu.addAction(act_exit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_icon(self):
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#ffcf33"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(8, 8, 48, 48)
        p.setPen(QColor("#191919"))
        p.drawText(pix.rect(), Qt.AlignCenter, "广")
        p.end()
        return QIcon(pix)

    def _register_hotkeys(self):
        self._unregister_hotkeys()
        user32.RegisterHotKey(int(self.winId()), HOTKEY_ID_TOGGLE, MOD_CONTROL | MOD_ALT, VK_M)
        user32.RegisterHotKey(int(self.winId()), HOTKEY_ID_ESCAPE, 0, VK_ESCAPE)

    def _unregister_hotkeys(self):
        try:
            user32.UnregisterHotKey(int(self.winId()), HOTKEY_ID_TOGGLE)
        except Exception:
            pass
        try:
            user32.UnregisterHotKey(int(self.winId()), HOTKEY_ID_ESCAPE)
        except Exception:
            pass

    def nativeEvent(self, eventType, message):
        if eventType == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                # 无边框窗口交给 Windows 原生处理左右下三边及下方两角缩放。
                # 顶部始终是标题栏拖拽区，不参与缩放。
                point = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(point))
                user32.ScreenToClient(int(self.winId()), ctypes.byref(point))
                margin = 8
                in_titlebar = point.y < 28
                in_bottom = point.y >= self.height() - margin
                in_left = point.x <= margin
                in_right = point.x >= self.width() - margin
                if not in_titlebar and in_bottom and in_left:
                    return True, HTBOTTOMLEFT
                if not in_titlebar and in_bottom and in_right:
                    return True, HTBOTTOMRIGHT
                if not in_titlebar and in_left:
                    return True, HTLEFT
                if not in_titlebar and in_right:
                    return True, HTRIGHT
                if not in_titlebar and in_bottom:
                    return True, HTBOTTOM
                return True, HTCLIENT
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_ID_TOGGLE:
                    self.toggle_visible()
                elif msg.wParam == HOTKEY_ID_ESCAPE:
                    self.handle_escape()
                return True, 0
        return super().nativeEvent(eventType, message)

    def handle_escape(self):
        if self.mode != "ad":
            self.switch_mode("ad")
        elif self.isVisible() and not self.isMinimized():
            self.hide_to_tray()
        else:
            self.show_from_tray()

    def toggle_visible(self):
        if self.isVisible() and not self.isMinimized():
            self.hide_to_tray()
        else:
            self.show_from_tray()

    def close_requested(self):
        # 关闭按钮只隐藏主程序，不关闭或重置已接入的视频窗口。
        self.hide_to_tray()

    def hide_to_tray(self):
        self.save_window_state()
        self.hide()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._clamp_to_screen()

    def quit_app(self):
        self.save_window_state()
        self.browser_view.restore_window()
        self._unregister_hotkeys()
        self.tray.hide()
        QApplication.quit()

    def save_window_state(self):
        geo = self.geometry()
        self.mode_geometries[self.mode] = {
            "x": geo.x(),
            "y": geo.y(),
            "width": geo.width(),
            "height": geo.height(),
        }
        # 保留顶层字段，兼容旧版本状态文件。
        save_state(
            {
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height(),
                "mode": self.mode,
                "mode_geometries": self.mode_geometries,
                "custom_ad_images": self.custom_ad_images,
            }
        )

    def choose_ad_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择广告图片（最多三张）",
            str(Path.home()),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not paths:
            return
        self.custom_ad_images = paths[:3]
        self.ad_view.set_images(self.custom_ad_images)
        self.save_window_state()

    def rotate_tagline(self):
        self.tagline.setText(self.taglines[int(time.time() / 20) % len(self.taglines)])

    def switch_mode(self, mode, initial=False):
        if not initial:
            # 先保存当前模式，避免切换时丢掉用户手动调整的尺寸。
            self.save_window_state()
        self.mode = mode
        self.stack.setCurrentIndex(0 if mode == "ad" else 1)
        self.mode_tag.setText("广告" if mode == "ad" else "视频")
        if mode == "ad":
            self.tagline.show()
            self.tagline.setText("限时清仓，手慢无")
        else:
            self.tagline.setText("抖音网页版浏览模式")
            QTimer.singleShot(0, self.browser_view.restore_embedded_geometry)
        if not initial:
            self.save_window_state()

    def toggle_mode(self):
        self.switch_mode("video" if self.mode == "ad" else "ad")

    def _clamp_to_screen(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if not screen:
            return
        avail = screen.availableGeometry()
        geo = self.geometry()
        x = max(avail.left(), min(geo.x(), avail.right() - geo.width() + 1))
        y = max(avail.top(), min(geo.y(), avail.bottom() - geo.height() + 1))
        if x != geo.x() or y != geo.y():
            super().move(x, y)

    def _in_resize_zone(self, pos):
        return self._resize_edges(pos) != 0

    def _resize_edges(self, pos):
        """返回靠近的边：左1、右2、上4、下8，支持四边和四角。"""
        edge = 0
        if pos.x() <= self.resize_margin:
            edge |= 1
        if pos.x() >= self.width() - self.resize_margin:
            edge |= 2
        if pos.y() <= self.resize_margin:
            edge |= 4
        if pos.y() >= self.height() - self.resize_margin:
            edge |= 8
        # 右上角的关闭按钮区域优先留给按钮，不启动缩放。
        if pos.y() < 28 and pos.x() > self.width() - 65:
            return 0
        return edge

    def _resize_cursor(self, edges):
        if edges in (1 | 8, 2 | 4):
            return Qt.SizeBDiagCursor
        if edges in (1 | 4, 2 | 8):
            return Qt.SizeFDiagCursor
        if edges in (1, 2):
            return Qt.SizeHorCursor
        if edges in (4, 8):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def _resize_from_mouse(self, global_pos):
        delta = global_pos - self.resize_start_pos
        rect = QRect(self.resize_origin)
        edges = self.resize_edges
        if edges & 1:
            new_left = min(rect.right() - self.min_size.width() + 1, rect.left() + delta.x())
            rect.setLeft(new_left)
        if edges & 2:
            rect.setWidth(max(self.min_size.width(), self.resize_origin.width() + delta.x()))
        if edges & 4:
            new_top = min(rect.bottom() - self.min_size.height() + 1, rect.top() + delta.y())
            rect.setTop(new_top)
        if edges & 8:
            rect.setHeight(max(self.min_size.height(), self.resize_origin.height() + delta.y()))
        self.setGeometry(rect)
        self._clamp_to_screen()

    def eventFilter(self, obj, event):
        # QApplication 级过滤器让网页子控件边缘也能触发窗口缩放。
        if obj is QApplication.instance() and event.type() in (
            QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease
        ):
            pos = event.globalPosition().toPoint()
            local = self.mapFromGlobal(pos)
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                edges = self._resize_edges(local)
                if edges:
                    self.resizing = True
                    self.resize_edges = edges
                    self.resize_start_pos = pos
                    self.resize_origin = self.geometry()
                    return True
            elif event.type() == QEvent.MouseMove:
                if self.resizing:
                    self._resize_from_mouse(pos)
                    return True
                if self.isVisible():
                    self.setCursor(self._resize_cursor(self._resize_edges(local)))
            elif event.type() == QEvent.MouseButtonRelease and self.resizing:
                self.resizing = False
                self.resize_edges = 0
                self.save_window_state()
                return True
        if obj in {self.titlebar}:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._begin_drag(event.globalPosition().toPoint())
                return True
            if event.type() == QEvent.MouseMove and self.dragging:
                self.move(event.globalPosition().toPoint() - self.drag_offset)
                return True
            if event.type() == QEvent.MouseButtonRelease:
                self._end_drag()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if self._in_resize_zone(pos):
                self.resizing = True
                self.drag_offset = event.globalPosition().toPoint()
                self.resize_origin = self.geometry()
            else:
                self.dragging = True
                self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.globalPosition().toPoint() - self.drag_offset
            rect = QRect(self.resize_origin)
            rect.setWidth(max(self.min_size.width(), rect.width() + delta.x()))
            rect.setHeight(max(self.min_size.height(), rect.height() + delta.y()))
            self.setGeometry(rect)
            self._clamp_to_screen()
        elif self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
        else:
            if self._in_resize_zone(event.position().toPoint()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._end_drag()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._clamp_to_screen()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.isVisible():
            self.save_window_state()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_visible()

    def closeEvent(self, event):
        event.ignore()
        self.hide_to_tray()


def main():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setQuitOnLastWindowClosed(False)

    window = FloatingWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
