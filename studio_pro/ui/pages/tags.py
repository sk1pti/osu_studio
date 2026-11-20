# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout

from ..widgets import Card, Field, Button, Log, page_header, caption, scroll_page


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self._build()

    def _build(self):
        page_header(self.box, "Теги и описание", "Шаблон тегов и описания для загрузки на osu!")
        row = QHBoxLayout()
        row.setSpacing(16)
        self.box.addLayout(row)

        form = Card("Метаданные", "результат копируется в буфер")
        row.addWidget(form)
        self.f_artist = Field()
        self.f_title = Field()
        self.f_artist.setMinimumWidth(260)
        self.f_title.setMinimumWidth(260)
        form.body.addWidget(caption("Artist"))
        form.body.addWidget(self.f_artist)
        form.body.addWidget(caption("Title"))
        form.body.addWidget(self.f_title)
        form.body.addSpacing(10)
        form.body.addWidget(Button("Сгенерировать и скопировать", self.gen, "primary"), 0, Qt.AlignmentFlag.AlignLeft)
        form.body.addStretch(1)

        out = Card("Результат")
        row.addWidget(out, 1)
        self.out = Log(10)
        out.body.addWidget(self.out)

    def gen(self):
        artist, title = self.f_artist.text().strip(), self.f_title.text().strip()
        if not artist or not title:
            return self.app.notify("Заполни Artist и Title", "warn")
        text = (f"Tags: {artist} {title} jump aim\n\n"
                f"Description:\nJump map for {artist} - {title}.")
        self.out.set_message(text)
        QApplication.clipboard().setText(text)
        self.app.notify("Описание скопировано в буфер", "ok")

    def prefs(self):
        return {}
