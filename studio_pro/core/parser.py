# -*- coding: utf-8 -*-
from .io import get_val

def make_obj(p):
    x, y, t, ty = int(float(p[0])), int(float(p[1])), int(float(p[2])), int(float(p[3]))
    o = {"x": x, "y": y, "t": t, "ty": ty, "kind": "circle", "ex": x, "ey": y, "end": t, "len": 0.0, "slides": 1, "pts": [(x, y)], "raw": list(p), "modified": False, "reasons": []}
    if ty & 2:
        o["kind"] = "slider"; pts = [(x, y)]; parts = p[5].split("|")
        o["curve_type"] = parts[0] if parts else "L"
        for c in parts[1:]:
            if ":" in c: a, b = c.split(":"); pts.append((int(float(a)), int(float(b))))
        o["pts"], o["slides"], o["len"] = pts, int(p[6]), float(p[7])
        o["ex"], o["ey"] = pts[-1] if o["slides"] % 2 == 1 else pts[0]
    elif ty & 8: o["kind"] = "spinner"; o["end"] = int(float(p[5]))
    return o

def serialize_obj(o):
    p = list(o["raw"]); p[0], p[1], p[2], p[3] = str(int(round(o["x"]))), str(int(round(o["y"]))), str(int(o["t"])), str(int(o["ty"]))
    if o["kind"] == "slider" and len(p) >= 8:
        ctype = o.get("curve_type") or (p[5].split("|")[0] if len(p) > 5 else "L")
        ctrl = ["%d:%d" % (int(round(px)), int(round(py))) for px, py in o["pts"][1:]]
        p[5] = ctype + ("|" + "|".join(ctrl) if ctrl else ""); p[6] = str(o["slides"]); p[7] = ("%.2f" % o["len"]).rstrip("0").rstrip(".")
    elif o["kind"] == "circle" and (int(o["raw"][3]) & 2):
        p = [p[0], p[1], p[2], p[3], o["raw"][4] if len(o["raw"]) > 4 else "0", o["raw"][10] if len(o["raw"]) > 10 else "0:0:0:0:"]
    return ",".join(p)

def parse_osu(text):
    info = {"sm": 1.4, "tp": [], "objs": [], "breaks": []}
    try: info["sm"] = float(get_val(text, "SliderMultiplier"))
    except ValueError: pass
    cur = None
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"): cur = s[1:-1]; continue
        if not s or s.startswith("//"): continue
        p = s.split(",")
        try:
            if cur == "TimingPoints" and len(p) >= 2:
                bl = float(p[1]); unin = (p[6].strip() == "1") if len(p) > 6 else bl > 0
                info["tp"].append((float(p[0]), bl, unin))
            elif cur == "Events" and p[0] == "2": info["breaks"].append((int(p[1]), int(p[2])))
            elif cur == "HitObjects" and len(p) >= 4: info["objs"].append(make_obj(p))
        except (ValueError, IndexError): continue
    tps = sorted(info["tp"], key=lambda x: x[0])
    for o in info["objs"]:
        if o["kind"] != "slider": continue
        beat, sv = 500.0, 1.0
        for t, bl, unin in tps:
            if t > o["t"]: break
            if unin and bl > 0: beat, sv = bl, 1.0
            elif bl < 0: sv = min(10.0, max(0.1, -100.0 / bl))
        o["end"] = int(o["t"] + o["len"] / (info["sm"] * 100 * sv) * beat * o["slides"])
    return info

def fmt_t(ms): return "%02d:%02d:%03d" % (int(ms) // 60000, (int(ms) // 1000) % 60, int(ms) % 1000)
def shift_hit(line, off):
    p = line.split(",")
    try:
        if len(p) >= 4 and p[2].lstrip("-").isdigit():
            p[2] = str(int(p[2]) + off)
            if p[3].isdigit() and (int(p[3]) & 8) and len(p) > 5 and p[5].lstrip("-").isdigit(): p[5] = str(int(p[5]) + off)
    except ValueError: pass
    return ",".join(p)
def shift_timing(line, off):
    p = line.split(",")
    try: p[0] = str(int(round(float(p[0]))) + off)
    except ValueError: pass
    return ",".join(p)
def shift_event(line, off):
    p = line.split(",")
    try:
        if p[0] == "2" and len(p) >= 3: p[1], p[2] = str(int(p[1]) + off), str(int(p[2]) + off)
    except ValueError: pass
    return ",".join(p)
