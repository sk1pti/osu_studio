# -*- coding: utf-8 -*-
import hashlib
import io
import json

import pytest

from studio_pro import updater as U


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(payload: bytes):
    return lambda url, timeout=None: FakeResp(payload)


def test_versions_compare():
    assert U.is_newer("0.4.0", "0.3.0")
    assert U.is_newer("1.0", "0.9.9")
    assert not U.is_newer("0.3.0", "0.3.0")
    assert not U.is_newer("0.2.9", "0.3.0")
    assert U.parse_version("v0.10.1") == (0, 10, 1)


def test_manifest_requires_https():
    with pytest.raises(U.UpdateError):
        U.fetch_manifest("http://example.com/latest.json", opener_for(b"{}"))


def test_manifest_missing_fields_rejected():
    body = json.dumps({"version": "9.9.9"}).encode()
    with pytest.raises(U.UpdateError):
        U.fetch_manifest("https://example.com/latest.json", opener_for(body))


def test_check_for_update_returns_manifest_only_when_newer():
    m = {"version": "0.4.0", "url": "https://example.com/s.exe", "sha256": "ab"}
    body = json.dumps(m).encode()
    assert U.check_for_update("0.3.0", "https://example.com/latest.json", opener_for(body)) == m
    assert U.check_for_update("0.4.0", "https://example.com/latest.json", opener_for(body)) is None


def test_download_verifies_sha256(tmp_path):
    payload = b"fake installer bytes"
    good = hashlib.sha256(payload).hexdigest()
    m = {"version": "0.4.0", "url": "https://example.com/osu_studio_setup_0.4.0.exe", "sha256": good}
    path = U.download_installer(m, str(tmp_path), opener=opener_for(payload))
    assert open(path, "rb").read() == payload


def test_download_rejects_bad_hash_and_deletes_file(tmp_path):
    m = {"version": "0.4.0", "url": "https://example.com/setup.exe", "sha256": "0" * 64}
    with pytest.raises(U.UpdateError):
        U.download_installer(m, str(tmp_path), opener=opener_for(b"tampered"))
    assert not (tmp_path / "setup.exe").exists()


def test_download_refuses_http(tmp_path):
    m = {"version": "0.4.0", "url": "http://example.com/setup.exe", "sha256": "x"}
    with pytest.raises(U.UpdateError):
        U.download_installer(m, str(tmp_path), opener=opener_for(b""))


def test_launch_refused_outside_windows(monkeypatch):
    monkeypatch.setattr(U.sys, "platform", "linux")
    with pytest.raises(U.UpdateError):
        U.launch_installer("/tmp/setup.exe")
