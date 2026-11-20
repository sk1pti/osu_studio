# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout

from ...config import PRESETS
from ..theme import SURFACE, SURFACE_2, TEXT, TEXT_2, TEXT_3
from ..widgets import Card, Field, Button, Chip, page_header, caption, scroll_page


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self._build()

    def _build(self):
        page_header(self.box, "Конфиг ИИ", "Параметры генерации Mapperatorinator")
        row = QHBoxLayout()
        row.setSpacing(16)
        self.box.addLayout(row)

        params = Card("Параметры", "-1 — случайный маппер")
        row.addWidget(params)
        self.f_mapper = Field("-1", mono=True)
        self.f_cfg = Field("2.8", mono=True)
        self.f_temp = Field("0.88", mono=True)
        self.f_year = Field("2023", mono=True)
        for label, field in (("Mapper ID", self.f_mapper), ("CFG Scale", self.f_cfg),
                             ("Temperature", self.f_temp), ("Год", self.f_year)):
            params.body.addWidget(caption(label))
            params.body.addWidget(field)
        params.body.addSpacing(10)
        params.body.addWidget(Button("Скопировать конфиг", self.copy, "info"), 0, Qt.AlignmentFlag.AlignLeft)
        params.body.addStretch(1)

        presets = Card("Пресеты", "клик — подставить значения")
        row.addWidget(presets, 1)
        for name, p in PRESETS.items():
            cell = QFrame()
            cell.setObjectName("cell")
            cell.setStyleSheet(f"#cell {{ background: {SURFACE_2}; border-radius: 8px; }}")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)
            cl.addWidget(Chip(name, lambda p=p: self.apply(p), bg=SURFACE, fg=TEXT), 0, Qt.AlignmentFlag.AlignLeft)
            cl.addWidget(caption(p.get("desc", ""), TEXT_3, 9))
            summary = (f"mapper {p.get('mapper', '-1')}   ·   cfg {p.get('cfg', '2.8')}   ·   "
                       f"temp {p.get('temp', '0.88')}   ·   {p.get('year', '2023')}")
            cl.addWidget(caption(summary, TEXT_2, 9))
            presets.body.addWidget(cell)
        presets.body.addStretch(1)

    def apply(self, p):
        self.f_mapper.setText(str(p.get("mapper", "-1")))
        self.f_cfg.setText(str(p.get("cfg", "2.8")))
        self.f_temp.setText(str(p.get("temp", "0.88")))
        self.f_year.setText(str(p.get("year", "2023")))
        self.app.notify("Пресет применён", "ok")

    def copy(self):
        text = (f"Mapper ID: {self.f_mapper.text()}\nCFG Scale: {self.f_cfg.text()}\n"
                f"Temperature: {self.f_temp.text()}\nYear: {self.f_year.text()}")
        QApplication.clipboard().setText(text)
        self.app.notify("Конфиг скопирован в буфер", "ok")

    def prefs(self):
        return {}
