# -*- coding: utf-8 -*-
import os
import zipfile

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from ...config import D_IN, D_OUT, D_WIP, load_settings
from ...core.humanizer import humanize_osu_text, ai_likeness_score
from ...core.io import read_text, write_text
from ...core.parser import parse_osu, fmt_t
from ..theme import PINK, BLUE, AMBER, PINK_DIM, TEXT_3, SURFACE_2, BORDER_HI, font
from ..widgets import (Card, Field, Button, Toggle, Slider, Log, Playfield, JobBar, page_header, caption,
                       fit_playfield, make_pen, save_png, scroll_page)
from ..worker import Job

TOGGLES = [
    ("micro", "Микро-слайдеры", "Слайдеры короче 18px превращаются в ноты"),
    ("stream", "Стримы", "Выравнивание расстояний между нотами подряд"),
    ("collinear", "Робо-линии", "Ломает прямые линии из 3+ нот в дуги"),
    ("spiral", "Спирали", "Ломает идеальные окружности"),
    ("repeat", "Повторы", "Раздвигает одинаковые паттерны"),
    ("overlap", "Наложения", "Раздвигает ноты, стоящие друг на друге"),
    ("edges", "Края", "Сдвигает ноты от границ экрана"),
    ("nc", "New Combo", "Расставляет NC по длине комбо"),
]


def _humanize_file(path, opts):
    """Хуманизирует один .osu (в 3_wip) или .osz (в 4_ready_osz). Возвращает путь результата."""
    name = os.path.basename(path)
    os.makedirs(str(D_WIP), exist_ok=True)
    os.makedirs(str(D_OUT), exist_ok=True)
    if name.lower().endswith(".osu"):
        new_t, _, _, _ = humanize_osu_text(read_text(path), opts)
        dest = os.path.join(str(D_WIP), name.replace(".osu", "_humanized.osu"))
        write_text(dest, new_t)
        return dest
    dest = os.path.join(str(D_OUT), name.replace(".osz", "_humanized.osz"))
    with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.lower().endswith(".osu"):
                raw = zin.read(item.filename).decode("utf-8-sig", errors="replace")
                new_t, _, _, _ = humanize_osu_text(raw, opts)
                zout.writestr(item.filename, new_t)
            else:
                zout.writestr(item, zin.read(item.filename))
    return dest


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self.hum_orig_objs, self.hum_new_objs = [], []
        self.undo_objs = None
        self._job = None
        self._build()
        self._restore(load_settings().get("hum_prefs") or {})

    # ── Интерфейс ─────────────────────────────────────────────────────
    def _build(self):
        page_header(self.box, "Хуманизатор ИИ",
                    "Делает карту менее «роботной»: сдвигает ноты, ломает идеальные паттерны и повторы")

        top = Card("Входной файл", ".osu или .osz с нейросетевой картой")
        self.box.addWidget(top)
        self.h_path = Field()
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.h_path, 1)
        row.addWidget(Button("Обзор", self.h_pick_file, "ghost"))
        row.addWidget(Button("Пакетная", self.action_batch, "info"))
        self.btn_undo = Button("Сбросить превью", self.action_undo, "ghost")
        self.btn_undo.set_enabled(False)
        row.addWidget(self.btn_undo)
        row.addWidget(Button("Обработать", self.action_humanize, "primary"))
        row.addWidget(Button("В 1:1 Куб", lambda: self.app.switch_page("cube"), "success"))
        top.body.addLayout(row)
        self.jobbar = JobBar()
        self.box.addWidget(self.jobbar)

        mid = QHBoxLayout()
        mid.setSpacing(16)
        self.box.addLayout(mid, 1)

        # ── Левая колонка: настройки ──
        detect = Card("Детекторы ИИ", "что ломать")
        detect.setFixedWidth(350)
        mid.addWidget(detect)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.vars = {}
        for i, (key, txt, tip) in enumerate(TOGGLES):
            t = Toggle(txt, True, tip)
            self.vars[key] = t
            grid.addWidget(t, i // 2, i % 2)
        detect.body.addLayout(grid)
        detect.body.addSpacing(12)

        self.h_strength = Slider("Сила коррекции", 0.1, 1.0, 0.05, PINK,
                                 fmt=lambda v: f"{v:.2f}", value=0.75)
        self.h_jitter = Slider("Микро-сдвиг", 0.0, 5.0, 0.5, BLUE,
                               fmt=lambda v: f"{v:.1f} px", value=2.0)
        detect.body.addWidget(self.h_strength)
        detect.body.addWidget(self.h_jitter)
        detect.body.addSpacing(6)
        detect.body.addWidget(caption("Seed"))
        self.h_seed = Field("727", mono=True)
        detect.body.addWidget(self.h_seed)

        self.hum_log = Log(4)
        detect.body.addWidget(self.hum_log, 1)

        # ── Правая колонка: превью и лог ──
        right = QVBoxLayout()
        right.setSpacing(16)
        mid.addLayout(right, 1)

        pf = Card("Превью карты", "playfield 512 × 384")
        right.addWidget(pf, 1)
        ctrl = QHBoxLayout()
        self.h_show_orig = Toggle("Призрак оригинала", True)
        self.h_show_orig.changed.connect(lambda *_: self.draw_playfield())
        ctrl.addWidget(self.h_show_orig)
        ctrl.addStretch(1)
        ctrl.addWidget(Button("PNG", self.export_png, "ghost"))
        self.lbl_score = QLabel("AI Score  —")
        self.lbl_score.setFont(font(10, True))
        self.lbl_score.setStyleSheet(f"color: {AMBER}; background: {SURFACE_2}; padding: 4px 12px; border-radius: 6px;")
        ctrl.addWidget(self.lbl_score)
        pf.body.addLayout(ctrl)

        self.pf = Playfield(self._paint_pf, 340)
        pf.body.addWidget(self.pf, 1)
        self.timeline = Slider("Таймлайн", 0, 100, 10, BLUE, fmt=fmt_t, value=0)
        self.timeline.changed.connect(lambda *_: self.draw_playfield())
        pf.body.addWidget(self.timeline)

        changes = Card("Лог изменений", "клик по строке — перейти к моменту")
        right.addWidget(changes)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Время", "Действие"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 110)
        self.tree.setMinimumHeight(170)
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        changes.body.addWidget(self.tree)

    # ── Данные и действия ─────────────────────────────────────────────
    def h_pick_file(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Файл карты", str(D_IN), "osu! (*.osu *.osz)")
        if p:
            self.load_path(p)

    def load_path(self, p):
        self.h_path.setText(p)
        self._clear_changes()
        self.hum_orig_objs, self.hum_new_objs = [], []
        if p.lower().endswith(".osu"):
            info = parse_osu(read_text(p))
            self.hum_orig_objs = info["objs"]
            self.setup_timeline(self.hum_orig_objs)
            self.lbl_score.setText(f"AI Score  {ai_likeness_score(self.hum_orig_objs)}")
        self.draw_playfield()

    def setup_timeline(self, objs):
        if not objs:
            return
        t0 = max(0, objs[0]["t"] - 500)
        t1 = objs[-1]["end"] + 500
        self.timeline.set_range(t0, max(t0 + 1000, t1))
        self.timeline.set_value(t0)

    def _get_opts(self):
        return {
            "fix_micro_sliders": self.vars["micro"].isChecked(), "smooth_streams": self.vars["stream"].isChecked(),
            "break_collinear": self.vars["collinear"].isChecked(), "break_spirals": self.vars["spiral"].isChecked(),
            "break_repeats": self.vars["repeat"].isChecked(), "fix_overlaps": self.vars["overlap"].isChecked(),
            "fix_edges": self.vars["edges"].isChecked(), "smart_nc": self.vars["nc"].isChecked(),
            "strength": self.h_strength.value(), "organic_jitter": self.h_jitter.value(),
            "seed": int(self.h_seed.text() or 42),
        }

    def _clear_changes(self):
        self.tree.clear()
        self.hum_log.clear()

    def _show_result(self, stats):
        self.setup_timeline(self.hum_new_objs or self.hum_orig_objs)
        self.draw_playfield()
        self.update_stats_ui(stats)

    def action_humanize(self):
        path = self.h_path.text().strip()
        if not os.path.isfile(path):
            return self.app.notify("Сначала выбери файл .osu или .osz", "warn")
        self.undo_objs = list(self.hum_orig_objs)
        self.btn_undo.set_enabled(True)
        self._clear_changes()
        opts = self._get_opts()
        try:
            if path.lower().endswith(".osu"):
                new_text, stats, orig, new = humanize_osu_text(read_text(path), opts)
                dest = os.path.join(str(D_WIP), os.path.basename(path).replace(".osu", "_humanized.osu"))
                write_text(dest, new_text)
                self.hum_orig_objs, self.hum_new_objs = orig, new
                self._show_result(stats)
                self.app.notify(f"Сохранено: {os.path.basename(dest)}", "ok")
            elif path.lower().endswith(".osz"):
                dest = os.path.join(str(D_OUT), os.path.basename(path).replace(".osz", "_humanized.osz"))
                first = None
                with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        raw = zin.read(item.filename)
                        if item.filename.lower().endswith(".osu"):
                            txt = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
                            new_txt, stats, orig, new = humanize_osu_text(txt, opts)
                            zout.writestr(item.filename, new_txt.replace("\n", "\r\n").encode("utf-8"))
                            if first is None:
                                first = (orig, new, stats)
                        else:
                            zout.writestr(item, raw)
                if first:
                    self.hum_orig_objs, self.hum_new_objs = first[0], first[1]
                    self._show_result(first[2])
                self.app.notify(f"Собрано: {os.path.basename(dest)}", "ok")
            else:
                self.app.notify("Поддерживаются только .osu и .osz", "warn")
        except Exception as e:
            QMessageBox.critical(self.app, "Ошибка", str(e))

    def action_batch(self):
        if self._job is not None and self._job.isRunning():
            return self.app.notify("Пакет уже выполняется", "warn")
        folder = QFileDialog.getExistingDirectory(self.app, "Папка с картами", str(D_IN))
        if not folder:
            return
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".osu", ".osz"))]
        if not files:
            return self.app.notify("В папке нет .osu или .osz файлов", "warn")
        opts = self._get_opts()

        job = Job(lambda j: self._batch_work(j, folder, files, opts), self.app)
        job.on_progress = lambda t: self.jobbar.update_progress(*t)
        job.on_log = lambda t: self.hum_log.add(*t)
        job.on_done = self._batch_done
        job.on_fail = self._batch_failed
        self.jobbar.cancel_requested.connect(job.cancel)
        self.jobbar.start(len(files), "Пакет…")
        self._job = job
        job.start()

    def _batch_work(self, job, folder, files, opts):
        count = failed = 0
        for i, f in enumerate(files, 1):
            if job.cancelled():
                job.say("Отменено пользователем", "warn")
                break
            try:
                _humanize_file(os.path.join(folder, f), opts)
                count += 1
                job.say(f"✓ {f}", "ok")
            except Exception as e:  # noqa: BLE001
                failed += 1
                job.say(f"✗ {f}: {e}", "err")
            job.report(i, len(files), f)
        return count, failed, job.cancelled()

    def _batch_done(self, res):
        count, failed, cancelled = res
        text = f"Пакет: обработано {count}" + (f", ошибок {failed}" if failed else "")
        if cancelled:
            text += " (отменено)"
        self.jobbar.finish(text)
        self.app.notify(text, "warn" if (failed or cancelled) else "ok")

    def _batch_failed(self, msg):
        self.jobbar.finish("Ошибка пакета")
        self.hum_log.add(msg, "err")
        self.app.notify("Пакетная обработка остановлена с ошибкой", "err")

    def export_png(self):
        try:
            path = save_png(self.pf, self.app, str(D_WIP / "humanize_preview.png"))
        except OSError as e:
            return self.app.notify(str(e), "err")
        if path:
            self.app.notify(f"Превью сохранено: {os.path.basename(path)}", "ok")

    # ── Настройки между запусками ─────────────────────────────────────
    def _restore(self, p):
        if not p:
            return
        toggles = p.get("toggles", {})
        for key, t in self.vars.items():
            t.setChecked(bool(toggles.get(key, True)))
        if "strength" in p:
            self.h_strength.set_value(float(p["strength"]))
        if "jitter" in p:
            self.h_jitter.set_value(float(p["jitter"]))
        if "seed" in p:
            self.h_seed.setText(str(p["seed"]))

    def prefs(self):
        return {"hum_prefs": {
            "toggles": {k: t.isChecked() for k, t in self.vars.items()},
            "strength": self.h_strength.value(),
            "jitter": self.h_jitter.value(),
            "seed": self.h_seed.text(),
        }}

    def update_stats_ui(self, stats):
        self.hum_log.clear()
        self.hum_log.add(f"Спирали: {stats['spirals']}    Повторы: {stats['repeats']}")
        self.hum_log.add(f"Наложения: {stats['overlaps']}    Стримы: {stats['stream_spacing']}", "dim")
        self.lbl_score.setText(f"AI Score  {stats['orig_ai']} → {stats['new_ai']}")
        for o in self.hum_new_objs:
            for r in o.get("reasons", []):
                item = QTreeWidgetItem([fmt_t(o["t"]), r])
                item.setData(0, Qt.ItemDataRole.UserRole, o["t"])
                self.tree.addTopLevelItem(item)

    def on_tree_select(self):
        items = self.tree.selectedItems()
        if items:
            t = items[0].data(0, Qt.ItemDataRole.UserRole)
            if t is not None:
                self.timeline.set_value(t)

    def action_undo(self):
        if self.undo_objs is None:
            return
        self.hum_new_objs = []
        self.hum_orig_objs = self.undo_objs
        self.btn_undo.set_enabled(False)
        self._clear_changes()
        self.lbl_score.setText("AI Score  —")
        self.draw_playfield()

    # ── Playfield ─────────────────────────────────────────────────────
    def draw_playfield(self):
        self.pf.update()

    def _paint_pf(self, p, w, h):
        fit = fit_playfield(w, h)
        if fit is None:
            return
        scale, ox, oy = fit

        def to_scr(px, py):
            return ox + px * scale, oy + py * scale

        x0, y0 = to_scr(0, 0)
        x1, y1 = to_scr(512, 384)
        p.setPen(make_pen(BORDER_HI, 1))
        p.setBrush(QColor("#0d1017"))
        p.drawRoundedRect(QRectF(x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2), 8, 8)

        p.setPen(make_pen("#141924", 1))
        for gx in range(64, 512, 64):
            a, b = to_scr(gx, 0), to_scr(gx, 384)
            p.drawLine(QPointF(*a), QPointF(*b))
        for gy in range(64, 384, 64):
            a, b = to_scr(0, gy), to_scr(512, gy)
            p.drawLine(QPointF(*a), QPointF(*b))

        cur_t = self.timeline.value()
        window = 1600
        r = 14 * scale

        def draw(objs, ghost=False):
            vis = [o for o in objs if cur_t - 400 <= o["t"] <= cur_t + window]
            for a, b in zip(vis, vis[1:]):
                if a["kind"] == "spinner" or b["kind"] == "spinner":
                    continue
                ax, ay = to_scr(a["ex"], a["ey"])
                bx, by = to_scr(b["x"], b["y"])
                p.setPen(make_pen("#252b3a", 1, dash=True) if ghost else make_pen(PINK_DIM, 2))
                p.drawLine(QPointF(ax, ay), QPointF(bx, by))
            for o in vis:
                if o["kind"] == "spinner":
                    continue
                c = QPointF(*to_scr(o["x"], o["y"]))
                if ghost:
                    p.setPen(make_pen(TEXT_3, 1, dash=True))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(c, r, r)
                    continue
                if o.get("modified"):
                    p.setPen(make_pen(PINK_DIM, 2))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(c, r + 4, r + 4)
                    fill = PINK
                else:
                    fill = BLUE
                p.setPen(make_pen("#ffffff", 2))
                p.setBrush(QColor(fill))
                p.drawEllipse(c, r, r)

        if self.h_show_orig.isChecked() and self.hum_orig_objs:
            draw(self.hum_orig_objs, True)
        if self.hum_new_objs:
            draw(self.hum_new_objs, False)
        if not self.hum_orig_objs and not self.hum_new_objs:
            p.setPen(make_pen(TEXT_3))
            p.setFont(font(10))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Выбери .osu, чтобы увидеть карту")

