# -*- coding: utf-8 -*-
"""Виджеты интерфейса на Qt: карточки, кнопки, тумблеры, слайдеры, лог и игровое поле."""
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget)
from .theme import (BG, SURFACE, SURFACE_2, SURFACE_3, BORDER, BORDER_HI, TEXT, TEXT_2, TEXT_3,
                    PINK, PINK_DIM, BLUE, GREEN, AMBER, RED, PLAYFIELD, font, mono_font)


def make_pen(color, width=1.0, dash=False, round_cap=False):
    pen = QPen()
    pen.setColor(QColor(color))
    pen.setWidthF(width)
    if dash:
        pen.setStyle(Qt.PenStyle.DashLine)
    if round_cap:
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def hline():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {BORDER};")
    return f


def caption(text, color=TEXT_3, size=9, bold=False):
    lbl = QLabel(text)
    lbl.setFont(font(size, bold))
    lbl.setStyleSheet(f"color: {color};")
    return lbl


class Dot(QWidget):
    """Цветная точка-индикатор."""

    def __init__(self, color, size=8, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(0, 0, self.width(), self.height()))
        p.end()


# ── Карточка ──────────────────────────────────────────────────────────
class Card(QFrame):
    """Карточка с заголовком. Содержимое добавляется через self.body (QVBoxLayout)."""

    def __init__(self, title=None, subtitle=None, pad=18, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if title:
            head = QWidget()
            hl = QHBoxLayout(head)
            hl.setContentsMargins(pad, 13, pad, 13)
            hl.setSpacing(10)
            hl.addWidget(Dot(PINK, 8))
            hl.addWidget(caption(title, TEXT, 11, True))
            if subtitle:
                hl.addWidget(caption(subtitle, TEXT_3, 9))
            hl.addStretch(1)
            outer.addWidget(head)
            outer.addWidget(hline())
        wrap = QWidget()
        self.body = QVBoxLayout(wrap)
        self.body.setContentsMargins(pad, pad, pad, pad)
        self.body.setSpacing(8)
        outer.addWidget(wrap, 1)


def page_header(layout, title, subtitle=""):
    hdr = QWidget()
    v = QVBoxLayout(hdr)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(3)
    t = QLabel(title)
    t.setFont(font(20, True))
    t.setStyleSheet(f"color: {TEXT};")
    v.addWidget(t)
    if subtitle:
        v.addWidget(caption(subtitle, TEXT_3, 10))
    layout.addWidget(hdr)


# ── Кнопка-пилюля ─────────────────────────────────────────────────────
class Button(QPushButton):
    def __init__(self, text, command=None, variant="ghost", parent=None):
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        self.setFont(font(10, True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)
        self._command = command
        self.clicked.connect(self._fire)

    def _fire(self, *_):
        if self._command:
            self._command()

    def set_enabled(self, on):
        self.setEnabled(bool(on))


class Chip(QPushButton):
    """Ссылка-таблетка."""

    def __init__(self, text, command=None, bg=None, fg=None, parent=None):
        super().__init__(text, parent)
        self.setProperty("chip", "yes")
        self.setFont(font(9, True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        if bg:
            self.setStyleSheet(f"background: {bg}; color: {fg or TEXT};")
        self._command = command
        self.clicked.connect(self._fire)

    def _fire(self, *_):
        if self._command:
            self._command()


# ── Тумблер ───────────────────────────────────────────────────────────
class _Switch(QWidget):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setFixedSize(38, 20)

    def paintEvent(self, _):
        on = self._owner.isChecked()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(PINK if on else SURFACE_3))
        p.drawRoundedRect(QRectF(1, 1, 36, 18), 9, 9)
        kx = 29 if on else 9
        p.setBrush(QColor("#ffffff" if on else TEXT_3))
        p.drawEllipse(QPointF(kx, 10), 7, 7)
        p.end()


class Toggle(QWidget):
    changed = Signal(bool)

    def __init__(self, text, checked=False, tip=None, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._sw = _Switch(self)
        lay.addWidget(self._sw)
        self._lbl = QLabel(text)
        self._lbl.setFont(font(10))
        lay.addWidget(self._lbl)
        if tip:
            self.setToolTip(tip)

    def isChecked(self):
        return self._checked

    def setChecked(self, on):
        self._checked = bool(on)
        self._sw.update()
        self.changed.emit(self._checked)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        e.accept()


# ── Слайдер с подписью и значением ────────────────────────────────────
class _Track(QWidget):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setFixedHeight(20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._owner._paint(p, self.width(), self.height())
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._owner._drag(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._owner._drag(e.position().x())


class Slider(QWidget):
    changed = Signal(float)

    def __init__(self, label, lo, hi, step=0, color=PINK, fmt=None, value=None, parent=None):
        super().__init__(parent)
        self._lo, self._hi, self._step = float(lo), float(hi), float(step)
        self._color = color
        self._fmt = fmt or (lambda v: f"{v:.2f}")
        self._value = self._lo if value is None else float(value)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(caption(label, TEXT_2, 9))
        head.addStretch(1)
        self._val_lbl = QLabel()
        self._val_lbl.setFont(font(9, True))
        self._val_lbl.setStyleSheet(f"color: {color};")
        head.addWidget(self._val_lbl)
        v.addLayout(head)
        self._track = _Track(self)
        v.addWidget(self._track)
        self._refresh()

    def value(self):
        return self._value

    def range(self):
        return self._lo, self._hi

    def set_range(self, lo, hi):
        self._lo, self._hi = float(lo), float(hi)
        self.set_value(self._value)

    def set_value(self, v):
        self._value = min(self._hi, max(self._lo, float(v)))
        self._refresh()
        self.changed.emit(self._value)

    def _drag(self, x):
        pad = 8
        w = max(1, self._track.width() - 2 * pad)
        frac = min(1.0, max(0.0, (x - pad) / w))
        v = self._lo + frac * (self._hi - self._lo)
        if self._step:
            v = round(round((v - self._lo) / self._step) * self._step + self._lo, 6)
        self.set_value(v)

    def _refresh(self):
        self._val_lbl.setText(self._fmt(self._value))
        self._track.update()

    def _paint(self, p, w, h):
        pad, y = 8, h / 2
        span = (self._hi - self._lo) or 1
        frac = min(1.0, max(0.0, (self._value - self._lo) / span))
        x_end = pad + frac * (w - 2 * pad)
        p.setPen(make_pen(SURFACE_3, 4, round_cap=True))
        p.drawLine(QPointF(pad, y), QPointF(w - pad, y))
        if x_end > pad + 1:
            p.setPen(make_pen(self._color, 4, round_cap=True))
            p.drawLine(QPointF(pad, y), QPointF(x_end, y))
        p.setPen(make_pen(self._color, 2))
        p.setBrush(QColor(TEXT))
        p.drawEllipse(QPointF(x_end, y), 7, 7)


# ── Поле ввода ────────────────────────────────────────────────────────
class Field(QLineEdit):
    def __init__(self, text="", mono=False, parent=None):
        super().__init__(str(text), parent)
        self.setMinimumHeight(34)
        if mono:
            self.setFont(mono_font(10))


# ── Лог с цветными строками ───────────────────────────────────────────
class Log(QTextEdit):
    TAGS = {"ok": GREEN, "warn": AMBER, "err": RED, "dim": TEXT_3, "info": BLUE}

    def __init__(self, lines=8, parent=None):
        super().__init__(parent)
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setFont(mono_font(9))
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setMinimumHeight(lines * 17 + 24)

    def add(self, msg, tag=None):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self.TAGS.get(tag, TEXT_2)))
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText(msg + "\n", fmt)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_message(self, msg):
        self.clear()
        self.add(msg)

    def get(self):
        return self.toPlainText()


# ── Полоса прогресса фоновой задачи ───────────────────────────────────
class JobBar(QWidget):
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(12)
        self.label = caption("", TEXT_2, 9)
        self.btn = Button("Отмена", lambda: self.cancel_requested.emit(), "ghost")
        row.addWidget(self.bar, 1)
        row.addWidget(self.label)
        row.addWidget(self.btn)
        self.setVisible(False)

    def start(self, total, text="Запуск…"):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(0)
        self.label.setText(text)
        self.btn.setEnabled(True)
        self.setVisible(True)

    def update_progress(self, i, n, msg=""):
        self.bar.setRange(0, max(1, n))
        self.bar.setValue(i)
        self.label.setText(f"{i}/{n}  {msg}".rstrip())

    def finish(self, text):
        self.bar.setValue(self.bar.maximum())
        self.label.setText(text)
        self.btn.setEnabled(False)


def save_png(widget, parent, default_path):
    """Сохраняет содержимое виджета в PNG. Возвращает путь или None, если отменено."""
    path, _ = QFileDialog.getSaveFileName(parent, "Сохранить PNG", default_path, "PNG (*.png)")
    if not path:
        return None
    if not widget.grab().save(path):
        raise OSError(f"Не удалось записать файл: {path}")
    return path


# ── Игровое поле ──────────────────────────────────────────────────────
def fit_playfield(w, h, pw=512.0, ph=384.0, margin=56):
    """Возвращает (scale, ox, oy) для вписывания поля pw×ph в виджет w×h."""
    if w < 50 or h < 50:
        return None
    scale = min((w - margin) / pw, (h - margin) / ph)
    return scale, (w - pw * scale) / 2.0, (h - ph * scale) / 2.0


class Playfield(QWidget):
    """Холст. Рисование делегируется paint_fn(painter, width, height)."""

    def __init__(self, paint_fn, min_height=340, parent=None):
        super().__init__(parent)
        self._paint_fn = paint_fn
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(make_pen(BORDER, 1))
        p.setBrush(QColor(PLAYFIELD))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
        self._paint_fn(p, w, h)
        p.end()


# ── Прокручиваемая страница ───────────────────────────────────────────
def scroll_page():
    """Возвращает (scroll, layout): scroll — окно страницы, layout — куда добавляются блоки."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    inner = QWidget()
    inner.setObjectName("page")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(30, 26, 30, 26)
    lay.setSpacing(16)
    scroll.setWidget(inner)
    return scroll, lay
