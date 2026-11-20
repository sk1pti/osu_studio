# -*- coding: utf-8 -*-
import copy
import math
from .parser import parse_osu, serialize_obj
from .io import get_val, set_val
from .humanizer import humanize_osu_text, ai_likeness_score

# Стандартное поле osu! 512x384 -> квадрат 1:1 (384x384 по центру: X в [64..448], Y в [0..384])
CUBE_MIN_X = 64.0
CUBE_MAX_X = 448.0
CUBE_MIN_Y = 0.0
CUBE_MAX_Y = 384.0
CUBE_SIZE = 384.0
CENTER_X = 256.0
CENTER_Y = 192.0

CUBE_PRESETS = {
    "Flow & Anti-AI": {
        "scale_mode": "comfortable",
        "padding_px": 14.0,
        "humanize_after": True,
        "humanize_strength": 0.65,
        "adjust_cs": True,
        "tag_version": True,
        "adaptive_density": True,
        "challenge_mode": "none",
    },
    "Strict 1:1": {
        "scale_mode": "comfortable",
        "padding_px": 12.0,
        "humanize_after": False,
        "humanize_strength": 0.25,
        "adjust_cs": False,
        "tag_version": True,
        "adaptive_density": False,
        "challenge_mode": "none",
    },
    "Pack Batch": {
        "scale_mode": "fill_cube",
        "padding_px": 14.0,
        "humanize_after": True,
        "humanize_strength": 0.55,
        "adjust_cs": True,
        "tag_version": True,
        "adaptive_density": True,
        "challenge_mode": "none",
    },
    "Mirror Cube": {
        "scale_mode": "comfortable",
        "padding_px": 14.0,
        "humanize_after": True,
        "humanize_strength": 0.50,
        "adjust_cs": True,
        "tag_version": True,
        "adaptive_density": True,
        "challenge_mode": "mirror_x",
    },
    "Narrow Corridor": {
        "scale_mode": "comfortable",
        "padding_px": 16.0,
        "humanize_after": True,
        "humanize_strength": 0.45,
        "adjust_cs": True,
        "tag_version": True,
        "adaptive_density": True,
        "challenge_mode": "corridor_y",
    },
}


def _clamp_cube(x, y, margin=12.0):
    nx = max(CUBE_MIN_X + margin, min(CUBE_MAX_X - margin, x))
    ny = max(CUBE_MIN_Y + margin, min(CUBE_MAX_Y - margin, y))
    return nx, ny


def _replace_hitobjects(text, objs):
    new_lines = [serialize_obj(o) for o in objs]
    out, cur, replaced = [], None, False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            out.append(line)
            if cur == "HitObjects" and not replaced:
                out.extend(new_lines)
                replaced = True
        elif cur == "HitObjects":
            continue
        else:
            out.append(line)
    return "\n".join(out)


def _compute_density_map(objs):
    n = len(objs)
    if n == 0:
        return []
    times = [float(o.get("t", 0)) for o in objs]
    densities = [0.0] * n
    left = 0
    right = 0
    for i in range(n):
        t_cur = times[i]
        while left < n and times[left] < t_cur - 300.0:
            left += 1
        while right < n and times[right] <= t_cur + 300.0:
            right += 1
        densities[i] = max(0.0, float(right - left - 1))
    max_d = max(densities) if densities else 1.0
    if max_d <= 0:
        return [0.0] * n
    return [min(1.0, d / max_d) for d in densities]


def build_heatmap_grid(objs, cols=16, rows=12):
    # Возвращает нормированную сетку плотности координат [rows][cols] по полю 512x384
    grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
    if not objs:
        return grid
    for o in objs:
        if o.get("kind") == "spinner":
            continue
        pts = o.get("pts") if (o.get("kind") == "slider" and o.get("pts")) else [(o["x"], o["y"])]
        for px, py in pts:
            c = max(0, min(cols - 1, int(float(px) / 512.0 * cols)))
            r = max(0, min(rows - 1, int(float(py) / 384.0 * rows)))
            grid[r][c] += 1.0
    peak = max((val for row in grid for val in row), default=0.0)
    if peak <= 0.0:
        return grid
    return [[val / peak for val in row] for row in grid]


def _detect_issues(objs):
    issues = []
    pts_objs = [o for o in objs if o.get("kind") != "spinner"]
    for prev, cur in zip(pts_objs, pts_objs[1:]):
        dt = max(1.0, float(cur.get("t", 0)) - float(prev.get("end", prev.get("t", 0))))
        dist = math.hypot(
            float(cur["x"]) - float(prev.get("ex", prev["x"])),
            float(cur["y"]) - float(prev.get("ey", prev["y"])),
        )
        vel = dist / dt
        if dist > 235.0 and dt < 220.0:
            issues.append({
                "t": int(cur.get("t", 0)),
                "type": "jump",
                "desc": f"Дальний скачок {int(dist)}px за {int(dt)}ms",
            })
        elif vel > 1.45:
            issues.append({
                "t": int(cur.get("t", 0)),
                "type": "speed",
                "desc": f"Резкая скорость {vel:.2f} px/ms",
            })

    for a, b, c in zip(pts_objs, pts_objs[1:], pts_objs[2:]):
        v1x = float(b["x"]) - float(a.get("ex", a["x"]))
        v1y = float(b["y"]) - float(a.get("ey", a["y"]))
        v2x = float(c["x"]) - float(b.get("ex", b["x"]))
        v2y = float(c["y"]) - float(b.get("ey", b["y"]))
        n1 = math.hypot(v1x, v1y)
        n2 = math.hypot(v2x, v2y)
        if n1 > 25.0 and n2 > 25.0:
            cos_ang = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (n1 * n2)))
            deg = math.degrees(math.acos(cos_ang))
            if deg > 142.0:
                issues.append({
                    "t": int(b.get("t", 0)),
                    "type": "angle",
                    "desc": f"Резкий разворот {int(deg)}°",
                })
    issues.sort(key=lambda item: item["t"])
    return issues[:25]


def _apply_challenge_mode(objs, mode: str):
    if not mode or mode == "none":
        return
    for o in objs:
        if o.get("kind") == "spinner":
            continue
        if mode == "mirror_x":
            o["x"] = int(round(2.0 * CENTER_X - float(o["x"])))
            if o.get("kind") == "slider" and o.get("pts"):
                o["pts"] = [(int(round(2.0 * CENTER_X - float(px))), int(round(float(py)))) for px, py in o["pts"]]
                o["x"], o["y"] = o["pts"][0]
                slides = o.get("slides", 1)
                o["ex"], o["ey"] = o["pts"][-1] if slides % 2 == 1 else o["pts"][0]
            else:
                o["ex"], o["ey"] = o["x"], o["y"]
        elif mode == "corridor_y":
            o["y"] = int(round(CENTER_Y + (float(o["y"]) - CENTER_Y) * 0.58))
            if o.get("kind") == "slider" and o.get("pts"):
                o["pts"] = [
                    (int(round(float(px))), int(round(CENTER_Y + (float(py) - CENTER_Y) * 0.58)))
                    for px, py in o["pts"]
                ]
                o["x"], o["y"] = o["pts"][0]
                slides = o.get("slides", 1)
                o["ex"], o["ey"] = o["pts"][-1] if slides % 2 == 1 else o["pts"][0]
            else:
                o["ex"], o["ey"] = o["x"], o["y"]


def _clamp_objs_to_cube(objs, margin):
    clamped_count = 0
    for o in objs:
        if o.get("kind") == "spinner":
            o["x"], o["y"] = 256, 192
            o["ex"], o["ey"] = 256, 192
            continue

        if o.get("kind") == "slider":
            pts = o.get("pts") or [(o["x"], o["y"])]
            min_px = min(p[0] for p in pts)
            max_px = max(p[0] for p in pts)
            min_py = min(p[1] for p in pts)
            max_py = max(p[1] for p in pts)

            dx = 0.0
            dy = 0.0
            if min_px < CUBE_MIN_X + margin:
                dx = (CUBE_MIN_X + margin) - min_px
            elif max_px > CUBE_MAX_X - margin:
                dx = (CUBE_MAX_X - margin) - max_px

            if min_py < CUBE_MIN_Y + margin:
                dy = (CUBE_MIN_Y + margin) - min_py
            elif max_py > CUBE_MAX_Y - margin:
                dy = (CUBE_MAX_Y - margin) - max_py

            if abs(dx) > 0.01 or abs(dy) > 0.01:
                clamped_count += 1

            new_pts = []
            for px, py in pts:
                fx, fy = _clamp_cube(px + dx, py + dy, margin=4.0)
                new_pts.append((int(round(fx)), int(round(fy))))

            o["pts"] = new_pts
            o["x"], o["y"] = new_pts[0]
            slides = o.get("slides", 1)
            o["ex"], o["ey"] = new_pts[-1] if slides % 2 == 1 else new_pts[0]
        else:
            nx, ny = float(o["x"]), float(o["y"])
            fx, fy = _clamp_cube(nx, ny, margin=margin)
            if abs(fx - nx) > 0.01 or abs(fy - ny) > 0.01:
                clamped_count += 1
            o["x"], o["y"] = int(round(fx)), int(round(fy))
            o["ex"], o["ey"] = o["x"], o["y"]
    return clamped_count


def _count_moved_objs(orig_objs, new_objs):
    moved = 0
    for a, b in zip(orig_objs, new_objs):
        if abs(float(a.get("x", 0)) - float(b.get("x", 0))) > 0.5 or abs(float(a.get("y", 0)) - float(b.get("y", 0))) > 0.5:
            moved += 1
    return moved


def cubify_osu_text(
    text,
    scale_mode="comfortable",
    padding_px=14.0,
    humanize_after=True,
    humanize_strength=0.65,
    seed=727,
    tag_version=True,
    adjust_cs=True,
    adaptive_density=True,
    challenge_mode="none",
):
    info = parse_osu(text)
    orig_objs = copy.deepcopy(info.get("objs", []))
    objs = info.get("objs", [])

    stats = {
        "total": len(objs),
        "moved": 0,
        "scale_x": 0.75,
        "scale_y": 1.0,
        "sliders_scaled": 0,
        "clamped": 0,
        "orig_ai": ai_likeness_score(orig_objs) if len(orig_objs) >= 10 else 0,
        "new_ai": 0,
        "orig_cs": None,
        "new_cs": None,
        "avg_density": 0.0,
        "challenge_mode": challenge_mode,
        "issues": [],
    }

    if not objs:
        return text, stats, orig_objs, objs

    margin = max(6.0, min(32.0, float(padding_px)))
    avail_w = CUBE_SIZE - 2.0 * margin
    avail_h = CUBE_SIZE - 2.0 * margin

    densities = _compute_density_map(objs)
    avg_d = sum(densities) / len(densities) if densities else 0.0
    stats["avg_density"] = round(avg_d, 2)

    if scale_mode == "fill_cube":
        sx = avail_w / 512.0
        sy = avail_h / 384.0
    else:
        xs, ys = [], []
        for o in objs:
            if o.get("kind") == "spinner":
                continue
            pts = o.get("pts") if o.get("kind") == "slider" else [(o["x"], o["y"])]
            for px, py in (pts or []):
                xs.append(px)
                ys.append(py)
        if xs and ys:
            span_x = max(1.0, max(xs) - min(xs))
            span_y = max(1.0, max(ys) - min(ys))
            fit_uniform = min(avail_w / max(span_x, 384.0), avail_h / max(span_y, 288.0), 0.88)
            min_scale = 0.72 if adaptive_density and avg_d > 0.55 else 0.68
            fit_uniform = max(min_scale, fit_uniform)
            sx = fit_uniform
            sy = fit_uniform
        else:
            sx = avail_w / 512.0
            sy = avail_w / 512.0

    stats["scale_x"] = round(sx, 3)
    stats["scale_y"] = round(sy, 3)

    for o in objs:
        if o.get("kind") == "spinner":
            o["x"], o["y"] = 256, 192
            o["ex"], o["ey"] = 256, 192
            continue

        if o.get("kind") == "slider":
            src_pts = o.get("pts") or [(o["x"], o["y"])]
            new_pts = []
            for px, py in src_pts:
                npx = CENTER_X + (px - CENTER_X) * sx
                npy = CENTER_Y + (py - CENTER_Y) * sy
                new_pts.append((int(round(npx)), int(round(npy))))

            o["pts"] = new_pts
            o["x"], o["y"] = new_pts[0]
            slides = o.get("slides", 1)
            o["ex"], o["ey"] = new_pts[-1] if slides % 2 == 1 else new_pts[0]
            o["modified"] = True
            o.setdefault("reasons", []).append("1:1 куб (слайдер)")
            stats["sliders_scaled"] += 1
        else:
            nx = CENTER_X + (o["x"] - CENTER_X) * sx
            ny = CENTER_Y + (o["y"] - CENTER_Y) * sy
            o["x"], o["y"] = int(round(nx)), int(round(ny))
            o["ex"], o["ey"] = o["x"], o["y"]
            o["modified"] = True
            o.setdefault("reasons", []).append("1:1 куб")

    _apply_challenge_mode(objs, challenge_mode)
    stats["clamped"] += _clamp_objs_to_cube(objs, margin=margin)
    res_text = _replace_hitobjects(text, objs)

    if humanize_after and len(objs) >= 3:
        eff_strength = float(humanize_strength)
        if adaptive_density and avg_d > 0.65:
            eff_strength = max(0.15, eff_strength * 0.75)
        h_opts = {
            "fix_micro_sliders": True,
            "smooth_streams": True,
            "break_collinear": True,
            "break_spirals": True,
            "break_repeats": True,
            "fix_overlaps": True,
            "fix_edges": False,
            "smart_nc": True,
            "strength": eff_strength,
            "organic_jitter": 1.8,
            "seed": int(seed),
        }
        res_text, _, _, h_objs = humanize_osu_text(res_text, h_opts)
        if h_objs:
            objs = h_objs
        stats["clamped"] += _clamp_objs_to_cube(objs, margin=margin)
        res_text = _replace_hitobjects(res_text, objs)

    try:
        cs_raw = get_val(res_text, "CircleSize")
        if cs_raw is not None and str(cs_raw).strip() != "":
            cs_val = float(cs_raw)
            stats["orig_cs"] = cs_val
            if adjust_cs and cs_val < 5.5:
                new_cs = round(min(6.5, cs_val + 0.3), 1)
                res_text = set_val(res_text, "CircleSize", "%g" % new_cs, "Difficulty")
                stats["new_cs"] = new_cs
            else:
                stats["new_cs"] = cs_val
    except ValueError:
        pass

    if tag_version:
        ver = get_val(res_text, "Version")
        suffix = "[1:1 Cube]" if challenge_mode == "none" else f"[1:1 Cube · {challenge_mode}]"
        if ver and "[1:1" not in ver and "Cube" not in ver:
            res_text = set_val(res_text, "Version", f"{ver} {suffix}", "Metadata")

    stats["moved"] = _count_moved_objs(orig_objs, objs)
    stats["new_ai"] = ai_likeness_score(objs) if len(objs) >= 10 else 0
    stats["issues"] = _detect_issues(objs)
    return res_text, stats, orig_objs, objs