# -*- coding: utf-8 -*-
"""Admin Panel - bindable admin commands for RAGE MP servers.

A bind types the command into the game chat (chat key + command text) and
leaves the chat open, so the admin finishes it with ID / time / reason.
"""
import sys
import os
import html
import math
import json
import time
import threading
import datetime
from pathlib import Path

from PySide6.QtCore import (
    Qt, Signal, QTimer, QObject, QPointF, QRectF, QSize, QEvent,
    QVariantAnimation, QEasingCurve,
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath, QPen, QFontMetrics
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame, QDialog,
    QMessageBox, QComboBox, QSpinBox, QSlider, QCheckBox, QListWidget,
    QListWidgetItem, QFileDialog, QMenu, QSystemTrayIcon, QSizeGrip,
    QDialogButtonBox, QPlainTextEdit, QStackedWidget, QSizePolicy,
)

try:
    import keyboard
except Exception:  # pragma: no cover
    keyboard = None

APP_NAME = "AdminPanel"

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

DEFAULTS = {
    "language": "en",
    "level": 1,
    "chat_key": "t",
    "auto_chat": True,
    "level_set": False,
    "key_delay_ms": 80,
    "cooldown_ms": 300,
    "opacity": 100,
    "autostart": False,
    "binds": {"act:toggle": "insert"},
    "favorites": [],
    "custom_commands": [],
    "reports": [],
    "history": [],
    "notes": [],
    "window": [None, None, 1040, 700],
}


def data_dir():
    base = os.environ.get("ADMINPANEL_HOME")
    if base:
        p = Path(base)
    elif os.name == "nt":
        p = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    else:
        p = Path.home() / ".adminpanel"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Config:
    def __init__(self):
        self.path = data_dir() / "config.json"
        self.data = json.loads(json.dumps(DEFAULTS))
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except Exception:
                pass
        self.data["binds"].setdefault("act:toggle", "insert")

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v


# ----------------------------------------------------------------------------
# Commands (only the important ones; custom ones can be added in Settings)
# ----------------------------------------------------------------------------

COMMANDS = [
    ("/mute", 1, "mute"), ("/unmute", 1, "mute"),
    ("/offmute", 1, "mute"), ("/offunmute", 1, "mute"),
    ("/jail", 2, "jail"), ("/unjail", 2, "jail"),
    ("/offjail", 2, "jail"), ("/offunjail", 2, "jail"),
    ("/kick", 2, "kick"),
    ("/warn", 3, "warn"), ("/unwarn", 3, "warn"),
    ("/offwarn", 3, "warn"), ("/unwarnoff", 3, "warn"),
    ("/offunwarn", 5, "warn"),
    ("/ban", 3, "ban"), ("/unban", 3, "ban"),
    ("/offban", 3, "ban"), ("/unbanoff", 3, "ban"),
    ("/hardban", 4, "ban"), ("/unhardban", 4, "ban"),
    ("/offhardban", 4, "ban"), ("/unhardbanoff", 4, "ban"),
    ("/crimeban", 7, "ban"), ("/uncrimeban", 7, "ban"),
    ("/offcrimeban", 7, "ban"), ("/offuncrimeban", 7, "ban"),
    ("/sp", 1, "watch"), ("/usp", 1, "watch"), ("/tp", 1, "watch"),
    ("/metp", 2, "watch"), ("/fz", 1, "watch"), ("/unfz", 1, "watch"),
    ("/spawn", 2, "watch"),
    ("/check", 2, "info"), ("/stats", 1, "info"), ("/offstats", 1, "info"),
    ("/id", 1, "info"), ("/checkkill", 2, "info"), ("/softcheck", 4, "info"),
    ("/a", 1, "chat"), ("/asms", 1, "chat"),
    ("/agm", 1, "admin"), ("/redname", 1, "admin"),
]

CATS = ["mute", "jail", "kick", "warn", "ban", "watch", "info", "chat", "admin", "custom"]


def all_commands(cfg):
    extra = [(c["cmd"], c.get("level", 1), "custom") for c in cfg["custom_commands"]]
    return COMMANDS + extra


# ----------------------------------------------------------------------------
# Translations
# ----------------------------------------------------------------------------

LANGS = {"en": "English", "ru": "Русский", "uk": "Українська"}

T = {
    "en": {
        "title": "Admin Panel", "tab_commands": "Commands", "tab_favorites": "Favorites",
        "tab_reports": "Reports", "tab_notes": "Notes", "tab_history": "History",
        "tab_settings": "Settings", "search": "Search commands...",
        "unbound": "not bound", "press_key": "Press the key combination...\nEsc - clear this bind",
        "cancel": "Cancel", "clear_bind": "Clear bind", "fav_add": "Add to favorites",
        "fav_remove": "Remove from favorites", "delete": "Delete",
        "replace_q": "This combination is already used by {x}. Replace it?",
        "toggle_busy": "This combination is the show/hide key of the panel.",
        "today": "Today", "week": "This week", "add_report": "+1 report",
        "remove_report": "-1 report (undo)", "recent": "Recent reports",
        "remove_selected": "Remove selected", "bind": "Bind",
        "reports_hint": "Bind a key to +1 and -1, or use the buttons. The week starts on Monday.",
        "language": "Language", "theme": "Theme", "dark": "Dark", "light": "Light",
        "level": "Admin level", "chat_key": "Chat key in game",
        "key_delay": "Delay after chat key (ms)", "cooldown": "Pause between binds (ms)",
        "opacity": "Window opacity", "toggle_key": "Show / hide panel",
        "autostart": "Start with Windows", "export_binds": "Export binds",
        "import_binds": "Import binds", "add_custom": "Add own command", "quit": "Quit",
        "player": "Player (nick / ID)", "note": "Note", "add": "Add",
        "clear_history": "Clear history", "custom_cmd": "Command", "level_short": "Level",
        "hook_error": "Keyboard hook is unavailable. On Windows run the program as administrator.",
        "imported": "Binds imported", "exported": "Binds exported",
        "history_hint": "Commands typed into the game by your binds.",
        "toast_added": "Report +1", "toast_removed": "Report -1", "nothing": "Nothing to remove",
        "cat_mute": "Mute", "cat_jail": "Jail", "cat_kick": "Kick", "cat_warn": "Warns",
        "cat_ban": "Bans", "cat_watch": "Watch / teleport", "cat_info": "Info",
        "cat_chat": "Chat", "cat_admin": "Admin", "cat_custom": "Own commands",
        "empty_fav": "No favorites yet. Right-click a command and add it.",
        "hide": "Hide",
        "auto_chat": "Open chat automatically",
        "tab_console": "Console", "ask_level": "What is your admin level?",
        "ask_level_hint": "Later it can only be raised with /aupgrade in the Console tab.",
        "ok": "OK", "console_placeholder": "Type a command, e.g. /help",
    },
    "ru": {
        "title": "Админ-панель", "tab_commands": "Команды", "tab_favorites": "Избранное",
        "tab_reports": "Репорты", "tab_notes": "Заметки", "tab_history": "История",
        "tab_settings": "Настройки", "search": "Поиск команд...",
        "unbound": "не назначено", "press_key": "Нажмите сочетание клавиш...\nEsc - убрать бинд",
        "cancel": "Отмена", "clear_bind": "Сбросить бинд", "fav_add": "В избранное",
        "fav_remove": "Убрать из избранного", "delete": "Удалить",
        "replace_q": "Это сочетание уже занято: {x}. Заменить?",
        "toggle_busy": "Это сочетание открывает и скрывает панель.",
        "today": "Сегодня", "week": "За неделю", "add_report": "+1 репорт",
        "remove_report": "-1 репорт (отмена)", "recent": "Последние репорты",
        "remove_selected": "Убрать выбранный", "bind": "Бинд",
        "reports_hint": "Назначьте клавиши на +1 и -1 или жмите кнопки. Неделя начинается с понедельника.",
        "language": "Язык", "theme": "Тема", "dark": "Тёмная", "light": "Светлая",
        "level": "Уровень админки", "chat_key": "Клавиша чата в игре",
        "key_delay": "Задержка после клавиши чата (мс)", "cooldown": "Пауза между биндами (мс)",
        "opacity": "Прозрачность окна", "toggle_key": "Показать / скрыть панель",
        "autostart": "Запускать с Windows", "export_binds": "Экспорт биндов",
        "import_binds": "Импорт биндов", "add_custom": "Своя команда", "quit": "Выход",
        "player": "Игрок (ник / ID)", "note": "Заметка", "add": "Добавить",
        "clear_history": "Очистить историю", "custom_cmd": "Команда", "level_short": "Уровень",
        "hook_error": "Перехват клавиатуры недоступен. В Windows запустите программу от имени администратора.",
        "imported": "Бинды импортированы", "exported": "Бинды экспортированы",
        "history_hint": "Команды, которые ваши бинды ввели в игру.",
        "toast_added": "Репорт +1", "toast_removed": "Репорт -1", "nothing": "Нечего убирать",
        "cat_mute": "Мут", "cat_jail": "Джайл", "cat_kick": "Кик", "cat_warn": "Варны",
        "cat_ban": "Баны", "cat_watch": "Слежка / телепорт", "cat_info": "Информация",
        "cat_chat": "Чат", "cat_admin": "Админ", "cat_custom": "Свои команды",
        "empty_fav": "Избранного пока нет. Нажмите на команду правой кнопкой и добавьте.",
        "hide": "Скрыть",
        "auto_chat": "Открывать чат автоматически",
        "tab_console": "Консоль", "ask_level": "Какой у вас уровень администратора?",
        "ask_level_hint": "Потом его можно только повысить командой /aupgrade на вкладке «Консоль».",
        "ok": "OK", "console_placeholder": "Введите команду, например /help",
    },
    "uk": {
        "title": "Адмін-панель", "tab_commands": "Команди", "tab_favorites": "Обране",
        "tab_reports": "Репорти", "tab_notes": "Нотатки", "tab_history": "Історія",
        "tab_settings": "Налаштування", "search": "Пошук команд...",
        "unbound": "не призначено", "press_key": "Натисніть комбінацію клавіш...\nEsc - прибрати бінд",
        "cancel": "Скасувати", "clear_bind": "Скинути бінд", "fav_add": "В обране",
        "fav_remove": "Прибрати з обраного", "delete": "Видалити",
        "replace_q": "Ця комбінація вже зайнята: {x}. Замінити?",
        "toggle_busy": "Ця комбінація відкриває і ховає панель.",
        "today": "Сьогодні", "week": "За тиждень", "add_report": "+1 репорт",
        "remove_report": "-1 репорт (скасувати)", "recent": "Останні репорти",
        "remove_selected": "Прибрати вибраний", "bind": "Бінд",
        "reports_hint": "Призначте клавіші на +1 і -1 або тисніть кнопки. Тиждень починається з понеділка.",
        "language": "Мова", "theme": "Тема", "dark": "Темна", "light": "Світла",
        "level": "Рівень адмінки", "chat_key": "Клавіша чату в грі",
        "key_delay": "Затримка після клавіші чату (мс)", "cooldown": "Пауза між біндами (мс)",
        "opacity": "Прозорість вікна", "toggle_key": "Показати / сховати панель",
        "autostart": "Запускати з Windows", "export_binds": "Експорт біндів",
        "import_binds": "Імпорт біндів", "add_custom": "Своя команда", "quit": "Вихід",
        "player": "Гравець (нік / ID)", "note": "Нотатка", "add": "Додати",
        "clear_history": "Очистити історію", "custom_cmd": "Команда", "level_short": "Рівень",
        "hook_error": "Перехоплення клавіатури недоступне. У Windows запустіть програму від імені адміністратора.",
        "imported": "Бінди імпортовано", "exported": "Бінди експортовано",
        "history_hint": "Команди, які ваші бінди ввели в гру.",
        "toast_added": "Репорт +1", "toast_removed": "Репорт -1", "nothing": "Нічого прибирати",
        "cat_mute": "Мут", "cat_jail": "Джейл", "cat_kick": "Кік", "cat_warn": "Варни",
        "cat_ban": "Бани", "cat_watch": "Стеження / телепорт", "cat_info": "Інформація",
        "cat_chat": "Чат", "cat_admin": "Адмін", "cat_custom": "Свої команди",
        "empty_fav": "Обраного поки немає. Натисніть на команду правою кнопкою і додайте.",
        "hide": "Сховати",
        "auto_chat": "Відкривати чат автоматично",
        "tab_console": "Консоль", "ask_level": "Який у вас рівень адміністратора?",
        "ask_level_hint": "Потім його можна лише підвищити командою /aupgrade на вкладці «Консоль».",
        "ok": "OK", "console_placeholder": "Введіть команду, наприклад /help",
    },
}

LANG = "en"


def set_lang(code):
    global LANG
    LANG = code if code in T else "en"


def tr(key):
    return T[LANG].get(key) or T["en"].get(key, key)


def fmt_combo(combo):
    return combo.replace("+", " + ").upper() if combo else ""


# ----------------------------------------------------------------------------
# Theme: flat black, hairline borders, one cream accent
# ----------------------------------------------------------------------------

C_BG = "#000000"
C_TOPBAR = "#3c3c3c"
C_BORDER = "#1c1c1c"
C_BORDER_HI = "#3c3c3c"
C_TEXT = "#ffffff"
C_LABEL = "#b3b3b3"
C_MUTED = "#808080"
C_ACCENT = "#fae4c8"
C_NAV = "#A1A1A8"          # header navigation text
C_NAV_BORDER = "#38383D"   # header CTA border
C_BADGE_BG = "#191814"
C_BADGE_FG = "#ffebc9"
RADIUS = 6      # corner radius of containers, buttons, badges
GAP = 32        # gap between blocks of the grid and outer margin
PAD = 20        # inner padding of containers
FONT_STACK = '"Inter", "Geist", "Segoe UI Variable", "Segoe UI", Arial, sans-serif'

TOKENS = {
    "BG": C_BG, "TOPBAR": C_TOPBAR, "BORDER": C_BORDER, "BORDER_HI": C_BORDER_HI,
    "TEXT": C_TEXT, "LABEL": C_LABEL, "MUTED": C_MUTED, "ACCENT": C_ACCENT,
    "BADGE_BG": C_BADGE_BG, "BADGE_FG": C_BADGE_FG, "R": RADIUS, "FONT": FONT_STACK,
    "NAV": C_NAV, "NAV_BORDER": C_NAV_BORDER,
}

QSS = """
QWidget { color: @TEXT@; font-family: @FONT@; font-size: 13px; }
#root { background: @BG@; border: 1px solid @BORDER@; border-radius: @R@px; }
#topbar { background: @TOPBAR@; border: none; border-top-left-radius: 5px; border-top-right-radius: 5px; }
QDialog, QMessageBox { background: @BG@; }
QLabel { background: transparent; }
QToolTip { background: @BG@; color: @TEXT@; border: 1px solid @BORDER@; padding: 4px 8px; }

#title { font-size: 16px; font-weight: 500; color: @TEXT@; }


QLineEdit, QSpinBox, QComboBox, QListWidget { background: @BG@; border: 1px solid @BORDER@; border-radius: @R@px; padding: 8px 12px; selection-background-color: @BORDER_HI@; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QListWidget:focus { border: 1px solid @MUTED@; }
QListWidget { outline: none; padding: 8px; }
QListWidget::item { padding: 8px 10px; border-radius: 4px; color: @LABEL@; }
QListWidget::item:selected { background: @BORDER@; color: @TEXT@; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: @BG@; color: @TEXT@; selection-background-color: @BORDER@; border: 1px solid @BORDER@; outline: none; }

QPushButton { background: transparent; border: 1px solid @BORDER@; border-radius: @R@px; padding: 8px 16px; color: @LABEL@; }
QPushButton:hover { border-color: @BORDER_HI@; color: @TEXT@; }
QPushButton:pressed { background: @BORDER@; }
QPushButton#tile { background: @BG@; padding: 0; text-align: left; }
QPushButton#tile:hover { border-color: @BORDER_HI@; }
QPushButton#primary { border: 1px solid @ACCENT@; color: @ACCENT@; padding: 14px; font-size: 14px; font-weight: 500; }
QPushButton#primary:hover { background: @BADGE_BG@; border-color: @ACCENT@; color: @ACCENT@; }
QPushButton#secondary { padding: 14px; font-size: 14px; }
QPushButton#iconbtn { background: transparent; border: none; border-radius: 4px; padding: 0; }
QPushButton#iconbtn:hover { background: @BORDER@; }
QPushButton#iconcta { background: rgba(255, 255, 255, 8); border: 1px solid @NAV_BORDER@; border-radius: 6px; padding: 0; }
QPushButton#iconcta:hover { background: rgba(255, 255, 255, 18); border-color: #4c4c52; }
QPushButton#navitem { background: transparent; border: none; padding: 0; font-size: 13px; font-weight: 300; }
QLineEdit:disabled, QSpinBox:disabled { color: @MUTED@; }
QPlainTextEdit#console { background: @BG@; border: 1px solid @BORDER@; border-radius: @R@px; padding: 12px; color: @LABEL@; font-family: "Cascadia Mono", Consolas, "Courier New", monospace; font-size: 12px; selection-background-color: @BORDER_HI@; }
QLineEdit#consoleinput { font-family: "Cascadia Mono", Consolas, "Courier New", monospace; font-size: 12px; }

#card { background: @BG@; border: 1px solid @BORDER@; border-radius: @R@px; }
#big { font-size: 44px; font-weight: 500; color: @TEXT@; }
#badge { background: @BADGE_BG@; color: @BADGE_FG@; border-radius: @R@px; padding: 0 10px; font-size: 12px; }
#muted { color: @MUTED@; }
#caption { color: @LABEL@; }
#catlabel { color: @LABEL@; font-size: 12px; }
#tilename { color: @TEXT@; font-size: 14px; }
#tilebind { color: @MUTED@; font-size: 12px; }
#arrow { color: @MUTED@; font-size: 14px; }
#pane QLabel { color: @LABEL@; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: @BORDER@; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: @BORDER_HI@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QSlider::groove:horizontal { height: 2px; background: @BORDER_HI@; border-radius: 1px; }
QSlider::sub-page:horizontal { background: @ACCENT@; border-radius: 1px; }
QSlider::handle:horizontal { background: @ACCENT@; width: 12px; margin: -5px 0; border-radius: 6px; }
QCheckBox { spacing: 10px; color: @LABEL@; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid @BORDER_HI@; border-radius: 3px; background: @BG@; }
QCheckBox::indicator:checked { background: @ACCENT@; border-color: @ACCENT@; }

QMenu { background: @BG@; border: 1px solid @BORDER@; padding: 6px; }
QMenu::item { padding: 6px 20px; color: @LABEL@; }
QMenu::item:selected { background: @BORDER@; color: @TEXT@; }
"""


def make_qss():
    out = QSS
    for k, v in TOKENS.items():
        out = out.replace("@%s@" % k, str(v))
    return out


def crescent_pixmap(size, color=C_ACCENT, bg=None):
    """Crescent-moon logo drawn in code (no image files needed)."""
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    if bg:
        p.setBrush(QColor(bg))
        p.drawRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
    r = size * (0.30 if bg else 0.46)
    c = size / 2.0
    moon = QPainterPath()
    moon.addEllipse(QPointF(c, c), r, r)
    bite = QPainterPath()
    bite.addEllipse(QPointF(c + r * 0.50, c - r * 0.22), r * 0.82, r * 0.82)
    p.fillPath(moon.subtracted(bite), QColor(color))
    p.end()
    return pm


def line_icon(kind, color, size=16):
    """Thin 1px line icons drawn in code: min, max, restore, close, trash."""
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.0)
    pen.setCosmetic(True)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    k = size / 16.0
    p.scale(k, k)
    path = QPainterPath()
    if kind == "min":
        path.moveTo(3, 8.5)
        path.lineTo(13, 8.5)
    elif kind == "max":
        path.addRoundedRect(QRectF(3.5, 3.5, 9, 9), 1.5, 1.5)
    elif kind == "restore":
        path.addRoundedRect(QRectF(3.5, 5.5, 7, 7), 1.5, 1.5)
        path.moveTo(5.5, 5.5)
        path.lineTo(5.5, 3.5)
        path.lineTo(12.5, 3.5)
        path.lineTo(12.5, 10.5)
        path.lineTo(10.5, 10.5)
    elif kind == "close":
        path.moveTo(3.5, 3.5)
        path.lineTo(12.5, 12.5)
        path.moveTo(12.5, 3.5)
        path.lineTo(3.5, 12.5)
    elif kind == "gear":
        n, step = 8, 2 * math.pi / 8
        first = True
        for i in range(n):
            a = i * step
            for r, da in ((4.9, -0.45), (6.6, -0.2), (6.6, 0.2), (4.9, 0.45)):
                x = 8 + r * math.cos(a + da * step)
                y = 8 + r * math.sin(a + da * step)
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
        path.closeSubpath()
        path.addEllipse(QPointF(8, 8), 2.1, 2.1)
    elif kind == "trash":
        path.moveTo(3, 4.5)
        path.lineTo(13, 4.5)
        path.moveTo(6.5, 4.5)
        path.lineTo(6.5, 3)
        path.lineTo(9.5, 3)
        path.lineTo(9.5, 4.5)
        path.moveTo(4.5, 4.5)
        path.lineTo(5.2, 13)
        path.lineTo(10.8, 13)
        path.lineTo(11.5, 4.5)
        path.moveTo(7, 6.5)
        path.lineTo(7, 11)
        path.moveTo(9, 6.5)
        path.lineTo(9, 11)
    p.drawPath(path)
    p.end()
    return pm


class IconButton(QPushButton):
    """Flat line-icon button: soft gray, white on hover. cta=True adds the thin border."""

    def __init__(self, kind, size=16, normal=C_MUTED, cta=False):
        super().__init__()
        self.kind, self.icon_size, self.normal = kind, size, normal
        self.setObjectName("iconcta" if cta else "iconbtn")
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(size, size))
        self._paint(self.normal)

    def _paint(self, color):
        self.setIcon(QIcon(line_icon(self.kind, color, self.icon_size)))

    def set_kind(self, kind):
        self.kind = kind
        self._paint(C_TEXT if self.underMouse() else self.normal)

    def enterEvent(self, e):
        self._paint(C_TEXT)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._paint(self.normal)
        super().leaveEvent(e)


class NavButton(QPushButton):
    """Header navigation item: no fill, no border, thin gray text.
    Default #A1A1A8 -> white on hover / when active, eased over 220 ms."""

    def __init__(self, text, index):
        super().__init__(text)
        self.index = index
        self.setObjectName("navitem")
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._mix = 0.0
        self._hover = False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_mix)
        self.toggled.connect(lambda _c: self._retarget())

    def _set_mix(self, v):
        self._mix = float(v)
        self.update()

    def _retarget(self):
        end = 1.0 if (self.isChecked() or self._hover) else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._mix)
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, e):
        self._hover = True
        self._retarget()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._retarget()
        super().leaveEvent(e)

    def sizeHint(self):
        self.ensurePolished()
        return QSize(QFontMetrics(self.font()).horizontalAdvance(self.text()) + 4, 28)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, e):
        a, b, m = QColor(C_NAV), QColor(C_TEXT), self._mix
        color = QColor(int(a.red() + (b.red() - a.red()) * m),
                       int(a.green() + (b.green() - a.green()) * m),
                       int(a.blue() + (b.blue() - a.blue()) * m))
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(self.font())
        p.setPen(color)
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


def set_autostart(enabled):
    if os.name != "nt":
        return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        if enabled:
            if getattr(sys, "frozen", False):
                cmd = '"%s"' % sys.executable
            else:
                cmd = '"%s" "%s"' % (sys.executable, os.path.abspath(__file__))
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Reports counter
# ----------------------------------------------------------------------------

def report_counts(stamps, now=None):
    now = now or datetime.datetime.now()
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week0 = today0 - datetime.timedelta(days=today0.weekday())
    t, w = today0.timestamp(), week0.timestamp()
    return sum(1 for x in stamps if x >= t), sum(1 for x in stamps if x >= w)


def fmt_time(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%d.%m %H:%M:%S")


# ----------------------------------------------------------------------------
# Hotkeys and typing into the game
# ----------------------------------------------------------------------------

class HotkeyManager(QObject):
    fired = Signal(str)

    def __init__(self):
        super().__init__()
        self.handles = []
        self.error = ""

    def clear(self):
        if keyboard:
            for h in self.handles:
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
        self.handles = []

    def apply(self, binds):
        self.clear()
        self.error = ""
        if keyboard is None:
            self.error = "keyboard module missing"
            return
        for bid, combo in binds.items():
            if not combo:
                continue
            try:
                h = keyboard.add_hotkey(
                    combo, lambda b=bid: self.fired.emit(b),
                    suppress=True, trigger_on_release=False)
                self.handles.append(h)
            except Exception as e:
                self.error = str(e)


def wait_release(combo):
    """Wait until the bound keys are physically released (max 1.5 s)."""
    if keyboard is None:
        return
    deadline = time.time() + 1.5
    for part in (combo or "").split("+"):
        part = part.strip()
        while part and time.time() < deadline:
            try:
                if not keyboard.is_pressed(part):
                    break
            except Exception:
                break
            time.sleep(0.01)
    time.sleep(0.03)


def type_command(chat_key, delay_ms, text, open_chat=True):
    """Worker thread: (optionally) open chat, wipe stray characters, type the command."""
    if keyboard is None:
        return
    try:
        if open_chat:
            keyboard.send(chat_key)
            time.sleep(delay_ms / 1000.0)
            # The pressed key or the chat key can leak a character into the input
            # (for example "e" on a Russian layout). Select all + delete removes it.
            keyboard.send("ctrl+a")
            time.sleep(0.02)
            keyboard.send("backspace")
            time.sleep(0.03)
        keyboard.write(text + " ", delay=0.01)
    except Exception:
        pass


class CaptureDialog(QDialog):
    got = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.combo = ""
        self.cleared = False
        self.setWindowTitle(" ")
        self.setModal(True)
        lay = QVBoxLayout(self)
        label = QLabel(tr("press_key"))
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumSize(320, 90)
        lay.addWidget(label)
        btn = QPushButton(tr("cancel"))
        btn.clicked.connect(self.reject)
        lay.addWidget(btn)
        self.got.connect(self.on_got)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            combo = keyboard.read_hotkey(suppress=False)
        except Exception:
            combo = ""
        try:
            self.got.emit(combo)
        except RuntimeError:
            pass

    def on_got(self, combo):
        if not self.isVisible():
            return
        combo = (combo or "").lower()
        if combo == "":
            self.reject()
        elif combo == "esc":
            self.cleared = True
            self.accept()
        else:
            self.combo = combo
            self.accept()


class CustomCommandDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("add_custom"))
        form = QFormLayout(self)
        self.cmd = QLineEdit()
        self.cmd.setPlaceholderText("/command")
        self.level = QSpinBox()
        self.level.setRange(1, 10)
        form.addRow(tr("custom_cmd"), self.cmd)
        form.addRow(tr("level_short"), self.level)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def value(self):
        text = self.cmd.text().strip().split(" ")[0]
        if not text:
            return None
        if not text.startswith("/"):
            text = "/" + text
        return {"cmd": text, "level": self.level.value()}


class LevelDialog(QDialog):
    """Shown once, on the very first start: asks for the admin level."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("title"))
        self.setModal(True)
        self.setFixedWidth(400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(GAP, GAP, GAP, GAP)
        lay.setSpacing(16)
        q = QLabel(tr("ask_level"))
        q.setWordWrap(True)
        q.setStyleSheet("font-size: 16px; font-weight: 500;")
        hint = QLabel(tr("ask_level_hint"))
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self.spin = QSpinBox()
        self.spin.setRange(1, 10)
        self.spin.setValue(1)
        btn = QPushButton(tr("ok"))
        btn.setObjectName("primary")
        btn.setDefault(True)
        btn.clicked.connect(self.accept)
        lay.addWidget(q)
        lay.addWidget(hint)
        lay.addWidget(self.spin)
        lay.addSpacing(8)
        lay.addWidget(btn)

    def value(self):
        return self.spin.value()


class Toast(QLabel):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: %s; color: %s; border: 1px solid %s; "
                           "padding: 10px 16px; border-radius: %dpx; font-size: 13px;"
                           % (C_BG, C_TEXT, C_BORDER_HI, RADIUS))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_text(self, text):
        self.setText(text)
        self.adjustSize()
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 24, scr.bottom() - self.height() - 24)
        self.show()
        self.timer.start(1500)


# ----------------------------------------------------------------------------
# UI pieces
# ----------------------------------------------------------------------------

class Tile(QPushButton):
    def __init__(self, main, cmd, cat):
        super().__init__()
        self.main, self.cmd = main, cmd
        self.cat = cat
        self.bid = "cmd:" + cmd
        self.setObjectName("tile")
        self.setFixedHeight(84)
        self.setCursor(Qt.PointingHandCursor)
        combo = main.cfg["binds"].get(self.bid)

        name = html.escape(cmd)
        if cmd in main.cfg["favorites"]:
            name = '<span style="color:%s">&#9733;</span>&nbsp; %s' % (C_ACCENT, name)
        lbl_name = QLabel(name)
        lbl_name.setObjectName("tilename")
        lbl_name.setTextFormat(Qt.RichText)
        lbl_bind = QLabel(fmt_combo(combo) if combo else tr("unbound"))
        lbl_bind.setObjectName("tilebind")
        if combo:
            lbl_bind.setStyleSheet("color: %s;" % C_ACCENT)
        arrow = QLabel("\u2197")
        arrow.setObjectName("arrow")
        for w in (lbl_name, lbl_bind, arrow):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

        lay = QGridLayout(self)
        lay.setContentsMargins(PAD, PAD, PAD, PAD)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(4)
        lay.addWidget(lbl_name, 0, 0)
        bind_row = QHBoxLayout()
        bind_row.setContentsMargins(0, 0, 0, 0)
        bind_row.setSpacing(8)
        bind_row.addWidget(lbl_bind)
        if combo:
            trash = IconButton("trash", 14)
            trash.setFixedSize(20, 20)
            trash.setToolTip(tr("clear_bind"))
            trash.clicked.connect(lambda: main.clear_bind(self.bid))
            bind_row.addWidget(trash)
        bind_row.addStretch(1)
        lay.addLayout(bind_row, 1, 0)
        lay.addWidget(arrow, 0, 1, 2, 1, Qt.AlignRight | Qt.AlignBottom)
        lay.setColumnStretch(0, 1)

        self.clicked.connect(lambda: main.capture_bind(self.bid))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)

    def show_menu(self, pos):
        cfg = self.main.cfg
        menu = QMenu(self)
        is_fav = self.cmd in cfg["favorites"]
        a_fav = menu.addAction(tr("fav_remove") if is_fav else tr("fav_add"))
        a_clear = menu.addAction(tr("clear_bind")) if self.bid in cfg["binds"] else None
        a_del = menu.addAction(tr("delete")) if self.cat == "custom" else None
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is a_fav:
            if is_fav:
                cfg["favorites"].remove(self.cmd)
            else:
                cfg["favorites"].append(self.cmd)
        elif chosen is a_clear:
            cfg["binds"].pop(self.bid, None)
        elif chosen is a_del:
            cfg["custom_commands"] = [c for c in cfg["custom_commands"] if c["cmd"] != self.cmd]
            cfg["binds"].pop(self.bid, None)
            if self.cmd in cfg["favorites"]:
                cfg["favorites"].remove(self.cmd)
        cfg.save()
        self.main.apply_hotkeys()
        QTimer.singleShot(0, self.main.rebuild)


class TilesView(QWidget):
    COLS = 3

    def __init__(self, main, fav_only=False):
        super().__init__()
        self.main, self.fav_only = main, fav_only
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 24, 0, 0)
        lay.setSpacing(24)
        top = QHBoxLayout()
        top.setSpacing(16)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("search"))
        self.search.textChanged.connect(self.refresh)
        top.addWidget(self.search, 1)
        badge = QLabel("%s %d" % (tr("level_short"), main.cfg["level"]))
        badge.setObjectName("badge")
        badge.setFixedHeight(24)
        top.addWidget(badge)
        lay.addLayout(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll)
        self.refresh()

    def refresh(self):
        cfg = self.main.cfg
        text = self.search.text().strip().lower()
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 16)
        col.setSpacing(GAP + 16)
        shown = 0
        cmds = [c for c in all_commands(cfg) if c[1] <= cfg["level"]]
        for cat in CATS:
            items = [c for c in cmds if c[2] == cat and text in c[0].lower()
                     and (not self.fav_only or c[0] in cfg["favorites"])]
            if not items:
                continue
            section = QVBoxLayout()
            section.setSpacing(16)
            head = QLabel(T["en"]["cat_" + cat])
            head.setObjectName("catlabel")
            section.addWidget(head)
            grid = QGridLayout()
            grid.setHorizontalSpacing(GAP)
            grid.setVerticalSpacing(GAP)
            for c in range(self.COLS):
                grid.setColumnStretch(c, 1)
            for i, (cmd, _lvl, _cat) in enumerate(items):
                grid.addWidget(Tile(self.main, cmd, cat), i // self.COLS, i % self.COLS)
                shown += 1
            section.addLayout(grid)
            col.addLayout(section)
        if self.fav_only and shown == 0 and not text:
            hint = QLabel(tr("empty_fav"))
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            col.addWidget(hint)
        col.addStretch(1)
        self.scroll.setWidget(inner)


class TitleBar(QWidget):
    def __init__(self, main, items):
        super().__init__()
        self.main = main
        self.setObjectName("titlebar")
        self.setFixedHeight(32)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        left = QWidget()
        ll = QHBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(crescent_pixmap(20))
        logo.setFixedSize(20, 20)
        ll.addWidget(logo)
        title = QLabel(tr("title"))
        title.setObjectName("title")
        ll.addWidget(title)
        ll.addStretch(1)

        center = QHBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(24)
        self.nav = []
        for idx, text in items:
            b = NavButton(text, idx)
            b.clicked.connect(lambda _c=False, i=idx: main.go_tab(i))
            center.addWidget(b)
            self.nav.append(b)

        right = QWidget()
        rl = QHBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        rl.addStretch(1)
        gear = IconButton("gear", 16, C_NAV, cta=True)
        gear.setFixedSize(28, 28)
        gear.setToolTip(tr("tab_settings"))
        gear.clicked.connect(main.show_settings)
        rl.addWidget(gear)
        rl.addSpacing(8)
        mini = IconButton("min", 16, C_NAV)
        mini.clicked.connect(main.showMinimized)
        self.max_btn = IconButton("restore" if main.isMaximized() else "max", 16, C_NAV)
        self.max_btn.clicked.connect(main.toggle_maximize)
        close = IconButton("close", 16, C_NAV)
        close.clicked.connect(main.hide_window)
        for w in (mini, self.max_btn, close):
            w.setFixedSize(36, 28)
            rl.addWidget(w)

        lay.addWidget(left, 1)
        lay.addLayout(center)
        lay.addWidget(right, 1)

    def set_active(self, idx):
        for b in self.nav:
            b.setChecked(b.index == idx)

    def sync_max(self, maximized):
        self.max_btn.set_kind("restore" if maximized else "max")

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.main.toggle_maximize()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------

class Main(QWidget):
    def __init__(self, cfg, hk):
        super().__init__()
        self.cfg, self.hk = cfg, hk
        self.toast = Toast()
        self.last_send = 0.0
        self.dirty = False
        self.tabs = None
        self.console_lines = ["Admin Panel console. Type /help for commands."]
        self.setWindowTitle(tr("title"))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(900, 520)
        x, y, w, h = cfg["window"]
        self.resize(w, h)
        if x is not None:
            self.move(x, y)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.root = QFrame()
        self.root.setObjectName("root")
        outer.addWidget(self.root)
        self.root_lay = QVBoxLayout(self.root)
        self.root_lay.setContentsMargins(1, 1, 1, 1)
        self.root_lay.setSpacing(0)

        self.apply_theme()
        self.build_ui()
        self.setWindowOpacity(cfg["opacity"] / 100.0)

        self.tray = QSystemTrayIcon(self.make_icon(), self)
        menu = QMenu()
        menu.addAction(tr("title"), self.toggle_window)
        menu.addAction(tr("quit"), self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda _r: self.toggle_window())
        self.tray.show()

        hk.fired.connect(self.on_fired)
        self.apply_hotkeys()
        if hk.error:
            self.toast.show_text(tr("hook_error"))

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def make_icon():
        return QIcon(crescent_pixmap(64, bg=C_BG))

    def apply_theme(self):
        self.setStyleSheet(make_qss())

    def apply_hotkeys(self):
        self.hk.apply(self.cfg["binds"])

    def rebuild(self):
        idx = self.tabs.currentIndex() if self.tabs is not None else 0
        self.build_ui()
        self.tabs.setCurrentIndex(min(idx, self.tabs.count() - 1))
        self.dirty = False

    def bind_label(self, bid):
        if bid.startswith("cmd:"):
            return bid[4:]
        return {"act:report_add": tr("add_report"),
                "act:report_remove": tr("remove_report"),
                "act:toggle": tr("toggle_key")}.get(bid, bid)

    # ---- UI ----------------------------------------------------------------
    def build_ui(self):
        while self.root_lay.count():
            it = self.root_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(4)
        self.root_lay.addWidget(bar)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(GAP, 24, GAP, 12)
        bl.setSpacing(0)
        # pages: 0 commands, 1 favorites, 2 reports, 3 notes, 4 history,
        #        5 settings (gear in the header), 6 console
        self.tabs = QStackedWidget()
        for page in (TilesView(self, False), TilesView(self, True), self.build_reports(),
                     self.build_notes(), self.build_history(), self.build_settings(),
                     self.build_console()):
            self.tabs.addWidget(page)
        items = [(0, tr("tab_commands")), (1, tr("tab_favorites")), (2, tr("tab_reports")),
                 (3, tr("tab_notes")), (4, tr("tab_history")), (6, tr("tab_console"))]
        self.title_bar = TitleBar(self, items)
        self.tabs.currentChanged.connect(self.title_bar.set_active)
        self.title_bar.set_active(self.tabs.currentIndex())
        bl.addWidget(self.title_bar)
        bl.addWidget(self.tabs, 1)
        grip_row = QWidget()
        gl = QHBoxLayout(grip_row)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.addStretch(1)
        gl.addWidget(QSizeGrip(self))
        bl.addWidget(grip_row)
        self.root_lay.addWidget(body, 1)

    def go_tab(self, idx):
        self.tabs.setCurrentIndex(idx)
        self.title_bar.set_active(idx)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            try:
                bar = getattr(self, "title_bar", None)
                if bar is not None:
                    bar.sync_max(self.isMaximized())
            except RuntimeError:
                pass

    def show_settings(self):
        self.tabs.setCurrentIndex(5)

    def bind_button(self, bid):
        combo = self.cfg["binds"].get(bid)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        b = QPushButton("%s: %s" % (tr("bind"), fmt_combo(combo) if combo else tr("unbound")))
        b.clicked.connect(lambda: self.capture_bind(bid))
        rl.addWidget(b, 1)
        if combo and bid != "act:toggle":
            trash = IconButton("trash", 16)
            trash.setFixedSize(34, 34)
            trash.setToolTip(tr("clear_bind"))
            trash.clicked.connect(lambda: self.clear_bind(bid))
            rl.addWidget(trash)
        return row

    def clear_bind(self, bid):
        if bid == "act:toggle":
            return
        self.cfg["binds"].pop(bid, None)
        self.cfg.save()
        self.apply_hotkeys()
        QTimer.singleShot(0, self.rebuild)

    def build_reports(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 24, 0, 0)
        lay.setSpacing(16)
        today, week = report_counts(self.cfg["reports"])
        cards = QHBoxLayout()
        cards.setSpacing(GAP)
        for label, val in ((tr("today"), today), (tr("week"), week)):
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(PAD, PAD, PAD, PAD)
            cl.setSpacing(8)
            cap = QLabel(label)
            cap.setObjectName("caption")
            big = QLabel(str(val))
            big.setObjectName("big")
            cl.addWidget(cap)
            cl.addWidget(big)
            cards.addWidget(card, 1)
        lay.addLayout(cards)

        actions = QHBoxLayout()
        actions.setSpacing(GAP)
        for bid, text, primary, slot in (
                ("act:report_add", tr("add_report"), True, self.report_add),
                ("act:report_remove", tr("remove_report"), False, self.report_remove)):
            col = QVBoxLayout()
            col.setSpacing(8)
            btn = QPushButton(text)
            if primary:
                btn.setObjectName("primary")
            else:
                btn.setObjectName("secondary")
            btn.clicked.connect(slot)
            col.addWidget(btn)
            col.addWidget(self.bind_button(bid))
            actions.addLayout(col, 1)
        lay.addLayout(actions)

        hint = QLabel(tr("reports_hint"))
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        recent = QLabel(tr("recent"))
        recent.setObjectName("catlabel")
        lay.addWidget(recent)
        self.report_list = QListWidget()
        for ts in sorted(self.cfg["reports"], reverse=True)[:30]:
            item = QListWidgetItem(fmt_time(ts))
            item.setData(Qt.UserRole, ts)
            self.report_list.addItem(item)
        lay.addWidget(self.report_list, 1)
        rm = QPushButton(tr("remove_selected"))
        rm.clicked.connect(self.report_remove_selected)
        lay.addWidget(rm)
        return w

    def build_notes(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 24, 0, 0)
        lay.setSpacing(16)
        row = QHBoxLayout()
        self.note_player = QLineEdit()
        self.note_player.setPlaceholderText(tr("player"))
        self.note_text = QLineEdit()
        self.note_text.setPlaceholderText(tr("note"))
        add = QPushButton(tr("add"))
        add.clicked.connect(self.note_add)
        self.note_text.returnPressed.connect(self.note_add)
        row.addWidget(self.note_player, 1)
        row.addWidget(self.note_text, 2)
        row.addWidget(add)
        lay.addLayout(row)
        self.note_list = QListWidget()
        for n in sorted(self.cfg["notes"], key=lambda n: n["t"], reverse=True):
            item = QListWidgetItem("%s  -  %s   (%s)" % (n["player"], n["text"], fmt_time(n["t"])))
            item.setData(Qt.UserRole, n["t"])
            self.note_list.addItem(item)
        lay.addWidget(self.note_list, 1)
        rm = QPushButton(tr("delete"))
        rm.clicked.connect(self.note_delete)
        lay.addWidget(rm)
        return w

    def build_history(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 24, 0, 0)
        lay.setSpacing(16)
        hint = QLabel(tr("history_hint"))
        hint.setObjectName("muted")
        lay.addWidget(hint)
        lst = QListWidget()
        for ts, cmd in reversed(self.cfg["history"]):
            lst.addItem("%s   %s" % (fmt_time(ts), cmd))
        lay.addWidget(lst, 1)
        clr = QPushButton(tr("clear_history"))
        clr.clicked.connect(self.history_clear)
        lay.addWidget(clr)
        return w

    def build_console(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 24, 0, 0)
        lay.setSpacing(16)
        self.console_out = QPlainTextEdit()
        self.console_out.setObjectName("console")
        self.console_out.setReadOnly(True)
        self.console_out.setPlainText("\n".join(self.console_lines))
        bar = self.console_out.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.console_in = QLineEdit()
        self.console_in.setObjectName("consoleinput")
        self.console_in.setPlaceholderText(tr("console_placeholder"))
        self.console_in.returnPressed.connect(self.console_submit)
        lay.addWidget(self.console_out, 1)
        lay.addWidget(self.console_in)
        return w

    def console_submit(self):
        text = self.console_in.text().strip()
        self.console_in.clear()
        if not text:
            return
        self.console_lines.append("> " + text)
        result = self.console_exec(text)
        if result is None:
            self.console_lines = []
        else:
            self.console_lines.extend(result)
        del self.console_lines[:-300]
        self.console_out.setPlainText("\n".join(self.console_lines))
        bar = self.console_out.verticalScrollBar()
        bar.setValue(bar.maximum())

    def console_exec(self, text):
        parts = text.split()
        cmd, args = parts[0].lower(), parts[1:]
        if cmd == "/help":
            return ["/help             show this list",
                    "/alevel           show your admin level",
                    "/aupgrade <level> raise your admin level (1-10)",
                    "/clear            clear the console"]
        if cmd == "/alevel":
            return ["Admin level: %d" % self.cfg["level"]]
        if cmd == "/clear":
            return None
        if cmd == "/aupgrade":
            if len(args) != 1 or not (args[0].isascii() and args[0].isdigit()):
                return ["Usage: /aupgrade <level>"]
            lvl = int(args[0])
            cur = self.cfg["level"]
            if lvl < 1 or lvl > 10:
                return ["Level must be between 1 and 10."]
            if lvl <= cur:
                return ["Your level is already %d. /aupgrade can only raise it." % cur]
            self.cfg["level"] = lvl
            self.cfg.save()
            QTimer.singleShot(0, self.after_upgrade)
            return ["Admin level raised: %d -> %d" % (cur, lvl)]
        return ["Unknown command: %s (try /help)" % cmd]

    def after_upgrade(self):
        self.rebuild()
        self.console_in.setFocus()

    def build_settings(self):
        cfg = self.cfg
        pane = QWidget()
        pane.setObjectName("pane")
        outer = QVBoxLayout(pane)
        outer.setContentsMargins(0, 24, 12, 24)
        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(PAD, PAD, PAD, PAD)
        form.setVerticalSpacing(16)
        form.setHorizontalSpacing(GAP)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        lang = QComboBox()
        for code, name in LANGS.items():
            lang.addItem(name, code)
        lang.setCurrentIndex(list(LANGS).index(cfg["language"]) if cfg["language"] in LANGS else 0)
        lang.currentIndexChanged.connect(lambda i: self.set_setting("language", lang.itemData(i), True))
        form.addRow(tr("language"), lang)

        auto_chat = QCheckBox(tr("auto_chat"))
        auto_chat.setChecked(bool(cfg["auto_chat"]))
        form.addRow("", auto_chat)

        chat = QLineEdit(cfg["chat_key"])
        chat.setMaximumWidth(120)
        chat.textChanged.connect(lambda t: self.set_setting("chat_key", t.strip() or "t", False))
        form.addRow(tr("chat_key"), chat)

        delay = QSpinBox()
        delay.setRange(10, 1000)
        delay.setSingleStep(10)
        delay.setValue(cfg["key_delay_ms"])
        delay.valueChanged.connect(lambda v: self.set_setting("key_delay_ms", v, False))
        form.addRow(tr("key_delay"), delay)

        def on_auto_chat(on):
            self.set_setting("auto_chat", bool(on), False)
            chat.setEnabled(bool(on))
            delay.setEnabled(bool(on))

        auto_chat.toggled.connect(on_auto_chat)
        chat.setEnabled(bool(cfg["auto_chat"]))
        delay.setEnabled(bool(cfg["auto_chat"]))

        cool = QSpinBox()
        cool.setRange(0, 5000)
        cool.setSingleStep(50)
        cool.setValue(cfg["cooldown_ms"])
        cool.valueChanged.connect(lambda v: self.set_setting("cooldown_ms", v, False))
        form.addRow(tr("cooldown"), cool)

        op = QSlider(Qt.Horizontal)
        op.setRange(40, 100)
        op.setValue(cfg["opacity"])
        op.valueChanged.connect(self.set_opacity)
        form.addRow(tr("opacity"), op)

        form.addRow(tr("toggle_key"), self.bind_button("act:toggle"))

        auto = QCheckBox(tr("autostart"))
        auto.setChecked(cfg["autostart"])
        auto.toggled.connect(self.set_autostart_pref)
        form.addRow("", auto)

        btns = QHBoxLayout()
        btns.setSpacing(16)
        for text, slot in ((tr("export_binds"), self.export_binds),
                           (tr("import_binds"), self.import_binds),
                           (tr("add_custom"), self.add_custom),
                           (tr("quit"), self.quit_app)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
        form.addRow(btns)

        if self.hk.error:
            err = QLabel(tr("hook_error"))
            err.setWordWrap(True)
            err.setStyleSheet("color: %s;" % C_ACCENT)
            form.addRow(err)

        outer.addWidget(card)
        outer.addStretch(1)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(pane)
        return sc

    # ---- settings handlers -------------------------------------------------
    def set_setting(self, key, value, rebuild):
        self.cfg[key] = value
        self.cfg.save()
        if key == "language":
            set_lang(value)
        if rebuild:
            QTimer.singleShot(0, self.rebuild)

    def set_opacity(self, v):
        self.cfg["opacity"] = v
        self.setWindowOpacity(v / 100.0)
        self.cfg.save()

    def set_autostart_pref(self, on):
        self.cfg["autostart"] = bool(on)
        self.cfg.save()
        set_autostart(bool(on))

    def add_custom(self):
        dlg = CustomCommandDialog(self)
        if dlg.exec() == QDialog.Accepted:
            val = dlg.value()
            if val and all(val["cmd"] != c[0] for c in all_commands(self.cfg)):
                self.cfg["custom_commands"].append(val)
                self.cfg.save()
                QTimer.singleShot(0, self.rebuild)

    def export_binds(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("export_binds"),
                                              "adminpanel_binds.json", "JSON (*.json)")
        if not path:
            return
        data = {k: self.cfg[k] for k in ("binds", "favorites", "custom_commands")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.toast.show_text(tr("exported"))

    def import_binds(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("import_binds"), "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for k in ("binds", "favorites", "custom_commands"):
                if k in data:
                    self.cfg[k] = data[k]
            self.cfg["binds"].setdefault("act:toggle", "insert")
            self.cfg.save()
            self.apply_hotkeys()
            self.rebuild()
            self.toast.show_text(tr("imported"))
        except Exception as e:
            QMessageBox.warning(self, "", str(e))

    # ---- binds -------------------------------------------------------------
    def owner_of(self, combo, exclude):
        for bid, c in self.cfg["binds"].items():
            if c == combo and bid != exclude:
                return bid
        return None

    def capture_bind(self, bid):
        if keyboard is None:
            QMessageBox.warning(self, "", tr("hook_error"))
            return
        self.hk.clear()  # old binds must not fire while we listen
        dlg = CaptureDialog(self)
        dlg.exec()
        combo = dlg.combo
        cleared = dlg.cleared
        dlg.deleteLater()
        if cleared and bid != "act:toggle":
            self.cfg["binds"].pop(bid, None)
            self.cfg.save()
        elif combo:
            owner = self.owner_of(combo, bid)
            ok = True
            if owner == "act:toggle":
                QMessageBox.information(self, "", tr("toggle_busy"))
                ok = False
            elif owner:
                q = QMessageBox.question(self, "", tr("replace_q").format(x=self.bind_label(owner)))
                ok = q == QMessageBox.Yes
                if ok:
                    self.cfg["binds"].pop(owner, None)
            if ok:
                self.cfg["binds"][bid] = combo
                self.cfg.save()
        self.apply_hotkeys()
        QTimer.singleShot(0, self.rebuild)

    # ---- reports -----------------------------------------------------------
    def report_add(self):
        self.cfg["reports"].append(time.time())
        self.cfg.save()
        self.after_report("toast_added")

    def report_remove(self):
        if not self.cfg["reports"]:
            self.toast.show_text(tr("nothing"))
            return
        self.cfg["reports"].remove(max(self.cfg["reports"]))
        self.cfg.save()
        self.after_report("toast_removed")

    def report_remove_selected(self):
        item = self.report_list.currentItem()
        if item is None:
            return
        ts = item.data(Qt.UserRole)
        if ts in self.cfg["reports"]:
            self.cfg["reports"].remove(ts)
            self.cfg.save()
        QTimer.singleShot(0, self.rebuild)

    def after_report(self, key):
        today, week = report_counts(self.cfg["reports"])
        self.toast.show_text("%s   %s: %d   %s: %d" % (tr(key), tr("today"), today, tr("week"), week))
        if self.isVisible():
            QTimer.singleShot(0, self.rebuild)
        else:
            self.dirty = True

    # ---- notes / history ---------------------------------------------------
    def note_add(self):
        player, text = self.note_player.text().strip(), self.note_text.text().strip()
        if not (player or text):
            return
        self.cfg["notes"].append({"t": time.time(), "player": player, "text": text})
        self.cfg.save()
        QTimer.singleShot(0, self.rebuild)

    def note_delete(self):
        item = self.note_list.currentItem()
        if item is None:
            return
        ts = item.data(Qt.UserRole)
        self.cfg["notes"] = [n for n in self.cfg["notes"] if n["t"] != ts]
        self.cfg.save()
        QTimer.singleShot(0, self.rebuild)

    def history_clear(self):
        self.cfg["history"] = []
        self.cfg.save()
        QTimer.singleShot(0, self.rebuild)

    # ---- hotkey dispatch ---------------------------------------------------
    def on_fired(self, bid):
        if bid == "act:toggle":
            self.toggle_window()
        elif bid == "act:report_add":
            self.report_add()
        elif bid == "act:report_remove":
            self.report_remove()
        elif bid.startswith("cmd:"):
            now = time.time()
            if (now - self.last_send) * 1000 < self.cfg["cooldown_ms"]:
                return
            self.last_send = now
            cmd = bid[4:]
            hist = self.cfg["history"]
            hist.append([now, cmd])
            del hist[:-500]
            self.cfg.save()
            self.dirty = True
            threading.Thread(target=self.run_type,
                             args=(cmd, self.cfg["binds"].get(bid, "")),
                             daemon=True).start()

    def run_type(self, cmd, combo):
        wait_release(combo)
        self.hk.clear()  # typed letters must not trigger the binds themselves
        try:
            type_command(self.cfg["chat_key"], self.cfg["key_delay_ms"], cmd,
                         bool(self.cfg["auto_chat"]))
        finally:
            self.hk.apply(self.cfg["binds"])

    # ---- window ------------------------------------------------------------
    def save_geometry(self):
        g = self.normalGeometry() if self.isMaximized() else self.geometry()
        self.cfg["window"] = [g.x(), g.y(), g.width(), g.height()]
        self.cfg.save()

    def hide_window(self):
        self.save_geometry()
        self.hide()

    def toggle_window(self):
        if self.isVisible() and not self.isMinimized():
            self.hide_window()
        else:
            if self.dirty:
                self.rebuild()
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, e):
        e.ignore()
        self.hide_window()

    def quit_app(self):
        self.save_geometry()
        self.hk.clear()
        self.tray.hide()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cfg = Config()
    set_lang(cfg["language"])
    hk = HotkeyManager()
    win = Main(cfg, hk)
    if not cfg["level_set"]:
        dlg = LevelDialog(win)
        if dlg.exec() == QDialog.Accepted:
            cfg["level"] = dlg.value()
            cfg["level_set"] = True
            cfg.save()
            win.rebuild()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
