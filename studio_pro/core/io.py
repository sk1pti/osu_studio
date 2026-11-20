# -*- coding: utf-8 -*-
import logging, os, re, shutil, datetime
from ..config import D_HISTORY

log = logging.getLogger(__name__)

def safe_name(s): return re.sub(r'[\\/:*?"<>|]', "", str(s)).strip()

def read_text(path):
    with open(path, "rb") as f: data = f.read()
    for enc in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try: return data.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError: continue
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")

def write_text(path, text, backup=True):
    if backup and os.path.exists(path):
        try:
            D_HISTORY.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(path, D_HISTORY / f"{ts}_{os.path.basename(path)}")
        except OSError: pass
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", "\r\n"))

def get_val(text, key):
    m = re.search(r"^" + re.escape(key) + r"\s*:\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else ""

def set_val(text, key, value, section, sep=""):
    line = "%s:%s%s" % (key, sep, value)
    pat = re.compile(r"^" + re.escape(key) + r"\s*:.*$", re.M)
    if pat.search(text): return pat.sub(lambda m: line, text, count=1)
    pat_sec = re.compile(r"(^\[" + re.escape(section) + r"\]\n)", re.M)
    if not pat_sec.search(text): return text
    return pat_sec.sub(lambda m: m.group(1) + line + "\n", text, count=1)

def map_section(text, section, fn):
    out, cur = [], None
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]; out.append(line)
        elif cur == section and s and not s.startswith("//"): out.append(fn(line))
        else: out.append(line)
    return "\n".join(out)

def set_background(text, bg_name):
    out, in_ev, inserted = [], False, False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_ev = (s == "[Events]"); out.append(line); continue
        if in_ev and re.match(r'^(0|Background),0,', s): continue
        out.append(line)
        if in_ev and not inserted and s.startswith("//Background"):
            out.append('0,0,"%s",0,0' % bg_name); inserted = True
    res = "\n".join(out)
    if not inserted:
        res = re.sub(r"(^\[Events\]\n)", lambda m: m.group(1) + '//Background\n0,0,"%s",0,0\n' % bg_name, res, count=1, flags=re.M)
    return res

def set_colours(text):
    colours = "[Colours]\nCombo1 : 255,102,170\nCombo2 : 68,170,221\nCombo3 : 102,204,102\nCombo4 : 255,170,68\n\n"
    if "[Colours]" in text: return re.sub(r"\[Colours\].*?(?=\n\[|\Z)", colours, text, flags=re.S)
    return text + "\n" + colours
