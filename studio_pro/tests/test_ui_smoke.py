# -*- coding: utf-8 -*-
"""Дымовой тест Qt-интерфейса: все страницы открываются, базовые действия не падают."""
import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def window():
    from studio_pro.ui.theme import apply_theme
    from studio_pro.ui.app import App
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    win = App()
    win.show()
    yield win
    win.close()


@pytest.mark.parametrize("key", ["humanize", "cube", "tune", "build", "lint", "ref", "tags", "cfg"])
def test_page_opens(window, key):
    window.switch_page(key)
    assert window.active_page == key


def test_cfg_preset_applies(window):
    window.switch_page("cfg")
    page = window.pages["cfg"]
    page.apply({"mapper": "3", "cfg": "2.1", "temp": "0.8", "year": "2024"})
    assert page.f_cfg.text() == "2.1"
    assert page.f_year.text() == "2024"


def test_tags_requires_fields(window):
    window.switch_page("tags")
    page = window.pages["tags"]
    page.f_artist.setText("")
    page.f_title.setText("")
    page.gen()  # не должен падать; предупреждение уходит в статус-бар
