# -*- coding: utf-8 -*-
import os
import re

from PySide6.QtWidgets import QFileDialog, QHBoxLayout

from ...core.io import read_text
from ...core.lint import lint_osu
from ..widgets import Card, Field, Button, Log, page_header, scroll_page

ERR_WORDS = ("ошиб", "error", "критич", "нельзя", "invalid")
WARN_WORDS = ("warn", "предупр", "внимание", "подозр", "слишком", "мало", "много")


def _tag_for(line):
    low = line.lower()
    if any(w in low for w in ERR_WORDS):
        return "err"
    if any(w in low for w in WARN_WORDS):
        return "warn"
    return None


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self._build()

    def _build(self):
        page_header(self.box, "Линтер", "Проверка .osu на типичные ошибки мэппинга")
        card = Card("Файл", "пусто — возьмётся первый дифф из сборщика")
        self.box.addWidget(card)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.l_path = Field()
        row.addWidget(self.l_path, 1)
        row.addWidget(Button("Обзор", self.pick, "ghost"))
        row.addWidget(Button("Проверить", self.run_lint, "primary"))
        card.body.addLayout(row)
        self.l_log = Log(15)
        self.box.addWidget(self.l_log, 1)

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Файл карты", "", "osu! (*.osu)")
        if p:
            self.l_path.setText(p)

    def run_lint(self):
        p = self.l_path.text().strip() or (self.app.build_files[0] if self.app.build_files else "")
        if not os.path.isfile(p):
            return self.app.notify("Нет файла для проверки", "warn")
        text = read_text(p)
        lines = lint_osu(text)
        audio = re.search(r"^AudioFilename:\s*(.+)$", text, re.M)
        if audio and not os.path.isfile(os.path.join(os.path.dirname(p), audio.group(1).strip())):
            lines.append("[ВНИМАНИЕ] Аудиофайл '%s' не найден рядом с картой" % audio.group(1).strip())
        self.l_log.clear()
        if not lines:
            self.l_log.add("✓ Проблем не найдено", "ok")
            self.app.notify("Проверка пройдена", "ok")
            return
        for line in lines:
            self.l_log.add(line, _tag_for(line))
        self.app.notify(f"Найдено замечаний: {len(lines)}", "warn")

    def prefs(self):
        return {}
