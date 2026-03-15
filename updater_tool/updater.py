#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path


def remove_dir_safe(path: Path, retries=10, delay=0.6):
    for _ in range(retries):
        try:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
            return
        except Exception:
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--app-exe", required=True)
    args = parser.parse_args()

    zip_path = Path(args.zip)
    app_dir = Path(args.app_dir)
    app_exe = Path(args.app_exe)

    if not zip_path.exists():
        sys.exit(1)

    # dá tempo do app principal fechar
    time.sleep(2.5)

    temp_extract = Path(tempfile.gettempdir()) / "vivo_fiscal_suite_extract"
    remove_dir_safe(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_extract)

    # espera que o zip tenha a estrutura:
    # package/
    #   main.exe
    #   access.py...
    #   assets/...
    package_dir = temp_extract / "package"
    if not package_dir.exists():
        package_dir = temp_extract

    backup_dir = app_dir.parent / f"{app_dir.name}_backup"

    remove_dir_safe(backup_dir)

    try:
        if app_dir.exists():
            app_dir.rename(backup_dir)

        shutil.copytree(package_dir, app_dir)

        remove_dir_safe(backup_dir)

    except Exception:
        if app_dir.exists():
            remove_dir_safe(app_dir)
        if backup_dir.exists():
            backup_dir.rename(app_dir)
        sys.exit(2)

    # reabre o app
    subprocess.Popen([str(app_exe)], cwd=str(app_dir))
    sys.exit(0)


if __name__ == "__main__":
    main()