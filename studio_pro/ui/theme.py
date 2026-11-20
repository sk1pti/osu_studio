# -*- coding: utf-8 -*-
"""Тема оформления (Qt): палитра, шрифты и таблица стилей."""
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

# ── Поверхности: графит с мягкими переходами ─────────────────────────
BG        = "#0b0c10"   # фон окна
SIDEBAR   = "#101217"   # боковая панель и верхняя полоса
SURFACE   = "#161a23"   # карточки
SURFACE_2 = "#1c2130"   # поля ввода, логи
SURFACE_3 = "#262c3d"   # кнопки и hover
BORDER    = "#232939"
BORDER_HI = "#374060"

# ── Текст ─────────────────────────────────────────────────────────────
TEXT   = "#eef1f8"
TEXT_2 = "#a9b1c6"
TEXT_3 = "#6d7592"

# ── Акценты (в духе osu!) ─────────────────────────────────────────────
PINK, PINK_HOVER, PINK_DIM = "#ff5fa2", "#ff7db5", "#9c3c6c"
BLUE, BLUE_HOVER = "#5cb3ff", "#7ec3ff"
GREEN, GREEN_HOVER = "#4ade80", "#6ee79a"
AMBER, RED = "#fbbf24", "#f87171"
INK = "#0b0c10"          # текст на ярких кнопках
NAV_HOVER = "#151923"
PLAYFIELD = "#080a0e"

UI_FAMILY = "Sans Serif"
MONO_FAMILY = "Monospace"
_cache = {}


def init_fonts():
    """Выбирает лучший доступный шрифт. Вызывать после создания QApplication."""
    global UI_FAMILY, MONO_FAMILY
    avail = set(QFontDatabase.families())
    UI_FAMILY = next((f for f in ("Segoe UI Variable Text", "Segoe UI", "SF Pro Text",
                                  "Helvetica Neue", "Inter", "Ubuntu", "DejaVu Sans") if f in avail),
                     QApplication.font().family())
    MONO_FAMILY = next((f for f in ("Cascadia Code", "JetBrains Mono", "Consolas",
                                    "SF Mono", "Menlo", "DejaVu Sans Mono") if f in avail),
                       "Monospace")
    _cache.clear()


def font(size=10, bold=False):
    key = ("ui", size, bold)
    if key not in _cache:
        f = QFont(UI_FAMILY, size)
        f.setBold(bold)
        _cache[key] = f
    return _cache[key]


def mono_font(size=9):
    key = ("mono", size)
    if key not in _cache:
        f = QFont(MONO_FAMILY, size)
        f.setStyleHint(QFont.StyleHint.Monospace)
        _cache[key] = f
    return _cache[key]


_QSS = """
QMainWindow#root, QWidget#page, QScrollArea { background: $BG; }
QScrollArea { border: none; }

QFrame#card { background: $SURFACE; border: 1px solid $BORDER; border-radius: 12px; }
QFrame#topbar { background: $SIDEBAR; border-bottom: 1px solid $BORDER; }
QFrame#sidebar { background: $SIDEBAR; border-right: 1px solid $BORDER; }
QFrame#statusbar { background: $SIDEBAR; border-top: 1px solid $BORDER; }

QLabel { color: $TEXT; background: transparent; }

QLineEdit {
    background: $SURFACE_2; color: $TEXT;
    border: 1px solid $BORDER; border-radius: 8px;
    padding: 6px 12px; selection-background-color: $PINK_DIM; selection-color: $TEXT;
}
QLineEdit:focus { border: 1px solid $PINK; }

QPushButton {
    background: $SURFACE_3; color: $TEXT; border: none;
    border-radius: 17px; padding: 8px 18px;
}
QPushButton:hover { background: $BORDER_HI; }
QPushButton[variant="primary"] { background: $PINK; color: $INK; }
QPushButton[variant="primary"]:hover { background: $PINK_HOVER; }
QPushButton[variant="success"] { background: $GREEN; color: $INK; }
QPushButton[variant="success"]:hover { background: $GREEN_HOVER; }
QPushButton[variant="info"] { background: $BLUE; color: $INK; }
QPushButton[variant="info"]:hover { background: $BLUE_HOVER; }
QPushButton[variant]:disabled { background: $SURFACE_2; color: $TEXT_3; }
QPushButton[chip="yes"] {
    background: $SURFACE_2; color: $TEXT_2; border-radius: 12px; padding: 5px 12px;
}
QPushButton[chip="yes"]:hover { background: $SURFACE_3; color: $TEXT; }

QComboBox {
    background: $SURFACE_2; color: $TEXT; border: 1px solid $BORDER;
    border-radius: 8px; padding: 5px 10px; min-height: 22px;
}
QComboBox:focus, QComboBox:on { border: 1px solid $PINK; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $SURFACE_2; color: $TEXT; selection-background-color: $PINK_DIM;
    border: 1px solid $BORDER_HI; outline: none;
}

QTextEdit#log {
    background: $SURFACE_2; color: $TEXT_2; border: 1px solid $BORDER;
    border-radius: 10px; padding: 8px 12px;
}

QListWidget, QTreeWidget {
    background: $SURFACE_2; color: $TEXT; border: 1px solid $BORDER;
    border-radius: 10px; padding: 4px; outline: none;
}
QListWidget::item { padding: 5px 8px; border-radius: 6px; }
QListWidget::item:selected { background: $PINK_DIM; color: $TEXT; }
QTreeWidget::item { padding: 5px 6px; }
QTreeWidget::item:selected { background: $PINK_DIM; color: $TEXT; }
QHeaderView::section {
    background: $SURFACE_3; color: $TEXT_2; border: none; padding: 6px 10px;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $SURFACE_3; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $BORDER_HI; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: $SURFACE_3; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

QProgressBar {
    background: $SURFACE_2; border: 1px solid $BORDER; border-radius: 6px;
    height: 10px; text-align: center; color: $TEXT_2;
}
QProgressBar::chunk { background: $PINK; border-radius: 5px; }

QToolTip {
    background: $SURFACE_3; color: $TEXT; border: 1px solid $BORDER_HI; padding: 6px 10px;
}
QMessageBox { background: $SURFACE; }
"""


def build_stylesheet():
    colors = {k: v for k, v in globals().items()
              if k.isupper() and isinstance(v, str) and v.startswith("#")}
    return Template(_QSS).substitute(colors)


def apply_theme(app):
    """Применяет тему ко всему приложению. Вызывать до создания окна."""
    init_fonts()
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(SURFACE_2))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(SURFACE_3))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(PINK))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(INK))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE_3))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    app.setPalette(pal)
    app.setFont(font(10))
    app.setStyleSheet(build_stylesheet())
