# -*- coding: utf-8 -*-
import os, zipfile
from pathlib import Path
from .io import read_text, write_text, safe_name, set_val, set_background, get_val, map_section, set_colours
from .parser import shift_hit, shift_timing, shift_event

def apply_tune(text, params, offset_ms, hitsounds=False, colours=False):
    for short, full in (("CS", "CircleSize"), ("AR", "ApproachRate"), ("OD", "OverallDifficulty"), ("HP", "HPDrainRate")):
        if short in params: text = set_val(text, full, "%g" % params[short], "Difficulty")
    if offset_ms:
        text = map_section(text, "HitObjects", lambda l: shift_hit(l, offset_ms))
        text = map_section(text, "TimingPoints", lambda l: shift_timing(l, offset_ms))
        text = map_section(text, "Events", lambda l: shift_event(l, offset_ms))
    if hitsounds:
        def add_hs(l):
            p = l.split(",")
            if len(p) > 4 and (int(p[3]) & 1 or int(p[3]) & 2):
                p[4] = "2"
            return ",".join(p)
        text = map_section(text, "HitObjects", add_hs)
    if colours: text = set_colours(text)
    return text

def tune_file(path, params, offset_ms, dest_dir, hitsounds=False, colours=False):
    text = apply_tune(read_text(path), params, offset_ms, hitsounds, colours)
    dest = Path(dest_dir) / (Path(path).stem + "_tuned.osu")
    write_text(dest, text)
    return dest

def build_osz(files, audio, bg, name, auto, dp, lad, out_dir):
    if not files or not Path(audio).is_file(): raise ValueError("Нет файлов или аудио")
    name = safe_name(name)
    if auto and len(files) not in lad:
        raise ValueError("Авто-лестница поддерживает от 1 до %d дифов, а выбрано %d. "
                         "Отключи авто-лестницу или уменьши количество." % (max(lad), len(files)))
    names = lad.get(len(files)) if auto else None
    out_path = Path(out_dir) / (name + ".osz")
    used = set()
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(audio, os.path.basename(audio))
        if bg and Path(bg).is_file(): z.write(bg, os.path.basename(bg))
        for i, p in enumerate(files):
            t = read_text(p); t = set_val(t, "AudioFilename", os.path.basename(audio), "General", " ")
            if bg: t = set_background(t, os.path.basename(bg))
            if names:
                ver = names[i]; cs, ar, od, hp = dp[ver]
                t = set_val(t, "Version", ver, "Metadata")
                t = set_val(t, "CircleSize", cs, "Difficulty"); t = set_val(t, "ApproachRate", ar, "Difficulty")
                t = set_val(t, "OverallDifficulty", od, "Difficulty"); t = set_val(t, "HPDrainRate", hp, "Difficulty")
            ver = get_val(t, "Version") or "Diff%d" % (i + 1)
            if ver in used: ver = "%s %d" % (ver, i + 1); t = set_val(t, "Version", ver, "Metadata")
            used.add(ver)
            z.writestr(safe_name("%s - %s (%s) [%s].osu" % (get_val(t, "Artist"), get_val(t, "Title"), get_val(t, "Creator"), ver)), t.replace("\n", "\r\n").encode("utf-8"))
    return out_path

def extract_reference(osz_path, dest_dir, selected_name=None):
    with zipfile.ZipFile(osz_path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".osu")]
        if not names:
            raise ValueError("В архиве нет .osu файлов")
        pick = selected_name or names[0]
        if pick not in names:
            raise ValueError("Файл не найден в архиве: %s" % pick)
        data = z.read(pick)
    dest = Path(dest_dir) / safe_name(os.path.basename(pick))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest, names
