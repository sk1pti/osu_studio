# -*- coding: utf-8 -*-
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QListWidget, QMessageBox, QVBoxLayout

from ...config import D_IN, D_OUT, D_WIP, DIFF_PARAMS, LADDERS, load_settings
from ...core.builder import build_osz
from ..widgets import Card, Field, Button, Toggle, Log, page_header, caption, scroll_page


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        s = load_settings()
        self.f_audio = Field(s.get("build_audio", ""))
        self.f_bg = Field(s.get("build_bg", ""))
        self.f_name = Field(s.get("build_name", ""))
        self._build()

    def _build(self):
        page_header(self.box, "Сборщик сета", "Собери несколько дифов в один .osz с авто-лестницей сложности")

        top = QHBoxLayout()
        top.setSpacing(16)
        self.box.addLayout(top)

        # ── Дифы ──
        diffs = Card("Дифы", "порядок = порядок в лестнице")
        top.addWidget(diffs, 1)
        self.lb = QListWidget()
        self.lb.setMinimumHeight(220)
        diffs.body.addWidget(self.lb, 1)
        col = QVBoxLayout()
        col.setSpacing(8)
        for txt, cmd in (("Добавить", self.b_add), ("Папка", self.b_add_folder),
                         ("Убрать", self.b_remove), ("Очистить", self.b_clear)):
            col.addWidget(Button(txt, cmd, "ghost"))
        col.addStretch(1)
        diffs.body.addSpacing(6)
        diffs.body.addLayout(col)

        # ── Ассеты ──
        assets = Card("Ассеты и имя", "аудио обязательно")
        top.addWidget(assets, 1)
        body = assets.body
        body.addWidget(caption("Аудио (.mp3 / .ogg)"))
        body.addLayout(self._picker(self.f_audio, self.b_pick_audio))
        body.addWidget(caption("Фон (.jpg / .png)"))
        body.addLayout(self._picker(self.f_bg, self.b_pick_bg))
        body.addWidget(caption("Имя сета"))
        body.addWidget(self.f_name)
        self.auto = Toggle("Авто-лестница сложности", True,
                           "Пересчитывает CS/AR/OD/HP и версии дифов по их количеству")
        body.addSpacing(10)
        body.addWidget(self.auto)
        body.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(Button("Собрать .osz", self.action_build, "success"))
        self.box.addLayout(actions)

        self.build_log = Log(6)
        self.box.addWidget(self.build_log)

    def _picker(self, field, cmd):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(field, 1)
        row.addWidget(Button("Обзор", cmd, "ghost"))
        return row

    # ── Список дифов ──────────────────────────────────────────────────
    def b_refresh(self):
        self.lb.clear()
        for p in self.app.build_files:
            self.lb.addItem(os.path.basename(p))

    def b_add(self):
        paths, _ = QFileDialog.getOpenFileNames(self.app, "Выбор дифов", str(D_WIP), "osu! (*.osu)")
        self.app.build_files.extend(paths)
        self.b_refresh()

    def b_add_folder(self):
        d = QFileDialog.getExistingDirectory(self.app, "Папка с дифами", str(D_WIP))
        if d:
            for f in sorted(os.listdir(d)):
                if f.endswith(".osu"):
                    self.app.build_files.append(os.path.join(d, f))
            self.b_refresh()

    def b_remove(self):
        row = self.lb.currentRow()
        if 0 <= row < len(self.app.build_files):
            del self.app.build_files[row]
            self.b_refresh()

    def b_clear(self):
        self.app.build_files = []
        self.b_refresh()

    def b_pick_audio(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Аудио", str(D_IN), "Audio (*.mp3 *.ogg)")
        if p:
            self.f_audio.setText(p)

    def b_pick_bg(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Фон", str(D_IN), "Img (*.jpg *.png)")
        if p:
            self.f_bg.setText(p)

    # ── Сборка ────────────────────────────────────────────────────────
    def action_build(self):
        try:
            out = build_osz(self.app.build_files, self.f_audio.text(), self.f_bg.text(), self.f_name.text(),
                            self.auto.isChecked(), DIFF_PARAMS, LADDERS, D_OUT)
            self.build_log.add(f"Собрано: {out}", "ok")
            self.app.notify(f"Сет собран: {os.path.basename(str(out))}", "ok")
        except Exception as e:
            QMessageBox.critical(self.app, "Ошибка", str(e))

    def prefs(self):
        return {"build_audio": self.f_audio.text(), "build_bg": self.f_bg.text(),
                "build_name": self.f_name.text()}
