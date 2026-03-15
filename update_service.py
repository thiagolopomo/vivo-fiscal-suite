#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import sys
import tempfile
from pathlib import Path

import requests

from app_info import APP_VERSION, UPDATE_MANIFEST_URL


def parse_version(version_str: str):
    try:
        return tuple(int(x) for x in version_str.strip().split("."))
    except Exception:
        return (0, 0, 0)


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_updates_dir() -> Path:
    p = get_base_dir() / "assets" / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def check_for_update(timeout=10):
    result = {
        "update_available": False,
        "current_version": APP_VERSION,
        "remote_version": None,
        "mandatory": False,
        "notes": "",
        "url": "",
        "sha256": "",
        "error": None,
    }

    try:
        resp = requests.get(UPDATE_MANIFEST_URL, timeout=timeout)
        resp.raise_for_status()
        manifest = resp.json()

        remote_version = str(manifest.get("version", "")).strip()
        mandatory = bool(manifest.get("mandatory", False))
        notes = str(manifest.get("notes", "") or "")
        url = str(manifest.get("url", "") or "")
        sha256 = str(manifest.get("sha256", "") or "")

        result["remote_version"] = remote_version
        result["mandatory"] = mandatory
        result["notes"] = notes
        result["url"] = url
        result["sha256"] = sha256

        if remote_version and parse_version(remote_version) > parse_version(APP_VERSION):
            result["update_available"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_update_package(url: str, expected_sha256: str = "", progress_callback=None) -> Path:
    """
    Baixa o zip da atualização para %TEMP% e retorna o caminho do arquivo.
    progress_callback(recebido_bytes, total_bytes)
    """
    tmp_dir = Path(tempfile.gettempdir()) / "vivo_fiscal_suite_updates"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    zip_path = tmp_dir / "update_package.zip"

    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()

        total = int(r.headers.get("Content-Length", "0") or 0)
        recebido = 0

        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                recebido += len(chunk)

                if progress_callback:
                    progress_callback(recebido, total)

    if expected_sha256:
        real_hash = sha256_file(zip_path)
        if real_hash.lower() != expected_sha256.lower():
            raise RuntimeError("O arquivo da atualização falhou na validação de integridade (SHA-256).")

    return zip_path


def get_updater_exe_path() -> Path:
    return get_updates_dir() / "updater.exe"