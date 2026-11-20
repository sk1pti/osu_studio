# -*- coding: utf-8 -*-
import math
from .io import get_val
from .parser import parse_osu, fmt_t

def lint_osu(text, max_len=400.0):
    res, counts = [], {}
    def add(cat, level, msg):
        counts[cat] = counts.get(cat, 0) + 1
        if counts[cat] <= 10: res.append("[%s] %s" % (level, msg))
        elif counts[cat] == 11: res.append("[%s] ...и еще в '%s'" % (level, cat))

    info = parse_osu(text); objs = info["objs"]
    if not objs: add("Объекты", "ОШИБКА", "Нет хит-объектов"); return res

    # 1. Тайминг-сетка
    tps = sorted(info["tp"], key=lambda x: x[0])
    if tps:
        beat = tps[0][1]
        if beat > 0:
            off_grid = 0
            for o in objs:
                if o["kind"] == "spinner": continue
                mod = (o["t"] - tps[0][0]) % beat
                if mod > 2 and mod < beat - 2: off_grid += 1
            if off_grid > len(objs) * 0.3:
                add("Тайминг", "ВНИМАНИЕ", "Много нот (%d) вне основной сетки BPM" % off_grid)

    # 2. Наложения
    for i in range(1, len(objs)):
        a, b = objs[i-1], objs[i]
        if a["kind"] == "spinner" or b["kind"] == "spinner": continue
        d = math.hypot(b["x"] - a["ex"], b["y"] - a["ey"])
        if d < 15 and 0 < b["t"] - a["end"] < 20:
            add("Наложение", "ВНИМАНИЕ", "%s - объект слишком близко к предыдущему" % fmt_t(b["t"]))

    # 3. Объекты за пределами игрового поля (512x384)
    out_of_field = 0
    for o in objs:
        pts = o["pts"] if o["kind"] == "slider" else [(o["x"], o["y"])]
        if any(not (0 <= px <= 512 and 0 <= py <= 384) for px, py in pts):
            out_of_field += 1
    if out_of_field:
        add("Поле", "ОШИБКА", "%d объектов выходят за пределы playfield 512x384" % out_of_field)

    # 4. Первый объект обязан начинать новое комбо
    if not (objs[0]["ty"] & 4):
        add("NC", "ВНИМАНИЕ", "Первый объект карты не начинает новое комбо (New Combo)")

    # 5. Слишком близкие по времени объекты (меньше 40 мс)
    fast = sum(1 for a, b in zip(objs, objs[1:]) if 0 <= b["t"] - a["end"] < 40 and a["kind"] != "spinner")
    if fast:
        add("Тайминг", "ВНИМАНИЕ", "%d пар объектов идут ближе 40 мс друг к другу" % fast)

    # 6. Базовые проверки
    for key in ("Title", "Artist", "Creator", "Version"):
        if not get_val(text, key): add("Метаданные", "ВНИМАНИЕ", "Пустое поле %s" % key)
    return res

def num(text, key):
    try: return float(get_val(text, key))
    except ValueError: return 0.0

def map_metrics(text):
    objs = parse_osu(text)["objs"]
    d = {"ver": get_val(text, "Version") or "?", "cs": num(text, "CircleSize"), "ar": num(text, "ApproachRate"),
         "od": num(text, "OverallDifficulty"), "hp": num(text, "HPDrainRate"), "n": len(objs), "index": 0.0}
    if len(objs) > 2:
        ds = [math.hypot(b["x"] - a["ex"], b["y"] - a["ey"]) for a, b in zip(objs, objs[1:]) if a["kind"] != "spinner" and b["kind"] != "spinner"]
        span = max(1.0, (objs[-1]["end"] - objs[0]["t"]) / 1000.0)
        avg = sum(ds) / len(ds) if ds else 0.0
        d["index"] = round(len(objs) / span * (1 + avg / 100.0), 2)
    return d
