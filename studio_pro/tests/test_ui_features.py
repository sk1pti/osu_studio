# -*- coding: utf-8 -*-
"""Тесты новых возможностей: фоновые задачи, drag & drop, сохранение настроек."""
import math
import os
import shutil
import tempfile
import time
import zipfile

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _wait(app, job, timeout=20.0):
    t0 = time.time()
    while job.isRunning() and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.01)
    for _ in range(10):  # доставить отложенные (queued) сигналы
        app.processEvents()
        time.sleep(0.005)


def _sample_osu(n=60):
    lines = []
    t = 1000
    for i in range(n):
        x = int(256 + 150 * math.cos(i * 0.4))
        y = int(192 + 110 * math.sin(i * 0.4))
        lines.append(f"{x},{y},{t},1,0,0:0:0:0:")
        t += 180
    return ("osu file format v14\n\n[General]\nAudioFilename: audio.mp3\n\n"
            "[Difficulty]\nCircleSize:4\nApproachRate:9\nOverallDifficulty:8\nHPDrainRate:5\n"
            "SliderMultiplier:1.4\n\n[TimingPoints]\n0,500,4,2,1,60,1,0\n\n[HitObjects]\n"
            + "\n".join(lines) + "\n")


@pytest.fixture(scope="module")
def app():
    from studio_pro.ui.theme import apply_theme
    qapp = _app()
    apply_theme(qapp)
    return qapp


@pytest.fixture(scope="module")
def window(app):
    from studio_pro.ui.app import App
    win = App()
    win.show()
    yield win
    win.close()


@pytest.fixture
def tmpdir_path():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ── Фоновые задачи ────────────────────────────────────────────────────
def test_job_delivers_result(app):
    from studio_pro.ui.worker import Job
    got = {}
    job = Job(lambda j: 42)
    job.on_done = lambda r: got.setdefault("r", r)
    job.start()
    _wait(app, job)
    assert got["r"] == 42


def test_job_reports_progress_and_logs(app):
    from studio_pro.ui.worker import Job
    seen = {"progress": [], "log": []}

    def work(j):
        for i in range(1, 4):
            j.report(i, 3, f"item{i}")
            j.say(f"line{i}", "ok")
        return "done"

    job = Job(work)
    job.on_progress = lambda t: seen["progress"].append(t)
    job.on_log = lambda t: seen["log"].append(t)
    job.start()
    _wait(app, job)
    assert seen["progress"] == [(1, 3, "item1"), (2, 3, "item2"), (3, 3, "item3")]
    assert seen["log"][0] == ("line1", "ok")


def test_job_cancel_stops_early(app):
    from studio_pro.ui.worker import Job
    got = {}

    def work(j):
        n = 0
        for _ in range(1000):
            if j.cancelled():
                break
            n += 1
            time.sleep(0.001)
        return n

    job = Job(work)
    job.on_done = lambda r: got.setdefault("n", r)
    job.start()
    job.cancel()
    _wait(app, job)
    assert got["n"] < 1000


def test_job_failure_goes_to_on_fail(app):
    from studio_pro.ui.worker import Job
    got = {}

    def boom(j):
        raise ValueError("плохой файл")

    job = Job(boom)
    job.on_fail = lambda msg: got.setdefault("msg", msg)
    job.start()
    _wait(app, job)
    assert "плохой файл" in got["msg"]


# ── Пакетная хуманизация ──────────────────────────────────────────────
def test_humanize_batch_worker_processes_folder(app, window, tmpdir_path):
    from studio_pro.ui.worker import Job
    folder = os.path.join(tmpdir_path, "maps")
    os.makedirs(folder)
    for name in ("a.osu", "b.osu"):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(_sample_osu())
    with zipfile.ZipFile(os.path.join(folder, "pack.osz"), "w") as z:
        z.writestr("x [Insane].osu", _sample_osu())
    with open(os.path.join(folder, "notes.txt"), "w") as f:
        f.write("ignore me")

    page = window.pages["humanize"]
    files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".osu", ".osz"))]
    assert len(files) == 3
    opts = page._get_opts()
    got = {}
    job2 = Job(lambda j: page._batch_work(j, folder, files, opts))
    job2.on_done = lambda r: got.setdefault("r", r)
    job2.start()
    _wait(app, job2)
    count, failed, cancelled = got["r"]
    assert count == 3 and failed == 0 and cancelled is False


def test_humanize_batch_cancel_before_start(app, window, tmpdir_path):
    from studio_pro.ui.worker import Job
    folder = os.path.join(tmpdir_path, "maps2")
    os.makedirs(folder)
    with open(os.path.join(folder, "a.osu"), "w", encoding="utf-8") as f:
        f.write(_sample_osu())
    page = window.pages["humanize"]
    got = {}
    job = Job(lambda j: page._batch_work(j, folder, ["a.osu"], page._get_opts()))
    job.on_done = lambda r: got.setdefault("r", r)
    job.cancel()
    job.start()
    _wait(app, job)
    count, failed, cancelled = got["r"]
    assert count == 0 and cancelled is True


# ── Drag & drop ───────────────────────────────────────────────────────
class _FakeEvent:
    def __init__(self, paths):
        self._m = QMimeData()
        self._m.setUrls([QUrl.fromLocalFile(p) for p in paths])

    def mimeData(self):
        return self._m


def test_drop_accepts_only_osu_and_osz(window):
    assert window._drop_path(_FakeEvent(["/tmp/a.osu"])) == "/tmp/a.osu"
    assert window._drop_path(_FakeEvent(["/tmp/pack.OSZ"])).lower().endswith(".osz")
    assert window._drop_path(_FakeEvent(["/tmp/readme.txt"])) is None


def test_open_path_switches_to_humanize(window, tmpdir_path):
    p = os.path.join(tmpdir_path, "map.osu")
    with open(p, "w", encoding="utf-8") as f:
        f.write(_sample_osu(10))
    window.switch_page("lint")
    window.open_path(p)
    assert window.active_page == "humanize"
    assert window.pages["humanize"].h_path.text() == p


# ── Сохранение настроек ───────────────────────────────────────────────
def test_humanize_prefs_roundtrip(window):
    page = window.pages["humanize"]
    page.vars["micro"].setChecked(False)
    page.h_seed.setText("1234")
    saved = page.prefs()["hum_prefs"]
    page.vars["micro"].setChecked(True)
    page.h_seed.setText("1")
    page._restore(saved)
    assert page.vars["micro"].isChecked() is False
    assert page.h_seed.text() == "1234"


def test_all_pages_provide_prefs(window):
    data = {}
    for page in window.pages.values():
        data.update(page.prefs())
    assert "hum_prefs" in data and "cube_prefs" in data and "build_name" in data


def test_cube_prefs_roundtrip(window):
    page = window.pages["cube"]
    page.v_seed.setText("999")
    saved = page.prefs()["cube_prefs"]
    page.v_seed.setText("1")
    page._restore(saved)
    assert page.v_seed.text() == "999"


def test_cube_folder_job_runs_in_background(app, window, tmpdir_path):
    folder = os.path.join(tmpdir_path, "cubefolder")
    os.makedirs(folder)
    for name in ("one.osu", "two.osu"):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(_sample_osu())
    page = window.pages["cube"]
    targets = [os.path.join(folder, n) for n in ("one.osu", "two.osu")]
    page._start_folder_job(targets, ["cube", "humanize", "lint_check"], page._build_cube_cfg(), 727)
    _wait(app, page._job)
    assert page.lbl_info.text().startswith("Папка: 2"), page.lbl_info.text()
    assert page.jobbar.btn.isEnabled() is False
    assert page.orig_objs, "превью первого дифа должно загрузиться"
