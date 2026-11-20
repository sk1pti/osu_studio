# -*- coding: utf-8 -*-
"""Фоновые задачи: тяжёлая обработка идёт в QThread, UI обновляется через очередь событий Qt."""
from PySide6.QtCore import QThread, Signal


class Job(QThread):
    """Запускает fn(job) в отдельном потоке.

    Внутри fn можно вызывать job.report(i, n, msg), job.say(msg, tag) и проверять job.cancelled().
    Колбэки on_progress / on_log / on_done / on_fail вызываются в главном потоке.
    """

    _dispatch = Signal(object, object)   # (callback, payload) — доставляется в поток объекта Job

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._cancel = False
        self.on_progress = None   # payload: (i, n, msg)
        self.on_log = None        # payload: (msg, tag)
        self.on_done = None       # payload: результат fn
        self.on_fail = None       # payload: текст ошибки
        self._dispatch.connect(self._call)

    def _call(self, cb, payload):
        if cb is not None:
            cb(payload)

    def _post(self, cb, payload):
        self._dispatch.emit(cb, payload)

    # ── Для кода внутри задачи (поток) ──
    def cancel(self):
        self._cancel = True

    def cancelled(self):
        return self._cancel

    def report(self, i, n, msg=""):
        self._post(self.on_progress, (i, n, msg))

    def say(self, msg, tag=None):
        self._post(self.on_log, (msg, tag))

    # ── Запуск ──
    def run(self):
        try:
            result = self._fn(self)
        except Exception as e:  # noqa: BLE001 — любая ошибка уходит в UI, а не валит поток
            self._post(self.on_fail, f"{type(e).__name__}: {e}")
            return
        self._post(self.on_done, result)
