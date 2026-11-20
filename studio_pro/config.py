# -*- coding: utf-8 -*-
import json
from pathlib import Path

import sys

APP_VERSION = "0.3.0"
UPDATE_MANIFEST_URL = "https://github.com/sk1pti/osu_studio/releases/latest/download/latest.json"

def _code_dir():
    """Папка с ресурсами программы (presets.json). В .exe — рядом с распакованным кодом."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent

def _data_dir():
    """Папка с рабочими данными.

    * Режим разработки (python -m studio_pro): рядом с проектом, как раньше.
    * Установленная программа (.exe): %APPDATA%\\osu_studio — Program Files для записи не подходит.
    * Переопределить можно переменной OSU_STUDIO_HOME.
    """
    import os
    env = os.environ.get("OSU_STUDIO_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "osu_studio"
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = _code_dir()
DATA_ROOT = _data_dir()
D_IN, D_REF, D_WIP = DATA_ROOT / "1_input", DATA_ROOT / "2_references", DATA_ROOT / "3_wip_projects"
D_OUT, D_UTIL = DATA_ROOT / "4_ready_osz", DATA_ROOT / "utils"
D_HISTORY = D_WIP / "_history"
SETTINGS_FILE = D_UTIL / "settings.json"

STREAM_GAP_MS, MICRO_SLIDER_MAX_PX = 135, 18.0
SPIRAL_MIN_PTS, SPIRAL_TOLERANCE, REPEAT_MIN_COUNT = 5, 6.0, 3
FIELD_MARGIN_PX, NC_COMBO_CHAIN, NC_HARD_LIMIT = 16, 6, 12
GAP_NC_MS, GAP_NC_MID_MS = 320, 160

DIFF_PARAMS = {
    "Normal": (3.5, 6.5, 5.0, 4.0), "Hard": (3.8, 8.0, 6.5, 5.0),
    "Light Insane": (3.9, 8.8, 7.5, 5.5), "Insane": (4.0, 9.1, 8.0, 6.0),
    "Extra": (4.0, 9.3, 8.3, 6.0), "Extreme": (4.0, 9.5, 8.5, 6.0),
}
LADDERS = {
    1: ["Insane"], 2: ["Hard", "Insane"], 3: ["Hard", "Insane", "Extra"],
    4: ["Hard", "Light Insane", "Insane", "Extra"],
    5: ["Hard", "Light Insane", "Insane", "Extra", "Extreme"],
    6: ["Normal", "Hard", "Light Insane", "Insane", "Extra", "Extreme"],
}

_DEFAULT_PRESETS = {
    "Desperation": {"mapper": "-1", "cfg": "2.8", "temp": "0.88", "year": "2023", "desc": "jump aim, sharp angles"},
    "Ranked": {"mapper": "-1", "cfg": "2.1", "temp": "0.82", "year": "2023", "desc": "clean, structured, geometric"},
}

def load_presets():
    p = PROJECT_ROOT / "presets.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data: return data
        except (OSError, ValueError): pass
    return dict(_DEFAULT_PRESETS)

PRESETS = load_presets()

def ensure_dirs():
    for d in (D_IN, D_REF, D_WIP, D_OUT, D_UTIL, D_HISTORY):
        d.mkdir(parents=True, exist_ok=True)

def load_settings():
    if SETTINGS_FILE.is_file():
        try: return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError): pass
    return {}

def save_settings(data):
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError: pass
