# -*- coding: utf-8 -*-
import os
import zipfile

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainterPath
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QMessageBox, QVBoxLayout)

from ...config import D_IN, D_OUT, D_WIP, load_settings
from ...core.cube import (CUBE_PRESETS, CUBE_MIN_X, CUBE_MAX_X, CUBE_MIN_Y, CUBE_MAX_Y,
                          build_heatmap_grid)
from ...core.pipeline import (load_recipes, save_recipes, run_pipeline_on_osu,
                              compare_diffs_summary, format_diff_report)
from ...core.humanizer import ai_likeness_score
from ...core.io import read_text, write_text
from ...core.parser import parse_osu, fmt_t
from ...utils.fs import open_dir
from ..theme import (SURFACE_2, BORDER, BORDER_HI, TEXT, TEXT_2, TEXT_3, PINK, BLUE, GREEN, AMBER,
                     PINK_DIM, SURFACE, font)
from ..widgets import (Card, Field, Button, Toggle, Slider, Log, Playfield, JobBar, page_header, caption,
                       fit_playfield, make_pen, hline, save_png, scroll_page)
from ..worker import Job


def _decode_osu_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251", "cp1252"):
        try:
            txt = raw.decode(enc)
            return txt.replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _set_combo(cb: QComboBox, text: str):
    i = cb.findText(text)
    if i >= 0:
        cb.setCurrentIndex(i)


def _process_osu_file(src_path, steps, cfg, seed):
    """Прогоняет один .osu через конвейер и пишет результат в 3_wip. Потокобезопасно."""
    raw_txt = read_text(src_path).replace("\r\n", "\n").replace("\r", "\n")
    new_text, stats, orig, new = run_pipeline_on_osu(
        raw_txt, steps=steps, cube_cfg=cfg, seed=seed, tag_suffix="[1:1 Cube]")
    os.makedirs(str(D_WIP), exist_ok=True)
    base_name = os.path.basename(src_path)
    out_name = base_name[:-4] + "_cube.osu" if base_name.lower().endswith(".osu") else base_name + "_cube.osu"
    dest = os.path.join(str(D_WIP), out_name)
    write_text(dest, new_text.replace("\n", "\r\n"))
    report = format_diff_report(base_name, stats)
    return dest, stats, orig, new, report


class Page:
    def __init__(self, app):
        self.app = app
        self.view, self.box = scroll_page()
        self.orig_objs, self.new_objs = [], []
        self._job = None
        self.osz_entries = []
        self.run_history = []
        self.last_dest_dir = str(D_WIP)
        self.last_report_txt = ""
        self.recipes_path = os.path.join(str(D_WIP), "cube_recipes.json")
        self.recipes = load_recipes(self.recipes_path)
        self._playing = False
        self._play_timer = QTimer()
        self._play_timer.timeout.connect(self._tick_play)
        self._issue_times = []
        self._build()

    def _build(self):
        page_header(self.box, "Лвл-Куб (1:1) & Конвейер",
                    "Челлендж-моды, тепловая карта, A/B сравнение seed, отчёты до/после и пакетная обработка")

        # ── Входной файл, рецепт и быстрые действия ──
        top = Card("Входной файл и конвейер", "один .osu, .osz пак или папка с картами")
        self.box.addWidget(top)
        self.c_path = Field()
        top.body.addWidget(self.c_path)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(Button("Файл", self.pick_file, "ghost"))
        row.addWidget(Button("Папка", self.pick_folder, "ghost"))
        row.addWidget(Button("Запустить", self.action_cubify, "primary"))
        row.addWidget(Button("A/B Seed", self.action_ab_seed, "ghost"))
        row.addWidget(Button("Отчёт", self.export_report, "ghost"))
        row.addWidget(Button("Папка рез.", self.open_output_dir, "ghost"))
        row.addStretch(1)
        top.body.addLayout(row)

        sub = QHBoxLayout()
        sub.setSpacing(8)
        sub.addWidget(caption("Пресет:"))
        self.cb_preset = QComboBox()
        self.cb_preset.addItems(list(CUBE_PRESETS.keys()) + ["Custom"])
        _set_combo(self.cb_preset, "Flow & Anti-AI")
        self.cb_preset.activated.connect(lambda *_: self.apply_preset())
        sub.addWidget(self.cb_preset)

        sub.addSpacing(12)
        sub.addWidget(caption("Челлендж:"))
        self.cb_challenge = QComboBox()
        self.cb_challenge.addItems(["none", "mirror_x", "corridor_y"])
        sub.addWidget(self.cb_challenge)

        sub.addSpacing(12)
        sub.addWidget(caption("Рецепт:"))
        self.cb_recipe = QComboBox()
        self.cb_recipe.addItems(list(self.recipes.keys()))
        self.cb_recipe.activated.connect(lambda *_: self.apply_recipe())
        sub.addWidget(self.cb_recipe)
        sub.addWidget(Button("Сохранить", self.save_current_recipe, "ghost"))
        sub.addStretch(1)
        top.body.addLayout(sub)

        sub2 = QHBoxLayout()
        sub2.setSpacing(8)
        sub2.addWidget(caption("Диф в .osz:"))
        self.cb_osz_diff = QComboBox()
        self.cb_osz_diff.setMinimumWidth(200)
        self.cb_osz_diff.activated.connect(lambda *_: self.preview_selected_osz_diff())
        sub2.addWidget(self.cb_osz_diff, 1)
        top.body.addLayout(sub2)

        # Шаги конвейера
        steps = QHBoxLayout()
        steps.setSpacing(12)
        steps.addWidget(caption("Шаги:"))
        self.v_step_cube = Toggle("1:1 Куб", True)
        self.v_step_hum = Toggle("Хуманизация", True)
        self.v_step_lint = Toggle("Чеклист", True)
        self.v_step_tags = Toggle("Теги версии", True)
        for t in (self.v_step_cube, self.v_step_hum, self.v_step_lint, self.v_step_tags):
            steps.addWidget(t)
        steps.addStretch(1)
        top.body.addLayout(steps)
        self.jobbar = JobBar()
        self.box.addWidget(self.jobbar)

        mid = QHBoxLayout()
        mid.setSpacing(16)
        self.box.addLayout(mid, 1)

        # ── Левая колонка: настройки, чеклист, таймкоды и лог ──
        left = Card("Параметры и аудит", "чеклист и лог")
        left.setFixedWidth(365)
        mid.addWidget(left)
        body = left.body

        self.v_fill_mode = Toggle("Максимально заполнять куб", False,
                                  "Выкл: равномерное сжатие. Вкл: подгонка под весь квадрат 384×384")
        self.v_adaptive = Toggle("Учёт плотности ритма", True,
                                 "На плотных кусках держит мягче сглаживание и безопаснее масштаб")
        self.v_adjust_cs = Toggle("Авто-подстройка CS под 1:1", True,
                                  "Если CS < 5.5, поднимает на +0.3 (до 6.5) для читаемости")
        for t in (self.v_fill_mode, self.v_adaptive, self.v_adjust_cs):
            body.addWidget(t)
        body.addSpacing(6)
        body.addWidget(hline())
        body.addSpacing(6)

        self.v_pad = Slider("Отступ от краёв куба", 6.0, 28.0, 1.0, BLUE,
                            fmt=lambda v: f"{int(v)} px", value=14.0)
        self.v_strength = Slider("Сила анти-ИИ сглаживания", 0.1, 1.0, 0.05, PINK,
                                 fmt=lambda v: f"{v:.2f}", value=0.65)
        body.addWidget(self.v_pad)
        body.addWidget(self.v_strength)

        body.addWidget(caption("Seed"))
        self.v_seed = Field("727", mono=True)
        body.addWidget(self.v_seed)

        body.addWidget(caption("Чеклист играбельности:"))
        self.lbl_checklist = QLabel("Ожидает запуска")
        self.lbl_checklist.setWordWrap(True)
        self.lbl_checklist.setFont(font(9))
        self._set_checklist("Ожидает запуска", TEXT_2)
        body.addWidget(self.lbl_checklist)

        body.addWidget(caption("Проблемные таймкоды (клик — переход на превью):"))
        self.lb_issues = QListWidget()
        self.lb_issues.setMinimumHeight(110)
        self.lb_issues.setFont(font(9))
        self.lb_issues.itemClicked.connect(lambda *_: self.jump_to_selected_issue())
        body.addWidget(self.lb_issues)

        self.cube_log = Log(7)
        body.addWidget(self.cube_log, 1)

        # ── Правая колонка: превью, тепловая карта и таймлайн ──
        pf = Card("Превью 1:1 Куба", "рамка = границы квадрата 384×384")
        mid.addWidget(pf, 1)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(14)
        self.v_show_orig = Toggle("Оригинал", True)
        self.v_show_sliders = Toggle("Слайдеры", True)
        self.v_show_heat = Toggle("Теплокарта", False)
        for t in (self.v_show_orig, self.v_show_sliders, self.v_show_heat):
            ctrl.addWidget(t)
            t.changed.connect(lambda *_: self.draw_playfield())
        ctrl.addStretch(1)
        pf.body.addLayout(ctrl)

        info_row = QHBoxLayout()
        info_row.setSpacing(12)
        self.btn_play = Button("▶ Плей", self.toggle_play, "ghost")
        info_row.addWidget(self.btn_play)
        info_row.addStretch(1)
        info_row.addWidget(Button("PNG", self.export_png, "ghost"))
        self.lbl_info = QLabel("1:1 Cube  —")
        self.lbl_info.setFont(font(10, True))
        self.lbl_info.setStyleSheet(f"color: {GREEN}; background: {SURFACE_2}; padding: 4px 12px; border-radius: 6px;")
        info_row.addWidget(self.lbl_info)
        pf.body.addLayout(info_row)

        self.pf = Playfield(self._paint_cube, 400)
        pf.body.addWidget(self.pf, 1)
        self.timeline = Slider("Таймлайн", 0, 100, 10, BLUE, fmt=fmt_t, value=0)
        self.timeline.changed.connect(lambda *_: self.draw_playfield())
        pf.body.addWidget(self.timeline)
        self._restore(load_settings().get("cube_prefs") or {})

    # ── Вспомогательное ───────────────────────────────────────────────
    def _set_checklist(self, text, color):
        self.lbl_checklist.setText(text)
        self.lbl_checklist.setStyleSheet(
            f"color: {color}; background: {SURFACE_2}; padding: 6px; border-radius: 6px;")

    def toggle_play(self):
        if self._playing:
            self._playing = False
            self.btn_play.setText("▶ Плей")
            self._play_timer.stop()
            return
        self._playing = True
        self.btn_play.setText("⏸ Пауза")
        self._play_timer.start(45)

    def _tick_play(self):
        if not self._playing:
            return
        lo, hi = self.timeline.range()
        nxt = self.timeline.value() + 45.0
        if nxt > hi:
            nxt = lo
        self.timeline.set_value(nxt)

    def apply_preset(self):
        name = self.cb_preset.currentText()
        cfg = CUBE_PRESETS.get(name)
        if not cfg:
            return
        self.v_fill_mode.setChecked(cfg["scale_mode"] == "fill_cube")
        self.v_pad.set_value(cfg["padding_px"])
        self.v_step_hum.setChecked(cfg["humanize_after"])
        self.v_strength.set_value(cfg["humanize_strength"])
        self.v_adjust_cs.setChecked(cfg["adjust_cs"])
        self.v_step_tags.setChecked(cfg["tag_version"])
        self.v_adaptive.setChecked(cfg["adaptive_density"])
        _set_combo(self.cb_challenge, cfg.get("challenge_mode", "none"))

    def apply_recipe(self):
        rec = self.recipes.get(self.cb_recipe.currentText())
        if not rec:
            return
        steps = rec.get("steps", [])
        self.v_step_cube.setChecked("cube" in steps)
        self.v_step_hum.setChecked("humanize" in steps)
        self.v_step_lint.setChecked("lint_check" in steps)
        self.v_step_tags.setChecked("tags" in steps)
        p = rec.get("cube_preset")
        if p in CUBE_PRESETS:
            _set_combo(self.cb_preset, p)
            self.apply_preset()

    def save_current_recipe(self):
        rname = (self.cb_recipe.currentText() or "Custom Recipe").strip()
        self.recipes[rname] = {
            "steps": self._collect_steps(),
            "cube_preset": self.cb_preset.currentText(),
            "tag_suffix": "[1:1 Cube]",
        }
        save_recipes(self.recipes_path, self.recipes)
        self.cb_recipe.clear()
        self.cb_recipe.addItems(list(self.recipes.keys()))
        _set_combo(self.cb_recipe, rname)
        self.app.notify(f"Рецепт сохранён: {rname}", "ok")

    def _collect_steps(self) -> list:
        steps = []
        if self.v_step_cube.isChecked():
            steps.append("cube")
        if self.v_step_hum.isChecked():
            steps.append("humanize")
        if self.v_step_lint.isChecked():
            steps.append("lint_check")
        if self.v_step_tags.isChecked():
            steps.append("tags")
        return steps

    def _update_checklist_ui(self, checks: list):
        if not checks:
            return self._set_checklist("Нет данных чеклиста", TEXT_2)
        lines = []
        top_level = "ok"
        for c in checks:
            lvl = c.get("level", "ok")
            if lvl == "err":
                top_level = "err"
            elif lvl == "warn" and top_level != "err":
                top_level = "warn"
            lines.append(f"• {c.get('msg', '')}")
        color = GREEN if top_level == "ok" else (PINK if top_level == "err" else AMBER)
        self._set_checklist("\n".join(lines), color)

    def _populate_issues(self, issues):
        self.lb_issues.clear()
        self._issue_times = []
        if not issues:
            self.lb_issues.addItem("Явных скачков и резких углов не найдено")
            return
        for item in issues:
            t_ms = int(item.get("t", 0))
            desc = item.get("desc", "Проблема")
            self._issue_times.append(t_ms)
            self.lb_issues.addItem(f"[{fmt_t(t_ms)}] {desc}")

    def jump_to_selected_issue(self):
        idx = self.lb_issues.currentRow()
        if 0 <= idx < len(self._issue_times):
            self.timeline.set_value(self._issue_times[idx])

    def open_output_dir(self):
        target = self.last_dest_dir if os.path.isdir(self.last_dest_dir) else str(D_OUT)
        os.makedirs(target, exist_ok=True)
        open_dir(target)

    def export_report(self):
        if not self.last_report_txt:
            return self.app.notify("Сначала запусти обработку, чтобы сформировать отчёт", "warn")
        os.makedirs(str(D_WIP), exist_ok=True)
        rep_path = os.path.join(str(D_WIP), "cube_pipeline_report.txt")
        write_text(rep_path, self.last_report_txt)
        self.app.notify(f"Отчёт сохранён: {os.path.basename(rep_path)}", "ok")

    def pick_file(self):
        p, _ = QFileDialog.getOpenFileName(self.app, "Выбери один .osu или .osz файл", str(D_IN),
                                           "osu! карта или пак (*.osu *.osz)")
        if p:
            self._load_target_path(p)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self.app, "Выбери папку с .osu или .osz файлами", str(D_IN))
        if not d:
            return
        self.c_path.setText(d)
        self.cube_log.clear()
        self.cube_log.add(f"Выбрана папка для пакетного прогона: {d}", "info")

    def _load_target_path(self, p: str):
        self.c_path.setText(p)
        self.cube_log.clear()
        self._populate_issues([])
        self._update_checklist_ui([])
        self.orig_objs, self.new_objs = [], []
        self.osz_entries = []
        self.cb_osz_diff.clear()

        if p.lower().endswith(".osu"):
            info = parse_osu(read_text(p))
            self.orig_objs = info.get("objs", [])
            self.setup_timeline(self.orig_objs)
            ai_val = ai_likeness_score(self.orig_objs) if len(self.orig_objs) >= 10 else 0
            self.lbl_info.setText(f"AI Score: {ai_val}")
            self.cube_log.add(f"Загружен .osu: {os.path.basename(p)} ({len(self.orig_objs)} об.)")
        elif p.lower().endswith(".osz"):
            try:
                with zipfile.ZipFile(p, "r") as z:
                    osu_list = [n for n in z.namelist() if n.lower().endswith(".osu")]
                    self.osz_entries = [(n, _decode_osu_bytes(z.read(n))) for n in osu_list]
                    self.cube_log.add(f"Загружен .osz: {os.path.basename(p)}", "info")
                    self.cube_log.add(f"Найдено карт внутри: {len(osu_list)}")
                    for name in osu_list:
                        self.cube_log.add(f"  • {name}", "dim")
                    if self.osz_entries:
                        names = [n for n, _ in self.osz_entries]
                        self.cb_osz_diff.addItems(names)
                        self.preview_selected_osz_diff()
                        self.lbl_info.setText(f"Пак: {len(osu_list)} дифов")
            except Exception as e:
                self.cube_log.add(f"Ошибка чтения архива: {e}", "err")

        self.draw_playfield()

    def preview_selected_osz_diff(self):
        target = self.cb_osz_diff.currentText()
        for name, txt in self.osz_entries:
            if name == target:
                self.orig_objs = parse_osu(txt).get("objs", [])
                self.new_objs = []
                self.setup_timeline(self.orig_objs)
                self.draw_playfield()
                break

    def setup_timeline(self, objs):
        if not objs:
            self.timeline.set_range(0, 1000)
            self.timeline.set_value(0)
            return
        t0 = max(0, objs[0].get("t", 0) - 500)
        t1 = max(o.get("end", o.get("t", 0)) for o in objs) + 500
        self.timeline.set_range(t0, max(t0 + 1000, t1))
        self.timeline.set_value(t0)

    def _get_seed(self) -> int:
        try:
            return int((self.v_seed.text() or "727").strip())
        except ValueError:
            return 727

    def _build_cube_cfg(self) -> dict:
        return {
            "scale_mode": "fill_cube" if self.v_fill_mode.isChecked() else "comfortable",
            "padding_px": float(self.v_pad.value()),
            "humanize_strength": float(self.v_strength.value()),
            "adjust_cs": bool(self.v_adjust_cs.isChecked()),
            "adaptive_density": bool(self.v_adaptive.isChecked()),
            "challenge_mode": self.cb_challenge.currentText() or "none",
        }

    def action_ab_seed(self):
        path = (self.c_path.text() or "").strip()
        if not os.path.isfile(path) or not path.lower().endswith(".osu"):
            return self.app.notify("A/B сравнение seed работает для одиночного .osu файла", "warn")
        steps = self._collect_steps() or ["cube", "humanize", "lint_check"]
        cfg = self._build_cube_cfg()
        base_seed = self._get_seed()
        raw_txt = read_text(path).replace("\r\n", "\n").replace("\r", "\n")
        _, st_a, _, _ = run_pipeline_on_osu(raw_txt, steps, cfg, seed=base_seed, tag_suffix="")
        _, st_b, _, _ = run_pipeline_on_osu(raw_txt, steps, cfg, seed=base_seed + 1, tag_suffix="")
        self.cube_log.add(
            f"A (seed={base_seed}): AI {st_a['orig_ai']}→{st_a['new_ai']}, Clamp {st_a['clamped']}, Issues {len(st_a['issues'])}",
            "info")
        self.cube_log.add(
            f"B (seed={base_seed + 1}): AI {st_b['orig_ai']}→{st_b['new_ai']}, Clamp {st_b['clamped']}, Issues {len(st_b['issues'])}",
            "ok")

    def _process_single_osu(self, src_path: str, steps: list, cfg: dict, seed: int):
        dest, stats, orig, new, report = _process_osu_file(src_path, steps, cfg, seed)
        self.last_dest_dir = str(D_WIP)
        self.last_report_txt = report
        return dest, stats, orig, new

    def action_cubify(self):
        if self._job is not None and self._job.isRunning():
            return self.app.notify("Обработка папки уже идёт", "warn")
        path = (self.c_path.text() or "").strip()
        steps = self._collect_steps()
        if not steps:
            return self.app.notify("Включи хотя бы один шаг конвейера", "warn")

        cfg = self._build_cube_cfg()
        seed = self._get_seed()
        self.cube_log.clear()

        try:
            if os.path.isdir(path):
                targets = []
                for root_dir, _, files in os.walk(path):
                    for fn in sorted(files):
                        if fn.lower().endswith(".osu"):
                            targets.append(os.path.join(root_dir, fn))
                if not targets:
                    return self.app.notify("В выбранной папке не найдено .osu файлов", "warn")
                self._start_folder_job(targets, steps, cfg, seed)
                return

            if not os.path.isfile(path):
                return self.app.notify("Сначала выбери .osu, .osz или папку", "warn")

            low = path.lower()
            if not low.endswith((".osu", ".osz")):
                return self.app.notify("Поддерживается .osu, .osz или папка", "warn")

            if low.endswith(".osu"):
                dest, stats, orig, new = self._process_single_osu(path, steps, cfg, seed)
                self.orig_objs, self.new_objs = orig, new
                self.setup_timeline(self.new_objs or self.orig_objs)
                self._populate_issues(stats.get("issues", []))
                self._update_checklist_ui(stats.get("checklist", []))
                self.draw_playfield()

                tp = stats.get("timing", {})
                bpm_str = f"{tp.get('min_bpm')}–{tp.get('max_bpm')} BPM" if tp.get("min_bpm") else "BPM —"
                self.lbl_info.setText(
                    f"Scale {stats['scale_x']}×{stats['scale_y']} | {bpm_str} | AI {stats['orig_ai']}→{stats['new_ai']}")
                self.cube_log.add(f"Готово: {os.path.basename(dest)}", "ok")
                self.cube_log.add(
                    f"Шаги: {' → '.join(stats.get('steps_run', []))} | Сдвинуто: {stats.get('moved', 0)}/{stats.get('total', 0)}",
                    "info")
                self.cube_log.add(
                    f"Clamp: {stats['clamped']} | AI: {stats['orig_ai']} → {stats['new_ai']} | Проблем: {len(stats.get('issues', []))}")
                self.run_history.append(f"{os.path.basename(path)} [{'+'.join(steps)}, seed={seed}]")
                self.cube_log.add(f"История ({len(self.run_history)}): {self.run_history[-1]}", "dim")
                self.app.notify(f"Конвейер выполнен: {os.path.basename(dest)}", "ok")

            elif low.endswith(".osz"):
                os.makedirs(str(D_OUT), exist_ok=True)
                self.last_dest_dir = str(D_OUT)
                base_osz = os.path.basename(path)
                out_osz_name = base_osz[:-4] + "_cube.osz" if base_osz.lower().endswith(".osz") else base_osz + "_cube.osz"
                dest = os.path.join(str(D_OUT), out_osz_name)
                processed = 0
                records = []
                preview_target = self.cb_osz_diff.currentText()
                chosen_preview = None
                first_preview = None

                with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        raw = zin.read(item.filename)
                        if item.filename.lower().endswith(".osu"):
                            txt = _decode_osu_bytes(raw)
                            new_txt, stats, orig, new = run_pipeline_on_osu(
                                txt, steps=steps, cube_cfg=cfg, seed=seed + processed, tag_suffix="[1:1 Cube]")
                            out_osu_name = (item.filename[:-4] + " [1x1 Cube].osu"
                                            if self.v_step_tags.isChecked() else item.filename)
                            zout.writestr(out_osu_name, new_txt.replace("\n", "\r\n").encode("utf-8"))
                            processed += 1
                            rec = dict(stats)
                            rec["name"] = os.path.basename(item.filename)
                            records.append(rec)
                            self.cube_log.add(
                                f"✓ {rec['name']} → Clamp {rec['clamped']} | Issues {len(rec.get('issues', []))} | AI {rec['orig_ai']}→{rec['new_ai']}",
                                "ok")
                            if first_preview is None:
                                first_preview = (orig, new, stats)
                            if item.filename == preview_target:
                                chosen_preview = (orig, new, stats)
                        else:
                            zout.writestr(item, raw)

                if processed == 0:
                    self.app.notify("Внутри .osz не найдено ни одного .osu файла", "warn")
                    return

                active_preview = chosen_preview or first_preview
                if active_preview:
                    self.orig_objs, self.new_objs, st = active_preview
                    self.setup_timeline(self.new_objs or self.orig_objs)
                    self._populate_issues(st.get("issues", []))
                    self._update_checklist_ui(st.get("checklist", []))
                    self.draw_playfield()

                cmp_summary = compare_diffs_summary(records)
                self.last_report_txt = (
                    f"Пак: {base_osz}\nКарт: {cmp_summary['count']}\n"
                    f"Max Clamp: {cmp_summary['max_clamp_diff']}\n"
                    f"Max Issues: {cmp_summary['max_issues_diff']}\n"
                    f"Средний ΔAI: {cmp_summary['avg_ai_delta']:+}"
                )
                self.lbl_info.setText(f"Пак: {cmp_summary['count']} карт | ΔAI {cmp_summary['avg_ai_delta']:+}")
                self.cube_log.add(
                    f"Кросс-дифф анализ: max Clamp={cmp_summary['max_clamp_diff']} | max Issues={cmp_summary['max_issues_diff']}",
                    "info")
                self.run_history.append(f"{base_osz} ({processed} дифов, {'+'.join(steps)})")
                self.cube_log.add(f"История ({len(self.run_history)}): {self.run_history[-1]}", "dim")
                self.app.notify(f"Готов .osz пак ({processed} карт): {os.path.basename(dest)}", "ok")

        except Exception as e:
            QMessageBox.critical(self.app, "Ошибка обработки", str(e))

    # ── Фоновая обработка папки ───────────────────────────────────────
    def _start_folder_job(self, targets, steps, cfg, seed):
        job = Job(lambda j: self._folder_work(j, targets, steps, cfg, seed), self.app)
        job.on_progress = lambda t: self.jobbar.update_progress(*t)
        job.on_log = lambda t: self.cube_log.add(*t)
        job.on_done = self._folder_done
        job.on_fail = self._job_failed
        self.jobbar.cancel_requested.connect(job.cancel)
        self.jobbar.start(len(targets), "Папка…")
        self._job = job
        job.start()

    def _folder_work(self, job, targets, steps, cfg, seed):
        first = None
        done = 0
        for idx, fp in enumerate(targets):
            if job.cancelled():
                job.say("Отменено пользователем", "warn")
                break
            dest, st, orig, new, report = _process_osu_file(fp, steps, cfg, seed + idx)
            done += 1
            job.say(f"✓ {os.path.basename(fp)} → Clamp {st['clamped']} | AI {st['orig_ai']}→{st['new_ai']}", "ok")
            job.report(idx + 1, len(targets), os.path.basename(fp))
            if first is None:
                first = (orig, new, st, report)
        return done, first, job.cancelled()

    def _folder_done(self, res):
        done, first, cancelled = res
        if first:
            orig, new, st, report = first
            self.orig_objs, self.new_objs = orig, new
            self.last_dest_dir = str(D_WIP)
            self.last_report_txt = report
            self.setup_timeline(self.new_objs or self.orig_objs)
            self._populate_issues(st.get("issues", []))
            self._update_checklist_ui(st.get("checklist", []))
            self.draw_playfield()
        text = f"Папка: {done} .osu готово" + (" (отменено)" if cancelled else "")
        self.lbl_info.setText(text)
        self.jobbar.finish(text)
        self.app.notify(text, "warn" if cancelled else "ok")

    def _job_failed(self, msg):
        self.jobbar.finish("Ошибка обработки")
        self.cube_log.add(msg, "err")
        self.app.notify("Обработка папки остановлена с ошибкой", "err")

    def export_png(self):
        try:
            path = save_png(self.pf, self.app, str(D_WIP / "cube_preview.png"))
        except OSError as e:
            return self.app.notify(str(e), "err")
        if path:
            self.app.notify(f"Превью сохранено: {os.path.basename(path)}", "ok")

    # ── Настройки между запусками ─────────────────────────────────────
    def _restore(self, p):
        if not p:
            return
        steps = p.get("steps", {})
        for name, t in (("cube", self.v_step_cube), ("humanize", self.v_step_hum),
                        ("lint", self.v_step_lint), ("tags", self.v_step_tags)):
            t.setChecked(bool(steps.get(name, True)))
        self.v_fill_mode.setChecked(bool(p.get("fill_mode", False)))
        self.v_adaptive.setChecked(bool(p.get("adaptive", True)))
        self.v_adjust_cs.setChecked(bool(p.get("adjust_cs", True)))
        if "pad" in p:
            self.v_pad.set_value(float(p["pad"]))
        if "strength" in p:
            self.v_strength.set_value(float(p["strength"]))
        if "seed" in p:
            self.v_seed.setText(str(p["seed"]))
        if p.get("preset") in CUBE_PRESETS:
            _set_combo(self.cb_preset, p["preset"])
        if "challenge" in p:
            _set_combo(self.cb_challenge, p["challenge"])

    def prefs(self):
        return {"cube_prefs": {
            "steps": {"cube": self.v_step_cube.isChecked(), "humanize": self.v_step_hum.isChecked(),
                      "lint": self.v_step_lint.isChecked(), "tags": self.v_step_tags.isChecked()},
            "fill_mode": self.v_fill_mode.isChecked(),
            "adaptive": self.v_adaptive.isChecked(),
            "adjust_cs": self.v_adjust_cs.isChecked(),
            "pad": self.v_pad.value(),
            "strength": self.v_strength.value(),
            "seed": self.v_seed.text(),
            "preset": self.cb_preset.currentText(),
            "challenge": self.cb_challenge.currentText(),
        }}

    # ── Playfield ─────────────────────────────────────────────────────
    def draw_playfield(self):
        self.pf.update()

    def _paint_cube(self, p, w, h):
        fit = fit_playfield(w, h)
        if fit is None:
            return
        scale, ox, oy = fit

        def to_scr(px, py):
            return ox + px * scale, oy + py * scale

        x0, y0 = to_scr(0, 0)
        x1, y1 = to_scr(512, 384)
        p.setPen(make_pen(BORDER, 1))
        p.setBrush(QColor("#0a0c12"))
        p.drawRoundedRect(QRectF(x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2), 8, 8)

        cx0, cy0 = to_scr(CUBE_MIN_X, CUBE_MIN_Y)
        cx1, cy1 = to_scr(CUBE_MAX_X, CUBE_MAX_Y)
        p.setPen(make_pen(PINK, 2))
        p.setBrush(QColor("#101521"))
        p.drawRect(QRectF(cx0, cy0, cx1 - cx0, cy1 - cy0))

        step = (CUBE_MAX_X - CUBE_MIN_X) / 6.0
        p.setPen(make_pen("#171e2e", 1))
        for i in range(1, 6):
            gx = CUBE_MIN_X + i * step
            a, b = to_scr(gx, CUBE_MIN_Y), to_scr(gx, CUBE_MAX_Y)
            p.drawLine(QPointF(*a), QPointF(*b))
            gy = CUBE_MIN_Y + i * step
            c, d = to_scr(CUBE_MIN_X, gy), to_scr(CUBE_MAX_X, gy)
            p.drawLine(QPointF(*c), QPointF(*d))

        if self.v_show_heat.isChecked() and (self.new_objs or self.orig_objs):
            heat_objs = self.new_objs or self.orig_objs
            grid = build_heatmap_grid(heat_objs, cols=16, rows=12)
            cw, ch = 512.0 / 16.0, 384.0 / 12.0
            p.setPen(Qt.PenStyle.NoPen)
            for r_idx, row in enumerate(grid):
                for c_idx, val in enumerate(row):
                    if val > 0.08:
                        hx0, hy0 = to_scr(c_idx * cw, r_idx * ch)
                        hx1, hy1 = to_scr((c_idx + 1) * cw, (r_idx + 1) * ch)
                        fill = "#3b1526" if val > 0.65 else ("#291d38" if val > 0.32 else "#182238")
                        p.setBrush(QColor(fill))
                        p.drawRect(QRectF(hx0, hy0, hx1 - hx0, hy1 - hy0))

        cur_t = self.timeline.value()
        window = 1600
        r = 13 * scale
        show_sliders = bool(self.v_show_sliders.isChecked())

        def draw(objs, ghost=False):
            vis = [o for o in objs if cur_t - 400 <= o.get("t", 0) <= cur_t + window]
            for a, b in zip(vis, vis[1:]):
                if a.get("kind") == "spinner" or b.get("kind") == "spinner":
                    continue
                ax, ay = to_scr(a.get("ex", a["x"]), a.get("ey", a["y"]))
                bx, by = to_scr(b["x"], b["y"])
                p.setPen(make_pen("#262c3d", 1, dash=True) if ghost else make_pen(PINK_DIM, 2))
                p.drawLine(QPointF(ax, ay), QPointF(bx, by))

            if show_sliders:
                for o in vis:
                    if o.get("kind") == "slider":
                        pts = o.get("pts") or []
                        if len(pts) >= 2:
                            path = QPainterPath()
                            first = True
                            for px, py in pts:
                                pt = QPointF(*to_scr(px, py))
                                if first:
                                    path.moveTo(pt)
                                    first = False
                                else:
                                    path.lineTo(pt)
                            p.setBrush(Qt.BrushStyle.NoBrush)
                            if ghost:
                                p.setPen(make_pen("#39425c", 2, dash=True))
                            else:
                                p.setPen(make_pen(BLUE, 3))
                            p.drawPath(path)

            for o in vis:
                if o.get("kind") == "spinner":
                    continue
                c = QPointF(*to_scr(o["x"], o["y"]))
                if ghost:
                    p.setPen(make_pen(TEXT_3, 1, dash=True))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(c, r, r)
                    continue
                p.setPen(make_pen("#ffffff", 2))
                p.setBrush(QColor(PINK))
                p.drawEllipse(c, r, r)

        if self.v_show_orig.isChecked() and self.orig_objs:
            draw(self.orig_objs, True)
        if self.new_objs:
            draw(self.new_objs, False)
        if not self.orig_objs and not self.new_objs:
            p.setPen(make_pen(TEXT_3))
            p.setFont(font(10))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "Выбери .osu, .osz или папку и нажми «Запустить»")

