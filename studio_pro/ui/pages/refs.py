# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from ...config import D_REF
from ...core.builder import extract_reference
from ..widgets import Card, Button, Log, page_header, scroll_page


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self._build()

    def _build(self):
        page_header(self.box, "Референсы", "Вытащи .osu из чужого .osz, чтобы разобрать маппинг")
        card = Card("Извлечение", "сохраняет в 2_references")
        self.box.addWidget(card)
        card.body.addWidget(Button("Выбрать .osz архив", self.extract, "primary"), 0, Qt.AlignmentFlag.AlignLeft)
        self.l = Log(14)
        self.box.addWidget(self.l, 1)

    def extract(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Архив .osz", "", "osz (*.osz)")
        if not p:
            return
        try:
            dest, _ = extract_reference(p, D_REF)
            self.l.add(f"Извлечено: {dest}", "ok")
            self.app.notify("Референс сохранён", "ok")
        except Exception as e:
            self.l.add(str(e), "err")
            self.app.notify("Не удалось извлечь файл", "err")

    def prefs(self):
        return {}
