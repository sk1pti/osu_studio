# -*- coding: utf-8 -*-
"""Главное окно (Qt): верхняя полоса, боковое меню, страницы и строка статуса."""
import logging
import os
import sys

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..config import (D_IN, D_REF, D_WIP, D_OUT, D_UTIL, APP_VERSION, UPDATE_MANIFEST_URL,
                      ensure_dirs, load_settings, save_settings)
from .. import updater
from .worker import Job
from ..utils.fs import open_dir
from .theme import (BG, SIDEBAR, SURFACE_2, BORDER, TEXT, TEXT_2, TEXT_3, PINK, BLUE,
                    GREEN, AMBER, RED, NAV_HOVER, font, apply_theme)
from .widgets import Chip, Dot, Button
from .pages import humanize, cube, tuner, builder, lint, refs, tags, cfg

NAV = [
    ("humanize", "Хуманизатор ИИ", "Очеловечить .osu / .osz"),
    ("cube", "Лвл-Куб 1:1", "Квадратное поле 384×384"),
    ("tune", "Тюннер карты", "CS · AR · OD · HP · звук"),
    ("build", "Сборщик сета", "Упаковка в .osz"),
    ("lint", "Линтер", "Проверка ошибок"),
    ("ref", "Референсы", "Извлечь .osu из .osz"),
    ("tags", "Теги", "Метаданные и описание"),
    ("cfg", "Конфиг ИИ", "Mapperatorinator"),
]
VERSION = "v" + APP_VERSION


class Logo(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(34, 34)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(PINK))
        p.drawEllipse(QRectF(1, 1, 32, 32))
        p.setPen(QColor(BG))
        p.setFont(font(10, True))
        p.drawText(QRectF(0, 0, 34, 34), Qt.AlignmentFlag.AlignCenter, "o!")
        p.end()


class NavItem(QFrame):
    clicked = Signal()

    def __init__(self, title, sub):
        super().__init__()
        self.setObjectName("navitem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active = False
        self._hover = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._ind = QFrame()
        self._ind.setFixedWidth(3)
        row.addWidget(self._ind)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(14, 9, 14, 9)
        col.setSpacing(1)
        self._title = QLabel(title)
        self._title.setFont(font(10, True))
        sub_lbl = QLabel(sub)
        sub_lbl.setFont(font(8))
        sub_lbl.setStyleSheet(f"color: {TEXT_3};")
        col.addWidget(self._title)
        col.addWidget(sub_lbl)
        row.addWidget(inner, 1)
        self._restyle()

    def set_active(self, on):
        self._active = bool(on)
        self._restyle()

    def _restyle(self):
        bg = SURFACE_2 if self._active else (NAV_HOVER if self._hover else SIDEBAR)
        self.setStyleSheet(f"#navitem {{ background: {bg}; }}")
        self._ind.setStyleSheet(f"background: {PINK if self._active else bg};")
        self._title.setStyleSheet(f"color: {TEXT if self._active else TEXT_2};")

    def enterEvent(self, e):
        self._hover = True
        self._restyle()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._restyle()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAcceptDrops(True)
        self.setWindowTitle("osu! Studio PRO")
        self.setMinimumSize(1120, 760)
        self.resize(1280, 860)

        self.build_files = []
        self.nav = {}
        self.pages = {}
        self.active_page = None
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._reset_status)

        settings = load_settings()
        geo = settings.get("window_geometry")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._topbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        root.addWidget(self._statusbar())

        self.pages = {
            "humanize": humanize.Page(self), "cube": cube.Page(self), "tune": tuner.Page(self),
            "build": builder.Page(self), "lint": lint.Page(self), "ref": refs.Page(self),
            "tags": tags.Page(self), "cfg": cfg.Page(self),
        }
        for page in self.pages.values():
            self.stack.addWidget(page.view)

        start = settings.get("last_page")
        self.switch_page(start if start in self.pages else "humanize")
        self._bind_hotkeys()
        self.notify("Готово к работе", "info")
        if self._update_check_due(settings):
            QTimer.singleShot(3000, lambda: self.check_updates(manual=False))

    # ── Обновления ────────────────────────────────────────────────────
    @staticmethod
    def _update_check_due(settings):
        import time
        last = settings.get("last_update_check", 0)
        return time.time() - float(last or 0) > 24 * 3600

    def check_updates(self, manual=True):
        """Проверка в фоне. manual=False — тихо, без сообщений, если обновлений нет или сеть недоступна."""
        import time
        if getattr(self, "_update_job", None) is not None and self._update_job.isRunning():
            return self.notify("Проверка уже идёт", "warn") if manual else None
        job = Job(lambda j: updater.check_for_update(APP_VERSION, UPDATE_MANIFEST_URL), self)
        job.on_done = lambda m: self._on_update_checked(m, manual)
        job.on_fail = lambda msg: (self.notify(f"Обновления: {msg}", "err") if manual else None)
        data = load_settings()
        data["last_update_check"] = time.time()
        save_settings(data)
        self._update_job = job
        if manual:
            self.notify("Проверяю обновления…", "info")
        job.start()

    def _on_update_checked(self, manifest, manual):
        if not manifest:
            if manual:
                self.notify(f"Установлена актуальная версия {APP_VERSION}", "ok")
            return
        notes = manifest.get("notes", "") or "Исправления и улучшения."
        ans = QMessageBox.question(
            self, "Доступно обновление",
            f"Вышла версия {manifest['version']} (у вас {APP_VERSION}).\n\n{notes}\n\nОбновить сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._start_download(manifest)

    def _start_download(self, manifest):
        job = Job(lambda j: updater.download_installer(manifest), self)
        job.on_done = self._on_downloaded
        job.on_fail = lambda msg: (self.notify(f"Не удалось скачать: {msg}", "err"),
                                   QMessageBox.warning(self, "Обновление", msg))
        self.notify("Скачиваю обновление…", "info")
        self._download_job = job
        job.start()

    def _on_downloaded(self, path):
        try:
            updater.launch_installer(path)
        except updater.UpdateError as e:
            return QMessageBox.information(self, "Обновление", f"Установщик скачан:\n{path}\n\n{e}")
        self.close()

    # ── Разметка ──────────────────────────────────────────────────────
    def _topbar(self):
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(60)
        lay = QHBoxLayout(top)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)
        lay.addWidget(Logo())

        titles = QVBoxLayout()
        titles.setSpacing(0)
        t1 = QLabel("osu! Studio")
        t1.setFont(font(12, True))
        t2 = QLabel("PRO · Ultimate")
        t2.setFont(font(8))
        t2.setStyleSheet(f"color: {TEXT_3};")
        titles.addWidget(t1)
        titles.addWidget(t2)
        lay.addLayout(titles)
        lay.addStretch(1)

        lbl = QLabel("Папки")
        lbl.setFont(font(9))
        lbl.setStyleSheet(f"color: {TEXT_3};")
        lay.addWidget(lbl)
        folders = (("1_input", D_IN), ("2_refs", D_REF), ("3_wip", D_WIP), ("4_ready_osz", D_OUT))
        for txt, d in folders:
            lay.addWidget(Chip(txt, lambda p=d: open_dir(str(p)), bg=SURFACE_2, fg=TEXT_2))
        return top

    def _sidebar(self):
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(252)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(12, 22, 12, 18)
        lay.setSpacing(2)

        head = QLabel("РАБОЧАЯ ОБЛАСТЬ")
        head.setFont(font(8, True))
        head.setStyleSheet(f"color: {TEXT_3};")
        head.setContentsMargins(10, 0, 0, 10)
        lay.addWidget(head)

        for key, title, sub in NAV:
            item = NavItem(title, sub)
            item.clicked.connect(lambda k=key: self.switch_page(k))
            self.nav[key] = item
            lay.addWidget(item)

        lay.addStretch(1)
        for txt in ("Ctrl+O  открыть файл", "Ctrl+Z  сбросить превью", "F5  обработать"):
            lay.addWidget(self._foot_label(txt, TEXT_3))
        lay.addWidget(Button("Проверить обновления", lambda: self.check_updates(manual=True), "ghost"))
        ver = self._foot_label(VERSION, BORDER)
        ver.setFont(font(8, True))
        lay.addWidget(ver)
        return sb

    @staticmethod
    def _foot_label(text, color):
        lbl = QLabel(text)
        lbl.setFont(font(8))
        lbl.setStyleSheet(f"color: {color}; padding-left: 10px;")
        return lbl

    def _statusbar(self):
        bar = QFrame()
        bar.setObjectName("statusbar")
        bar.setFixedHeight(30)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(10)
        self._dot = Dot(BLUE, 8)
        lay.addWidget(self._dot)
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(font(9))
        lay.addWidget(self.status_lbl, 1)
        return bar

    # ── Навигация ─────────────────────────────────────────────────────
    def switch_page(self, key):
        if key == self.active_page or key not in self.pages:
            return
        if self.active_page:
            self.nav[self.active_page].set_active(False)
        self.active_page = key
        self.nav[key].set_active(True)
        self.stack.setCurrentWidget(self.pages[key].view)

    # ── Уведомления в статус-баре ─────────────────────────────────────
    def notify(self, msg, kind="info"):
        color = {"ok": GREEN, "warn": AMBER, "err": RED}.get(kind, BLUE)
        self._dot.set_color(color)
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet(f"color: {TEXT};")
        self._status_timer.start(6000)

    def _reset_status(self):
        self._dot.set_color(BLUE)
        self.status_lbl.setText("Готово")
        self.status_lbl.setStyleSheet(f"color: {TEXT_3};")

    # ── Горячие клавиши ───────────────────────────────────────────────
    def _bind_hotkeys(self):
        shortcuts = (
            ("Ctrl+O", lambda: self._page_action("pick_file" if self.active_page == "cube" else "h_pick_file")),
            ("Ctrl+Z", lambda: self._page_action("action_undo")),
            ("F5", lambda: self._page_action("action_cubify" if self.active_page == "cube" else "action_humanize")),
        )
        self._shortcuts = []
        for seq, fn in shortcuts:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(fn)
            self._shortcuts.append(sc)

    # ── Перетаскивание карт в окно ────────────────────────────────────
    DROP_EXTS = (".osu", ".osz")

    def dragEnterEvent(self, event):
        if self._drop_path(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self._drop_path(event)
        if path:
            event.acceptProposedAction()
            self.open_path(path)
        else:
            event.ignore()

    def _drop_path(self, event):
        if not event.mimeData().hasUrls():
            return None
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(self.DROP_EXTS):
                return p
        return None

    def open_path(self, path):
        """Открывает карту на текущей странице (куб) или в хуманизаторе."""
        if self.active_page == "cube":
            self.pages["cube"]._load_target_path(path)
        else:
            self.switch_page("humanize")
            self.pages["humanize"].load_path(path)
        self.notify(f"Открыто: {os.path.basename(path)}", "ok")

    def _page_action(self, name):
        fn = getattr(self.pages.get(self.active_page), name, None)
        if fn:
            fn()

    def closeEvent(self, event):
        data = load_settings()
        data.update({
            "last_page": self.active_page,
            "window_geometry": bytes(self.saveGeometry().toBase64()).decode(),
        })
        for page in self.pages.values():
            data.update(page.prefs())
        save_settings(data)
        super().closeEvent(event)


def run():
    ensure_dirs()
    logging.basicConfig(filename=str(D_UTIL / "studio.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    logging.info("App started")
    win = App()
    win.show()
    sys.exit(app.exec())
