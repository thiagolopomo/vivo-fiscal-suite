#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from update_service import get_base_dir, get_updater_exe_path


def iniciar_instalacao_update(extracted_dir: Path, parent=None):
    updater_exe = get_updater_exe_path()
    base_dir = get_base_dir()

    if not updater_exe.exists():
        raise FileNotFoundError(
            f"Updater não encontrado em:\n{updater_exe}\n\n"
            "Coloque o updater.exe em assets/updates/"
        )

    app_exe = base_dir / "main.exe"
    if not app_exe.exists():
        app_exe = Path(sys.executable).resolve()

    extracted_dir = Path(extracted_dir).resolve()

    temp_dir = Path(tempfile.gettempdir()) / "vivo_fiscal_suite_updater"
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_updater = temp_dir / "updater.exe"
    shutil.copy2(updater_exe, temp_updater)

    subprocess.Popen(
        [
            str(temp_updater),
            "--source-dir", str(extracted_dir),
            "--app-dir", str(base_dir),
            "--app-exe", str(app_exe),
            "--wait-pid", str(os.getpid()),
        ],
        cwd=str(temp_dir),
        shell=False
    )