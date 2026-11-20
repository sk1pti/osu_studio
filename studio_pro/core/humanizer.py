# -*- coding: utf-8 -*-
import copy, math, random
from .parser import parse_osu, serialize_obj
from ..config import *

DEFAULT_OPTS = {"fix_micro_sliders": True, "smooth_streams": True, "break_collinear": True, "break_spirals": True, "break_repeats": True, "fix_overlaps": True, "fix_edges": True, "smart_nc": True, "strength": 0.75, "organic_jitter": 2.0, "seed": 42}

def _clamp(x, y, m=FIELD_MARGIN_PX): return max(m, min(512 - m, x)), max(m, min(384 - m, y))
def _move(o, nx, ny):
    nx, ny = _clamp(nx, ny); dx, dy = nx - o["x"], ny - o["y"]
    if abs(dx) < 0.1 and abs(dy) < 0.1: return
    o["x"], o["y"] = int(round(nx)), int(round(ny))
    if o["kind"] == "slider":
        o["pts"] = [(int(round(px + dx)), int(round(py + dy))) for px, py in o["pts"]]
        o["ex"], o["ey"] = (o["pts"][-1] if o["slides"] % 2 == 1 else o["pts"][0])
    else: o["ex"], o["ey"] = o["x"], o["y"]

def ai_likeness_score(objs):
    if len(objs) < 10: return 0
    score, points = 0, 0
    col = 0
    for i in range(1, len(objs) - 1):
        a, b, c = objs[i - 1], objs[i], objs[i + 1]
        if "spinner" in (a["kind"], b["kind"], c["kind"]): continue
        v1x, v1y = b["x"] - a["ex"], b["y"] - a["ey"]; v2x, v2y = c["x"] - b["ex"], c["y"] - b["ey"]
        d1, d2 = math.hypot(v1x, v1y), math.hypot(v2x, v2y)
        if d1 > 30 and d2 > 30 and (v1x * v2x + v1y * v2y) / (d1 * d2) > 0.999: col += 1
    score += (col / max(1, len(objs) - 2)) * 40; points += 40
    
    q = sum(1 for o in objs if o["kind"] != "spinner" and o["x"] % 64 == 0 and o["y"] % 64 == 0)
    v = sum(1 for o in objs if o["kind"] != "spinner")
    if v: score += (q / v) * 30
    points += 30

    ds = [math.hypot(b["x"] - a["ex"], b["y"] - a["ey"]) for a, b in zip(objs, objs[1:]) if a["kind"] != "spinner" and b["kind"] != "spinner"]
    if ds:
        mean = sum(ds) / len(ds); std = math.sqrt(sum((d - mean) ** 2 for d in ds) / len(ds))
        score += (1.0 - min(1.0, std / 50.0)) * 30
    points += 30
    return int((score / max(1, points)) * 100)

def humanize_osu_text(text, opts=None):
    opts = {**DEFAULT_OPTS, **(opts or {})}
    rng = random.Random(opts["seed"])
    info = parse_osu(text); orig = copy.deepcopy(info["objs"]); objs = info["objs"]
    stats = {k: 0 for k in ("total", "micro_sliders", "stream_spacing", "collinear", "spirals", "repeats", "overlaps", "edges", "nc_fixed", "jittered", "orig_ai", "new_ai")}
    stats["total"] = len(objs)
    if len(objs) < 3: return text, stats, orig, objs
    stats["orig_ai"] = ai_likeness_score(objs)
    strength = float(opts["strength"])

    if opts["fix_micro_sliders"]:
        for o in objs:
            if o["kind"] == "slider" and o["len"] < MICRO_SLIDER_MAX_PX and o["slides"] == 1:
                nc_flag = o["ty"] & 4; o["kind"], o["ty"], o["pts"], o["ex"], o["ey"], o["end"] = "circle", 1 | nc_flag, [(o["x"], o["y"])], o["x"], o["y"], o["t"]
                o["modified"] = True; o["reasons"].append("Микро-слайдер в ноту"); stats["micro_sliders"] += 1

    if opts["smooth_streams"]:
        buf = []
        def flush(b):
            if len(b) < 3: return
            ds = [math.hypot(y["x"] - x["ex"], y["y"] - x["ey"]) for x, y in zip(b, b[1:])]
            if not ds: return
            md = sorted(ds)[len(ds) // 2]
            if md < 8: return
            for i in range(1, len(b)):
                prev, cur = b[i - 1], b[i]; vx, vy = cur["x"] - prev["ex"], cur["y"] - prev["ey"]; d = math.hypot(vx, vy)
                if d < 1: continue
                if d/md > 1.65 or d/md < 0.55:
                    td = d + (md - d) * (0.75 * strength); _move(cur, prev["ex"] + (vx / d) * td, prev["ey"] + (vy / d) * td)
                    cur["modified"] = True; cur["reasons"].append("Сглажен стрим"); stats["stream_spacing"] += 1
        for o in objs:
            if o["kind"] == "spinner": flush(buf); buf = []; continue
            if not buf: buf = [o]
            else:
                if 0 < o["t"] - buf[-1]["end"] <= STREAM_GAP_MS: buf.append(o)
                else: flush(buf); buf = [o]
        flush(buf)

    if opts["break_collinear"]:
        for i in range(1, len(objs) - 1):
            a, b, c = objs[i - 1], objs[i], objs[i + 1]
            if "spinner" in (a["kind"], b["kind"], c["kind"]): continue
            v1x, v1y = b["x"] - a["ex"], b["y"] - a["ey"]; v2x, v2y = c["x"] - b["ex"], c["y"] - b["ey"]
            d1, d2 = math.hypot(v1x, v1y), math.hypot(v2x, v2y)
            if d1 > 65 and d2 > 65 and (v1x * v2x + v1y * v2y) / (d1 * d2) > 0.994:
                px, py = -v1y / d1, v1x / d1; sh = min(26.0, d1 * 0.14) * strength * (1 if i % 2 == 0 else -1)
                _move(b, b["x"] + px * sh, b["y"] + py * sh); b["modified"] = True; b["reasons"].append("Робо-линия в дугу"); stats["collinear"] += 1

    if opts["break_spirals"]:
        for i in range(SPIRAL_MIN_PTS, len(objs)):
            w = objs[i - SPIRAL_MIN_PTS:i]
            if any(o["kind"] == "spinner" for o in w): continue
            cx, cy = sum(o["x"] for o in w)/len(w), sum(o["y"] for o in w)/len(w)
            r = [math.hypot(o["x"] - cx, o["y"] - cy) for o in w]; mr = sum(r) / len(r)
            if mr > 30 and all(abs(ri - mr) < SPIRAL_TOLERANCE for ri in r):
                mid = w[len(w)//2]; ang = math.atan2(mid["y"] - cy, mid["x"] - cx)
                _move(mid, mid["x"] + math.cos(ang) * min(15.0, mr*0.2) * strength, mid["y"] + math.sin(ang) * min(15.0, mr*0.2) * strength)
                mid["modified"] = True; mid["reasons"].append("Спираль сломана"); stats["spirals"] += 1

    if opts["break_repeats"]:
        for i in range(REPEAT_MIN_COUNT * 2, len(objs)):
            p1, p2, p3 = objs[i-2], objs[i-1], objs[i]
            if "spinner" in (p1["kind"], p2["kind"], p3["kind"]): continue
            v1x, v1y, v2x, v2y = p2["x"] - p1["x"], p2["y"] - p1["y"], p3["x"] - p2["x"], p3["y"] - p2["y"]
            d1, d2 = math.hypot(v1x, v1y), math.hypot(v2x, v2y)
            if d1 > 10 and d2 > 10 and (v1x * v2x + v1y * v2y) / (d1 * d2) > 0.95 and abs(d1 - d2) < 5:
                _move(p3, p3["x"] + (v2x / d2) * 5, p3["y"] + (v2y / d2) * 5); p3["modified"] = True; p3["reasons"].append("Повтор паттерна"); stats["repeats"] += 1

    if opts["fix_overlaps"]:
        for i in range(1, len(objs)):
            a, b = objs[i-1], objs[i]
            if a["kind"] == "spinner" or b["kind"] == "spinner": continue
            d = math.hypot(b["x"] - a["ex"], b["y"] - a["ey"])
            if d < 15 and 0 < b["t"] - a["end"] < 20:
                _move(b, b["x"] + 15, b["y"] + 15); b["modified"] = True; b["reasons"].append("Раздвинуто наложение"); stats["overlaps"] += 1

    jit = float(opts["organic_jitter"]) * strength
    if jit > 0.2:
        for i, o in enumerate(objs):
            if o["kind"] == "spinner": continue
            if i > 0 and math.hypot(o["x"] - objs[i - 1]["ex"], o["y"] - objs[i - 1]["ey"]) < 6: continue
            jx, jy = rng.uniform(-jit, jit), rng.uniform(-jit, jit)
            if abs(jx) >= 0.6 or abs(jy) >= 0.6:
                _move(o, o["x"] + jx, o["y"] + jy)
                if not o["modified"]: o["modified"] = True; o["reasons"].append("Jitter")
                stats["jittered"] += 1

    if opts["fix_edges"]:
        for o in objs:
            if o["kind"] == "spinner": continue
            pts = o["pts"] if o["kind"] == "slider" else [(o["x"], o["y"])]
            min_x, max_x, min_y, max_y = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)
            dx = 16 - min_x if min_x < 16 else (496 - max_x if max_x > 496 else 0)
            dy = 16 - min_y if min_y < 16 else (368 - max_y if max_y > 368 else 0)
            if dx or dy: _move(o, o["x"] + dx, o["y"] + dy); o["modified"] = True; o["reasons"].append("Сдвиг от края"); stats["edges"] += 1

    if opts["smart_nc"]:
        chain = 0
        for i, o in enumerate(objs):
            if o["kind"] == "spinner": chain = 0; continue
            old = bool(o["ty"] & 4); want = (i == 0)
            if not want:
                gap = o["t"] - objs[i - 1]["end"]
                if gap >= GAP_NC_MS or (chain >= NC_COMBO_CHAIN and gap >= GAP_NC_MID_MS) or chain >= NC_HARD_LIMIT: want = True
            if want != old:
                o["ty"] = (o["ty"] | 4) if want else (o["ty"] & ~4); stats["nc_fixed"] += 1
                if not o["modified"]: o["modified"] = True; o["reasons"].append("Правка NC")
            chain = 1 if want else chain + 1

    stats["new_ai"] = ai_likeness_score(objs)
    new_lines = [serialize_obj(o) for o in objs]
    out, cur, replaced = [], None, False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]; out.append(line)
            if cur == "HitObjects" and not replaced: out.extend(new_lines); replaced = True
        elif cur == "HitObjects": continue
        else: out.append(line)
    return "\n".join(out), stats, orig, objs
