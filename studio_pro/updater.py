# -*- coding: utf-8 -*-
"""Проверка и установка обновлений.

Манифест (latest.json) на сервере выглядит так:
    {"version": "0.4.0", "url": "https://.../osu_studio_setup_0.4.0.exe",
     "sha256": "<hex>", "notes": "что нового"}

Безопасность: только HTTPS, установщик запускается только после совпадения SHA-256.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse


class UpdateError(Exception):
    pass


def parse_version(v: str) -> tuple:
    v = v.strip().lstrip("vV")
    parts = []
    for chunk in v.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def _require_https(url: str):
    if urlparse(url).scheme != "https":
        raise UpdateError("Обновления разрешены только по HTTPS")


def fetch_manifest(url: str, opener=None) -> dict:
    _require_https(url)
    opener = opener or urllib.request.urlopen
    try:
        with opener(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        raise UpdateError(f"Не удалось получить манифест: {e}") from e
    for key in ("version", "url", "sha256"):
        if not data.get(key):
            raise UpdateError(f"В манифесте нет поля '{key}'")
    _require_https(data["url"])
    return data


def check_for_update(current: str, url: str, opener=None):
    """Возвращает манифест, если есть более новая версия, иначе None."""
    manifest = fetch_manifest(url, opener)
    return manifest if is_newer(manifest["version"], current) else None


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_installer(manifest: dict, dest_dir: str = None, opener=None, progress=None) -> str:
    """Скачивает установщик и проверяет SHA-256. При несовпадении файл удаляется."""
    _require_https(manifest["url"])
    dest_dir = dest_dir or tempfile.gettempdir()
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(urlparse(manifest["url"]).path) or "osu_studio_setup.exe")
    opener = opener or urllib.request.urlopen
    try:
        with opener(manifest["url"], timeout=60) as resp, open(dest, "wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                if progress:
                    progress(out.tell())
    except OSError as e:
        raise UpdateError(f"Ошибка загрузки: {e}") from e
    actual = sha256_of(dest)
    if actual.lower() != manifest["sha256"].lower():
        os.remove(dest)
        raise UpdateError("Контрольная сумма не совпала — файл повреждён или подменён. Установка отменена.")
    return dest


def launch_installer(path: str):
    """Запускает установщик без лишних окон. Работает только в Windows."""
    if sys.platform != "win32":
        raise UpdateError("Автоустановка доступна только в Windows")
    subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES"], close_fds=True)
