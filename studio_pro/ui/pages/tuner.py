# -*- coding: utf-8 -*-
import os

from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox

from ...config import D_WIP
from ...core.builder import tune_file
from ...core.io import read_text, get_val
from ..theme import PINK, BLUE, GREEN, AMBER, TEXT_2, font
from ..widgets import Card, Field, Button, Toggle, Slider, Log, page_header, scroll_page

PARAMS = [("CS", "CircleSize", PINK), ("AR", "ApproachRate", BLUE),
          ("OD", "OverallDifficulty", GREEN), ("HP", "HPDrainRate", AMBER)]


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self._build()

    def _build(self):
        page_header(self.box, "Тюннер карты", "Сложность, сдвиг таймлайна и звуки")

        file_card = Card("Файл карты", "редактирует .osu из 3_wip")
        self.box.addWidget(file_card)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.t_path = Field()
        row.addWidget(self.t_path, 1)
        row.addWidget(Button("Обзор", self.t_pick, "ghost"))
        file_card.body.addLayout(row)

        diff = Card("Сложность", "значения подхватываются из файла")
        self.box.addWidget(diff)
        grid = QGridLayout()
        grid.setHorizontalSpacing(36)
        grid.setVerticalSpacing(14)
        self.t_sliders = {}
        for i, (short, _, color) in enumerate(PARAMS):
            sl = Slider(short, 0.0, 10.0, 0.1, color, fmt=lambda v: f"{v:.1f}", value=4.0)
            self.t_sliders[short] = sl
            grid.addWidget(sl, i // 2, i % 2)
        diff.body.addLayout(grid)

        misc = Card("Таймлайн и звук")
        self.box.addWidget(misc)
        r = QHBoxLayout()
        r.setSpacing(12)
        r.addWidget(QLabel("Сдвиг, мс", styleSheet=f"color: {TEXT_2};"))
        self.t_off = Field("0")
        self.t_off.setFixedWidth(120)
        r.addWidget(self.t_off)
        self.v_hs = Toggle("Hitsounds (Whistle)", False)
        self.v_col = Toggle("Цвета комбо", False)
        r.addSpacing(18)
        r.addWidget(self.v_hs)
        r.addSpacing(12)
        r.addWidget(self.v_col)
        r.addStretch(1)
        misc.body.addLayout(r)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(Button("Применить и сохранить", self.action_apply, "success"))
        self.box.addLayout(actions)

        self.tune_log = Log(8)
        self.box.addWidget(self.tune_log, 1)

    def t_pick(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Карта", str(D_WIP), "osu! (*.osu)")
        if not p:
            return
        self.t_path.setText(p)
        t = read_text(p)
        for short, full, _ in PARAMS:
            try:
                self.t_sliders[short].set_value(float(get_val(t, full)))
            except (TypeError, ValueError):
                pass
        self.app.notify(f"Загружено: {os.path.basename(p)}", "info")

    def action_apply(self):
        path = self.t_path.text().strip()
        if not os.path.isfile(path):
            return self.app.notify("Сначала выбери файл .osu", "warn")
        try:
            off = int(self.t_off.text().strip() or "0")
        except ValueError:
            return QMessageBox.critical(self.app, "Ошибка", "Сдвиг должен быть целым числом")
        try:
            dest = tune_file(path, {k: s.value() for k, s in self.t_sliders.items()}, off, D_WIP,
                             hitsounds=self.v_hs.isChecked(), colours=self.v_col.isChecked())
            self.tune_log.add(f"Сохранено: {dest}", "ok")
            self.app.notify("Карта обновлена", "ok")
        except Exception as e:
            QMessageBox.critical(self.app, "Ошибка", str(e))

    def prefs(self):
        return {}
