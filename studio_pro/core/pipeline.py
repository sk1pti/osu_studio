# -*- coding: utf-8 -*-
import copy
import json
import math
import os
from .parser import parse_osu
from .io import get_val, set_val
from .humanizer import humanize_osu_text, ai_likeness_score
from .cube import cubify_osu_text


DEFAULT_RECIPES = {
    "Cube + Anti-AI + Tag": {
        "steps": ["cube", "humanize", "lint_check", "tags"],
        "cube_preset": "Flow & Anti-AI",
        "tag_suffix": "[1:1 Cube]",
    },
    "Strict 1:1 Clean": {
        "steps": ["cube", "lint_check", "tags"],
        "cube_preset": "Strict 1:1",
        "tag_suffix": "[Strict 1:1]",
    },
    "Full Pack Pipeline": {
        "steps": ["cube", "humanize", "lint_check", "tags"],
        "cube_preset": "Pack Batch",
        "tag_suffix": "[1:1 Cube]",
    },
    "Mirror Challenge": {
        "steps": ["cube", "humanize", "lint_check", "tags"],
        "cube_preset": "Mirror Cube",
        "tag_suffix": "[1:1 Mirror]",
    },
}


def load_recipes(recipes_path: str) -> dict:
    recipes = copy.deepcopy(DEFAULT_RECIPES)
    if recipes_path and os.path.isfile(recipes_path):
        try:
            with open(recipes_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict) and isinstance(v.get("steps"), list):
                        recipes[str(k)] = v
        except Exception:
            pass
    return recipes


def save_recipes(recipes_path: str, recipes: dict) -> None:
    if not recipes_path:
        return
    os.makedirs(os.path.dirname(recipes_path), exist_ok=True)
    with open(recipes_path, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)


def extract_timing_summary(text: str) -> dict:
    in_tp = False
    bpms = []
    svs = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_tp = (line[1:-1] == "TimingPoints")
            continue
        if not in_tp or line.startswith("//"):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            beat_len = float(parts[1])
        except ValueError:
            continue
        if beat_len > 0:
            bpm = 60000.0 / beat_len
            if 20.0 <= bpm <= 600.0:
                bpms.append(bpm)
        elif beat_len < 0:
            sv = max(0.05, min(10.0, -100.0 / beat_len))
            svs.append(sv)
    return {
        "min_bpm": round(min(bpms), 1) if bpms else None,
        "max_bpm": round(max(bpms), 1) if bpms else None,
        "min_sv": round(min(svs), 2) if svs else 1.0,
        "max_sv": round(max(svs), 2) if svs else 1.0,
    }


def playable_checklist(objs: list) -> list:
    checks = []
    pts_objs = [o for o in objs if o.get("kind") != "spinner"]
    if not pts_objs:
        return [{"level": "warn", "t": 0, "msg": "Нет активных нот или слайдеров"}]

    out_of_bounds = 0
    overlaps = 0
    extreme_jumps = 0

    for o in pts_objs:
        xs = [float(o["x"])]
        ys = [float(o["y"])]
        if o.get("kind") == "slider" and o.get("pts"):
            xs.extend(float(p[0]) for p in o["pts"])
            ys.extend(float(p[1]) for p in o["pts"])
        if min(xs) < -8 or max(xs) > 520 or min(ys) < -8 or max(ys) > 392:
            out_of_bounds += 1

    for a, b in zip(pts_objs, pts_objs[1:]):
        dt = float(b.get("t", 0)) - float(a.get("t", 0))
        dist = math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"]))
        if abs(dt) < 12.0 and dist < 8.0:
            overlaps += 1
        if dist > 260.0 and max(1.0, dt) < 200.0:
            extreme_jumps += 1

    if out_of_bounds > 0:
        checks.append({"level": "err", "t": int(pts_objs[0].get("t", 0)), "msg": f"Выход за базовое поле 512×384: {out_of_bounds} об."})
    if overlaps > 0:
        checks.append({"level": "warn", "t": int(pts_objs[0].get("t", 0)), "msg": f"Возможные наложения близких нот: {overlaps}"})
    if extreme_jumps > 0:
        checks.append({"level": "warn", "t": int(pts_objs[0].get("t", 0)), "msg": f"Резкие дальние скачки: {extreme_jumps}"})
    if not checks:
        checks.append({"level": "ok", "t": int(pts_objs[0].get("t", 0)), "msg": "Чеклист пройден: явных проблем границ и наложений нет"})
    return checks


def format_diff_report(source_name: str, stats: dict) -> str:
    tp = stats.get("timing", {})
    bpm_str = f"{tp.get('min_bpm')}–{tp.get('max_bpm')} BPM" if tp.get("min_bpm") else "BPM —"
    lines = [
        f"Файл: {source_name}",
        f"Шаги: {' -> '.join(stats.get('steps_run', []))}",
        f"Режим челленджа: {stats.get('challenge_mode', 'none')}",
        f"Масштаб: X={stats.get('scale_x')}, Y={stats.get('scale_y')}",
        f"Сдвинуто объектов: {stats.get('moved', 0)} / {stats.get('total', 0)}",
        f"Зажато в рамку (clamped): {stats.get('clamped', 0)}",
        f"Слайдеров обработано: {stats.get('sliders_scaled', 0)}",
        f"CS: {stats.get('orig_cs')} -> {stats.get('new_cs')}",
        f"AI Score: {stats.get('orig_ai')} -> {stats.get('new_ai')}",
        f"Ритм: {bpm_str}, SV {tp.get('min_sv')}–{tp.get('max_sv')}, плотность {stats.get('avg_density')}",
        f"Найдено проблем: {len(stats.get('issues', []))}",
    ]
    return "\n".join(lines)


def run_pipeline_on_osu(
    text: str,
    steps: list,
    cube_cfg: dict,
    seed: int = 727,
    tag_suffix: str = "[1:1 Cube]",
):
    cur_text = text.replace("\r\n", "\n").replace("\r", "\n")
    orig_objs = parse_osu(cur_text).get("objs", [])
    objs = copy.deepcopy(orig_objs)
    timing = extract_timing_summary(cur_text)
    stats = {
        "total": len(objs),
        "moved": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "clamped": 0,
        "sliders_scaled": 0,
        "orig_ai": ai_likeness_score(orig_objs) if len(orig_objs) >= 10 else 0,
        "new_ai": ai_likeness_score(orig_objs) if len(orig_objs) >= 10 else 0,
        "orig_cs": None,
        "new_cs": None,
        "avg_density": 0.0,
        "challenge_mode": cube_cfg.get("challenge_mode", "none"),
        "issues": [],
        "checklist": [],
        "timing": timing,
        "steps_run": [],
    }

    applied_cube = False
    for step in steps:
        if step == "cube":
            cur_text, st, orig_objs, objs = cubify_osu_text(
                cur_text,
                scale_mode=cube_cfg.get("scale_mode", "comfortable"),
                padding_px=cube_cfg.get("padding_px", 14.0),
                humanize_after=False,
                humanize_strength=cube_cfg.get("humanize_strength", 0.65),
                seed=seed,
                tag_version=False,
                adjust_cs=cube_cfg.get("adjust_cs", True),
                adaptive_density=cube_cfg.get("adaptive_density", True),
                challenge_mode=cube_cfg.get("challenge_mode", "none"),
            )
            stats.update({k: v for k, v in st.items() if k != "timing"})
            stats["timing"] = timing
            stats["steps_run"].append("cube")
            applied_cube = True
        elif step == "humanize":
            if len(objs) >= 3:
                h_opts = {
                    "fix_micro_sliders": True,
                    "smooth_streams": True,
                    "break_collinear": True,
                    "break_spirals": True,
                    "break_repeats": True,
                    "fix_overlaps": True,
                    "fix_edges": False,
                    "smart_nc": True,
                    "strength": float(cube_cfg.get("humanize_strength", 0.65)),
                    "organic_jitter": 1.8,
                    "seed": int(seed),
                }
                cur_text, _, _, h_objs = humanize_osu_text(cur_text, h_opts)
                if h_objs:
                    objs = h_objs
            stats["new_ai"] = ai_likeness_score(objs) if len(objs) >= 10 else 0
            stats["steps_run"].append("humanize")
        elif step == "lint_check":
            stats["checklist"] = playable_checklist(objs)
            stats["steps_run"].append("lint_check")
        elif step == "tags":
            if tag_suffix:
                ver = get_val(cur_text, "Version")
                clean_tag = tag_suffix.strip("[]")
                if ver and clean_tag.lower() not in ver.lower():
                    cur_text = set_val(cur_text, "Version", f"{ver} {tag_suffix}", "Metadata")
            stats["steps_run"].append("tags")

    if not applied_cube:
        stats["new_ai"] = ai_likeness_score(objs) if len(objs) >= 10 else 0
    if not stats["checklist"]:
        stats["checklist"] = playable_checklist(objs)

    return cur_text, stats, orig_objs, objs


def compare_diffs_summary(diff_records: list) -> dict:
    if not diff_records:
        return {"count": 0, "max_clamp_diff": "", "max_issues_diff": "", "avg_ai_delta": 0.0}
    max_clamp = max(diff_records, key=lambda r: r.get("clamped", 0))
    max_issues = max(diff_records, key=lambda r: len(r.get("issues", [])))
    deltas = [r.get("new_ai", 0) - r.get("orig_ai", 0) for r in diff_records]
    return {
        "count": len(diff_records),
        "max_clamp_diff": f"{max_clamp.get('name', '?')} ({max_clamp.get('clamped', 0)})",
        "max_issues_diff": f"{max_issues.get('name', '?')} ({len(max_issues.get('issues', []))})",
        "avg_ai_delta": round(sum(deltas) / len(deltas), 1) if deltas else 0.0,
    }