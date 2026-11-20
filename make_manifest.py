"""Создаёт latest.json для публикации обновления.

Пример:
  python make_manifest.py dist/installer/osu_studio_setup_0.4.0.exe ^
      --version 0.4.0 --url https://github.com/sk1pti/osu_studio/releases/download/v0.4.0/osu_studio_setup_0.4.0.exe ^
      --notes "Фоновая обработка, drag & drop, автообновления"
"""
import argparse
import hashlib
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("installer")
ap.add_argument("--version", required=True)
ap.add_argument("--url", required=True)
ap.add_argument("--notes", default="")
ap.add_argument("--out", default="latest.json")
a = ap.parse_args()

if not a.url.startswith("https://"):
    raise SystemExit("URL должен начинаться с https://")
h = hashlib.sha256()
with open(a.installer, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
manifest = {"version": a.version, "url": a.url, "sha256": h.hexdigest(), "notes": a.notes}
with open(a.out, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"{a.out}: версия {a.version}, sha256 {manifest['sha256'][:16]}… ({os.path.getsize(a.installer)} байт)")
