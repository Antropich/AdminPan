# -*- coding: utf-8 -*-
"""Admin Panel installer / uninstaller (PySide6).

One exe does both jobs:
  AdminPanel-Setup.exe            -> install
  <install dir>\\Uninstall.exe    -> the same exe copied next to the program, runs with --uninstall

The installer is built with --uac-admin, so it is elevated. A program started
from an elevated process inherits elevation, which is why launching
AdminPanel.exe (it also requires admin) at the end of the setup no longer
fails with "CreateProcess error 740".
"""
import os
import sys
import time
import shutil
import base64
import ctypes
import subprocess

from PySide6.QtCore import Qt, QThread, Signal, QRectF, QPoint
from PySide6.QtGui import QIcon, QPainter, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QProgressBar, QStackedWidget, QFileDialog,
)

APP_TITLE = "Admin Panel"
APP_ID = "AdminPanel"
APP_EXE = "AdminPanel.exe"
UNINSTALL_EXE = "Uninstall.exe"
PUBLISHER = "Admin Panel"
APP_VERSION = "1.2.0"   # the release workflow rewrites this from the release tag
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s" % APP_ID
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

NO_WINDOW = 0x08000000
DETACHED = 0x00000008

# ----------------------------------------------------------------------------
# Theme (same tokens as admin_panel.py)
# ----------------------------------------------------------------------------
C_BG = "#000000"
C_TOPBAR = "#3c3c3c"
C_BORDER = "#1c1c1c"
C_BORDER_HI = "#3c3c3c"
C_TEXT = "#ffffff"
C_LABEL = "#b3b3b3"
C_MUTED = "#808080"
C_ACCENT = "#fae4c8"
C_BADGE_BG = "#191814"
RADIUS = 6
FONT_STACK = '"Inter", "Geist", "Segoe UI Variable", "Segoe UI", Arial, sans-serif'

QSS = """
QWidget { color: %(TEXT)s; font-family: %(FONT)s; font-size: 13px; }
#root { background: %(BG)s; border: 1px solid %(BORDER_HI)s; border-radius: %(R)spx; }
#topbar { background: %(TOPBAR)s; border: none; border-top-left-radius: 5px; border-top-right-radius: 5px; }
QLabel { background: transparent; }
#toptitle { color: %(TEXT)s; font-size: 12px; }
#h1 { font-size: 30px; font-weight: 500; color: %(TEXT)s; }
#h2 { font-size: 22px; font-weight: 500; color: %(TEXT)s; }
#sub { color: %(MUTED)s; font-size: 13px; }
#text { color: %(LABEL)s; font-size: 13px; }
#cap { color: %(LABEL)s; font-size: 12px; }
#err { color: #ff8a80; font-size: 12px; }
#pct { color: %(ACCENT)s; font-size: 44px; font-weight: 500; }
#badge { background: %(BADGE_BG)s; color: #ffebc9; border-radius: %(R)spx; padding: 3px 10px; font-size: 12px; }

QLineEdit { background: %(BG)s; border: 1px solid %(BORDER)s; border-radius: %(R)spx; padding: 9px 12px; selection-background-color: %(BORDER_HI)s; }
QLineEdit:focus { border: 1px solid %(MUTED)s; }

QPushButton { background: transparent; border: 1px solid %(BORDER)s; border-radius: %(R)spx; padding: 11px 22px; color: %(LABEL)s; font-size: 13px; }
QPushButton:hover { border-color: %(BORDER_HI)s; color: %(TEXT)s; }
QPushButton:pressed { background: %(BORDER)s; }
QPushButton:disabled { color: #4a4a4a; border-color: %(BORDER)s; }
QPushButton#primary { border: 1px solid %(ACCENT)s; color: %(ACCENT)s; font-weight: 500; }
QPushButton#primary:hover { background: %(BADGE_BG)s; border-color: %(ACCENT)s; color: %(ACCENT)s; }
QPushButton#close { border: none; border-radius: 4px; padding: 0; color: %(TEXT)s; font-size: 14px; }
QPushButton#close:hover { background: #c42b1c; }
QPushButton#close:disabled { color: #777777; background: transparent; }

QCheckBox { spacing: 10px; color: %(LABEL)s; background: transparent; }
QCheckBox:hover { color: %(TEXT)s; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid %(BORDER_HI)s; border-radius: 4px; background: %(BG)s; }
QCheckBox::indicator:hover { border-color: %(ACCENT)s; }
QCheckBox::indicator:checked { background: %(ACCENT)s; border-color: %(ACCENT)s; }

QProgressBar { background: %(BORDER)s; border: none; border-radius: 3px; height: 6px; max-height: 6px; text-align: center; color: transparent; }
QProgressBar::chunk { background: %(ACCENT)s; border-radius: 3px; }
""" % {
    "BG": C_BG, "TOPBAR": C_TOPBAR, "BORDER": C_BORDER, "BORDER_HI": C_BORDER_HI,
    "TEXT": C_TEXT, "LABEL": C_LABEL, "MUTED": C_MUTED, "ACCENT": C_ACCENT,
    "BADGE_BG": C_BADGE_BG, "R": RADIUS, "FONT": FONT_STACK,
}

# ----------------------------------------------------------------------------
# Texts
# ----------------------------------------------------------------------------
STR = {
    "ru": {
        "win_install": "Установка Admin Panel",
        "win_uninstall": "Удаление Admin Panel",
        "welcome_title": "Admin Panel",
        "welcome_text": "Программа для админов: список команд сервера по уровням, "
                        "бинды на любые клавиши и счётчик репортов.",
        "welcome_note": "Для работы биндов нужны права администратора - "
                        "программа сама запросит их при запуске.",
        "next": "Далее", "back": "Назад", "cancel": "Отмена", "install": "Установить",
        "update": "Обновить", "finish": "Готово",
        "path_title": "Параметры установки",
        "path_label": "Папка установки",
        "browse": "Обзор...",
        "opt_desktop": "Ярлык на рабочем столе",
        "opt_autostart": "Запускать вместе с Windows",
        "opt_launch": "Запустить Admin Panel",
        "installing": "Установка...",
        "st_stop": "Закрываем запущенную программу",
        "st_dir": "Создаём папку",
        "st_copy": "Копируем файлы",
        "st_uninst": "Добавляем деинсталлятор",
        "st_links": "Создаём ярлыки",
        "st_reg": "Регистрируем в системе",
        "st_done": "Готово",
        "done_title": "Установка завершена",
        "done_text": "Admin Panel установлена. Запускайте её от имени администратора - "
                     "ярлык сделает это сам.",
        "fail_title": "Не удалось установить",
        "bad_path": "Укажите корректную папку установки.",
        "un_title": "Удалить Admin Panel?",
        "un_text": "Программа и ярлыки будут удалены с этого компьютера.",
        "un_data": "Также удалить настройки и бинды",
        "un_btn": "Удалить",
        "un_busy": "Удаление...",
        "un_done_title": "Admin Panel удалена",
        "un_done_text": "Файлы программы удалены с компьютера.",
        "un_fail_title": "Не удалось удалить",
        "st_rm_files": "Удаляем файлы",
        "st_rm_links": "Удаляем ярлыки",
        "st_rm_reg": "Чистим реестр",
        "st_rm_data": "Удаляем настройки",
        "need_admin": "Нужны права администратора. Запустите установщик от имени администратора.",
        "version": "Версия",
    },
    "en": {
        "win_install": "Admin Panel Setup",
        "win_uninstall": "Admin Panel Uninstall",
        "welcome_title": "Admin Panel",
        "welcome_text": "A tool for admins: the full server command list by level, "
                        "binds on any key and a report counter.",
        "welcome_note": "Binds need administrator rights - the app asks for them on start.",
        "next": "Next", "back": "Back", "cancel": "Cancel", "install": "Install",
        "update": "Update", "finish": "Finish",
        "path_title": "Install options",
        "path_label": "Install folder",
        "browse": "Browse...",
        "opt_desktop": "Desktop shortcut",
        "opt_autostart": "Start with Windows",
        "opt_launch": "Launch Admin Panel",
        "installing": "Installing...",
        "st_stop": "Closing the running app",
        "st_dir": "Creating the folder",
        "st_copy": "Copying files",
        "st_uninst": "Adding the uninstaller",
        "st_links": "Creating shortcuts",
        "st_reg": "Registering in the system",
        "st_done": "Done",
        "done_title": "Setup complete",
        "done_text": "Admin Panel is installed. It needs administrator rights - "
                     "the shortcut asks for them automatically.",
        "fail_title": "Installation failed",
        "bad_path": "Enter a valid install folder.",
        "un_title": "Remove Admin Panel?",
        "un_text": "The program and its shortcuts will be removed from this computer.",
        "un_data": "Also delete settings and binds",
        "un_btn": "Remove",
        "un_busy": "Removing...",
        "un_done_title": "Admin Panel removed",
        "un_done_text": "The program files were removed from this computer.",
        "un_fail_title": "Removal failed",
        "st_rm_files": "Removing files",
        "st_rm_links": "Removing shortcuts",
        "st_rm_reg": "Cleaning the registry",
        "st_rm_data": "Removing settings",
        "need_admin": "Administrator rights are required. Run the installer as administrator.",
        "version": "Version",
    },
}


def detect_lang():
    try:
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF
        if lid in (0x19, 0x22):   # Russian, Ukrainian
            return "ru"
    except Exception:
        pass
    return "en"


LANG = detect_lang()


def T(key):
    return STR[LANG][key]


# ----------------------------------------------------------------------------
# System helpers
# ----------------------------------------------------------------------------

def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def payload_path(name):
    p = resource_path("payload", name)
    if os.path.exists(p):
        return p
    # running from source: fall back to the build output
    alt = {"AdminPanel.exe": os.path.join("dist", "AdminPanel.exe"),
           "icon.ico": os.path.join("assets", "icon.ico")}.get(name, name)
    return resource_path(alt)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def clean_env():
    """Environment for launching another PyInstaller exe from this one."""
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("_PYI") or k == "_MEIPASS2":
            env.pop(k, None)
    return env


def run_hidden(args):
    try:
        subprocess.run(args, creationflags=NO_WINDOW, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=60)
    except Exception:
        pass


def make_shortcut(lnk, target, workdir, icon):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)

    def q(s):
        return "'" + s.replace("'", "''") + "'"
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);"
          "$s.TargetPath=%s;$s.WorkingDirectory=%s;$s.IconLocation=%s;"
          "$s.Description='Admin Panel';$s.Save()") % (q(lnk), q(target), q(workdir), q(icon))
    enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    run_hidden(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                "Bypass", "-EncodedCommand", enc])


def start_menu_lnk():
    base = os.environ.get("ProgramData", r"C:\ProgramData")
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs", APP_TITLE + ".lnk")


def desktop_lnk():
    base = os.environ.get("PUBLIC", r"C:\Users\Public")
    return os.path.join(base, "Desktop", APP_TITLE + ".lnk")


def default_dir():
    return os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_TITLE)


def installed_dir():
    """Install dir from the registry, or None."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "InstallLocation")[0]
    except Exception:
        return None


def copy_with_progress(src, dst, cb):
    size = max(os.path.getsize(src), 1)
    done = 0
    last_err = None
    for _ in range(8):   # the target may be locked for a moment after taskkill
        try:
            with open(src, "rb") as fi, open(dst, "wb") as fo:
                while True:
                    buf = fi.read(1024 * 256)
                    if not buf:
                        break
                    fo.write(buf)
                    done += len(buf)
                    cb(done / size)
            return
        except PermissionError as e:
            last_err = e
            done = 0
            time.sleep(0.5)
    raise last_err


# ----------------------------------------------------------------------------
# Workers
# ----------------------------------------------------------------------------

class InstallWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str)       # install dir
    failed = Signal(str)

    def __init__(self, target, desktop, autostart):
        super().__init__()
        self.target, self.desktop, self.autostart = target, desktop, autostart

    def run(self):
        try:
            self._install()
        except Exception as e:
            self.failed.emit(str(e) or e.__class__.__name__)

    def _install(self):
        import winreg
        target = os.path.normpath(self.target)
        exe = os.path.join(target, APP_EXE)
        ico = os.path.join(target, "icon.ico")
        unin = os.path.join(target, UNINSTALL_EXE)

        self.progress.emit(3, T("st_stop"))
        run_hidden(["taskkill", "/F", "/IM", APP_EXE])
        time.sleep(0.6)

        self.progress.emit(8, T("st_dir"))
        os.makedirs(target, exist_ok=True)

        self.progress.emit(10, T("st_copy"))
        copy_with_progress(payload_path(APP_EXE), exe,
                           lambda f: self.progress.emit(10 + int(f * 60), T("st_copy")))
        shutil.copyfile(payload_path("icon.ico"), ico)

        self.progress.emit(75, T("st_uninst"))
        if getattr(sys, "frozen", False):
            try:
                shutil.copyfile(sys.executable, unin)
            except Exception:
                pass   # running an old uninstaller over itself, not fatal

        self.progress.emit(85, T("st_links"))
        make_shortcut(start_menu_lnk(), exe, target, ico)
        if self.desktop:
            make_shortcut(desktop_lnk(), exe, target, ico)
        else:
            try:
                os.remove(desktop_lnk())
            except OSError:
                pass

        self.progress.emit(93, T("st_reg"))
        size_kb = max(os.path.getsize(exe) // 1024, 1)
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0,
                                winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_TITLE)
            winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, target)
            winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, ico)
            winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, '"%s" --uninstall' % unin)
            winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                if self.autostart:
                    winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, '"%s"' % exe)
                else:
                    try:
                        winreg.DeleteValue(k, APP_ID)
                    except FileNotFoundError:
                        pass
        except OSError:
            pass

        self.progress.emit(100, T("st_done"))
        time.sleep(0.4)
        self.finished_ok.emit(target)


class UninstallWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, target, remove_data):
        super().__init__()
        self.target, self.remove_data = target, remove_data

    def run(self):
        try:
            self._uninstall()
        except Exception as e:
            self.failed.emit(str(e) or e.__class__.__name__)

    def _uninstall(self):
        import winreg
        target = os.path.normpath(self.target)

        self.progress.emit(5, T("st_stop"))
        run_hidden(["taskkill", "/F", "/IM", APP_EXE])
        time.sleep(0.6)

        self.progress.emit(25, T("st_rm_links"))
        for p in (start_menu_lnk(), desktop_lnk()):
            try:
                os.remove(p)
            except OSError:
                pass

        self.progress.emit(45, T("st_rm_files"))
        # only our own files, never a recursive delete of an arbitrary folder
        for name in (APP_EXE, "icon.ico"):
            p = os.path.join(target, name)
            for _ in range(8):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                    break
                except PermissionError:
                    time.sleep(0.5)

        self.progress.emit(70, T("st_rm_reg"))
        try:
            winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, winreg.KEY_WOW64_64KEY, 0)
        except OSError:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, APP_ID)
        except OSError:
            pass

        if self.remove_data:
            self.progress.emit(85, T("st_rm_data"))
            appdata = os.path.join(os.environ.get("APPDATA", ""), APP_ID)
            if os.environ.get("APPDATA") and os.path.isdir(appdata):
                shutil.rmtree(appdata, ignore_errors=True)

        # this exe is still running: delete it (and the empty folder) a moment later
        self_exe = os.path.join(target, UNINSTALL_EXE)
        cmd = ('ping 127.0.0.1 -n 3 >nul & del /f /q "%s" & rmdir "%s"' % (self_exe, target))
        try:
            subprocess.Popen(["cmd.exe", "/c", cmd], creationflags=NO_WINDOW | DETACHED,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL, close_fds=True)
        except Exception:
            pass

        self.progress.emit(100, T("st_done"))
        time.sleep(0.4)
        self.finished_ok.emit()


# ----------------------------------------------------------------------------
# Widgets
# ----------------------------------------------------------------------------

class Logo(QWidget):
    """Crescent moon on black, same drawing as assets/icon.ico."""

    def __init__(self, size=72, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        p.setPen(QPen(QColor(C_BORDER_HI), 1))
        p.setBrush(QColor(C_BG))
        p.drawRoundedRect(QRectF(0.5, 0.5, s - 1, s - 1), s * 0.22, s * 0.22)
        r, c = s * 0.30, s / 2
        moon = QPainterPath()
        moon.addEllipse(QRectF(c - r, c - r, 2 * r, 2 * r))
        br = r * 0.82
        bx, by = c + r * 0.50, c - r * 0.22
        bite = QPainterPath()
        bite.addEllipse(QRectF(bx - br, by - br, 2 * br, 2 * br))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_ACCENT))
        p.drawPath(moon.subtracted(bite))


class CheckMark(QWidget):
    """Accent circle with a tick (success) or a cross (failure)."""

    def __init__(self, ok=True, parent=None):
        super().__init__(parent)
        self.ok = ok
        self.setFixedSize(72, 72)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(C_ACCENT if self.ok else "#ff8a80")
        p.setPen(QPen(col, 2))
        p.setBrush(QColor(C_BADGE_BG))
        p.drawEllipse(QRectF(2, 2, 68, 68))
        p.setPen(QPen(col, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if self.ok:
            p.drawLine(22, 37, 32, 47)
            p.drawLine(32, 47, 51, 26)
        else:
            p.drawLine(26, 26, 46, 46)
            p.drawLine(46, 26, 26, 46)


class TopBar(QFrame):
    def __init__(self, window, title):
        super().__init__()
        self.win = window
        self.setObjectName("topbar")
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 6, 0)
        t = QLabel(title)
        t.setObjectName("toptitle")
        lay.addWidget(t)
        lay.addStretch(1)
        self.btn = QPushButton("\u2715")
        self.btn.setObjectName("close")
        self.btn.setFixedSize(30, 24)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(window.close)
        lay.addWidget(self.btn)
        self._drag = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None


def label(text, name=None, wrap=True):
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    l.setWordWrap(wrap)
    return l


def button(text, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    b.setCursor(Qt.PointingHandCursor)
    return b


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w:
            w.deleteLater()


# ----------------------------------------------------------------------------
# Wizard window
# ----------------------------------------------------------------------------

class Wizard(QWidget):
    def __init__(self, uninstall=False):
        super().__init__()
        self.uninstall = uninstall
        self.busy = False
        self.worker = None
        self.target = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setFixedSize(660, 440)
        self.setWindowTitle(T("win_uninstall") if uninstall else T("win_install"))
        ico = payload_path("icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        root = QFrame()
        root.setObjectName("root")
        outer.addWidget(root)
        rl = QVBoxLayout(root)
        rl.setContentsMargins(1, 1, 1, 1)
        rl.setSpacing(0)

        self.top = TopBar(self, self.windowTitle())
        rl.addWidget(self.top)

        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)

        # footer
        foot = QFrame()
        foot.setStyleSheet("QFrame { border-top: 1px solid %s; }" % C_BORDER)
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(32, 16, 32, 16)
        fl.setSpacing(12)
        self.foot_note = QLabel("%s %s" % (T("version"), APP_VERSION))
        self.foot_note.setObjectName("sub")
        self.foot_note.setStyleSheet("border: none;")
        fl.addWidget(self.foot_note)
        fl.addStretch(1)
        self.btn_back = button(T("back"))
        self.btn_cancel = button(T("cancel"))
        self.btn_next = button(T("next"), primary=True)
        for b in (self.btn_back, self.btn_cancel, self.btn_next):
            fl.addWidget(b)
        rl.addWidget(foot)

        self.btn_cancel.clicked.connect(self.close)

        self.build_pages()
        self.show_page(0)

    # ---- pages
    def page(self, widget_builder):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 22)
        lay.setSpacing(0)
        widget_builder(lay)
        self.stack.addWidget(w)
        return w

    def build_pages(self):
        # 0: welcome / uninstall confirm
        def intro(lay):
            row = QHBoxLayout()
            row.setSpacing(22)
            row.addWidget(Logo(84), 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(10)
            if self.uninstall:
                col.addWidget(label(T("un_title"), "h1"))
                col.addWidget(label(T("un_text"), "text"))
                col.addSpacing(12)
                self.chk_data = QCheckBox(T("un_data"))
                col.addWidget(self.chk_data)
            else:
                col.addWidget(label(T("welcome_title"), "h1"))
                badge = QLabel("%s %s" % (T("version"), APP_VERSION))
                badge.setObjectName("badge")
                brow = QHBoxLayout()
                brow.addWidget(badge)
                brow.addStretch(1)
                col.addLayout(brow)
                col.addSpacing(6)
                col.addWidget(label(T("welcome_text"), "text"))
                col.addWidget(label(T("welcome_note"), "sub"))
            col.addStretch(1)
            row.addLayout(col, 1)
            lay.addLayout(row)
        self.p_intro = self.page(intro)

        # 1: options (install only)
        def options(lay):
            lay.addWidget(label(T("path_title"), "h2"))
            lay.addSpacing(22)
            lay.addWidget(label(T("path_label"), "cap"))
            lay.addSpacing(6)
            row = QHBoxLayout()
            row.setSpacing(10)
            self.ed_path = QLineEdit(installed_dir() or default_dir())
            row.addWidget(self.ed_path, 1)
            b = button(T("browse"))
            b.clicked.connect(self.browse)
            row.addWidget(b)
            lay.addLayout(row)
            self.lbl_err = label("", "err")
            lay.addSpacing(6)
            lay.addWidget(self.lbl_err)
            lay.addSpacing(14)
            self.chk_desktop = QCheckBox(T("opt_desktop"))
            self.chk_desktop.setChecked(True)
            self.chk_auto = QCheckBox(T("opt_autostart"))
            lay.addWidget(self.chk_desktop)
            lay.addSpacing(12)
            lay.addWidget(self.chk_auto)
            lay.addStretch(1)
        self.p_opts = self.page(options)

        # 2: progress
        def prog(lay):
            lay.addStretch(1)
            self.lbl_pct = label("0%", "pct", wrap=False)
            lay.addWidget(self.lbl_pct)
            lay.addSpacing(10)
            self.bar = QProgressBar()
            self.bar.setRange(0, 100)
            self.bar.setTextVisible(False)
            self.bar.setFixedHeight(6)
            lay.addWidget(self.bar)
            lay.addSpacing(14)
            self.lbl_status = label(T("un_busy") if self.uninstall else T("installing"), "text")
            lay.addWidget(self.lbl_status)
            lay.addStretch(1)
        self.p_prog = self.page(prog)

        # 3: done
        def done(lay):
            row = QHBoxLayout()
            row.setSpacing(22)
            self.done_icon_holder = QVBoxLayout()
            row.addLayout(self.done_icon_holder)
            col = QVBoxLayout()
            col.setSpacing(10)
            self.lbl_done_title = label("", "h2")
            self.lbl_done_text = label("", "text")
            col.addWidget(self.lbl_done_title)
            col.addWidget(self.lbl_done_text)
            col.addSpacing(14)
            self.chk_launch = QCheckBox(T("opt_launch"))
            self.chk_launch.setChecked(True)
            col.addWidget(self.chk_launch)
            col.addStretch(1)
            row.addLayout(col, 1)
            lay.addLayout(row)
        self.p_done = self.page(done)

    def show_page(self, idx):
        self.stack.setCurrentIndex(idx)
        for b in (self.btn_back, self.btn_cancel, self.btn_next):
            try:
                b.clicked.disconnect()
            except Exception:
                pass
        self.btn_cancel.clicked.connect(self.close)
        self.btn_back.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_next.setVisible(True)
        self.btn_next.setEnabled(True)
        self.top.btn.setEnabled(True)

        if idx == 0:
            if self.uninstall:
                self.btn_next.setText(T("un_btn"))
                self.btn_next.clicked.connect(self.start_uninstall)
            else:
                self.btn_next.setText(T("next"))
                self.btn_next.clicked.connect(lambda: self.show_page(1))
        elif idx == 1:
            self.btn_back.setVisible(True)
            self.btn_back.clicked.connect(lambda: self.show_page(0))
            self.btn_next.setText(T("update") if installed_dir() else T("install"))
            self.btn_next.clicked.connect(self.start_install)
        elif idx == 2:
            self.btn_cancel.setVisible(False)
            self.btn_next.setVisible(False)
            self.top.btn.setEnabled(False)
        elif idx == 3:
            self.btn_cancel.setVisible(False)
            self.btn_next.setText(T("finish"))
            self.btn_next.clicked.connect(self.finish_clicked)

    # ---- actions
    def browse(self):
        d = QFileDialog.getExistingDirectory(self, T("path_label"), self.ed_path.text())
        if d:
            d = os.path.normpath(d)
            # keep the app in its own subfolder if the user picked a drive/root-like folder
            if os.path.basename(d).lower() != APP_TITLE.lower() and os.listdir(d):
                d = os.path.join(d, APP_TITLE)
            self.ed_path.setText(d)

    def set_progress(self, value, text):
        self.bar.setValue(value)
        self.lbl_pct.setText("%d%%" % value)
        self.lbl_status.setText(text)

    def start_install(self):
        path = self.ed_path.text().strip().strip('"')
        if not path or not os.path.isabs(path) or len(os.path.splitdrive(path)[1].strip("\\/")) == 0:
            self.lbl_err.setText(T("bad_path"))
            return
        if not is_admin():
            self.lbl_err.setText(T("need_admin"))
            return
        self.lbl_err.setText("")
        self.target = path
        self.busy = True
        self.show_page(2)
        self.set_progress(0, T("installing"))
        self.worker = InstallWorker(path, self.chk_desktop.isChecked(), self.chk_auto.isChecked())
        self.worker.progress.connect(self.set_progress)
        self.worker.finished_ok.connect(self.install_ok)
        self.worker.failed.connect(self.install_failed)
        self.worker.start()

    def start_uninstall(self):
        self.target = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) \
            else (installed_dir() or default_dir())
        if not is_admin():
            self.lbl_status.setText(T("need_admin"))
        self.busy = True
        self.show_page(2)
        self.set_progress(0, T("un_busy"))
        self.worker = UninstallWorker(self.target, self.chk_data.isChecked())
        self.worker.progress.connect(self.set_progress)
        self.worker.finished_ok.connect(self.uninstall_ok)
        self.worker.failed.connect(self.install_failed)
        self.worker.start()

    def set_done(self, ok, title, text, show_launch):
        clear_layout(self.done_icon_holder)
        self.done_icon_holder.addWidget(CheckMark(ok), 0, Qt.AlignTop)
        self.lbl_done_title.setText(title)
        self.lbl_done_text.setText(text)
        self.chk_launch.setVisible(show_launch)
        self.busy = False
        self.show_page(3)

    def install_ok(self, target):
        self.target = target
        self.set_done(True, T("done_title"), T("done_text"), True)

    def uninstall_ok(self):
        self.set_done(True, T("un_done_title"), T("un_done_text"), False)

    def install_failed(self, msg):
        title = T("un_fail_title") if self.uninstall else T("fail_title")
        self.set_done(False, title, msg, False)

    def finish_clicked(self):
        if not self.uninstall and self.chk_launch.isVisible() and self.chk_launch.isChecked():
            self.launch_app()
        self.close()

    def launch_app(self):
        exe = os.path.join(self.target, APP_EXE)
        try:
            # we are elevated, so the child (requireAdministrator) inherits it: no error 740
            subprocess.Popen([exe], cwd=self.target, env=clean_env(), close_fds=True,
                             creationflags=DETACHED | 0x00000200)
        except OSError:
            try:
                os.startfile(exe)   # shows the normal UAC prompt if needed
            except Exception:
                pass

    def closeEvent(self, e):
        if self.busy:
            e.ignore()
        else:
            e.accept()


def main():
    # taskbar icon / grouping
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AdminPanel.Setup")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = Wizard(uninstall="--uninstall" in sys.argv[1:])
    scr = app.primaryScreen().availableGeometry()
    w.move(scr.center() - QPoint(w.width() // 2, w.height() // 2))
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
