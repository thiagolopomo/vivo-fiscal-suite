#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from update_service import get_base_dir, get_updater_exe_path


def iniciar_instalacao_update(zip_path: Path, parent=None):
    updater_exe = get_updater_exe_path()
    base_dir = get_base_dir()

    if not updater_exe.exists():
        raise FileNotFoundError(
            f"Updater não encontrado em:\n{updater_exe}\n\n"
            "Coloque o updater.exe em assets/updates/"
        )

    app_exe = base_dir / "main.exe"
    if not app_exe.exists():
        # durante teste em .py
        app_exe = Path(sys.executable).resolve()

    subprocess.Popen([
        str(updater_exe),
        "--zip", str(zip_path),
        "--app-dir", str(base_dir),
        "--app-exe", str(app_exe),
    ])

    QMessageBox.information(
        parent,
        "Atualização",
        "A atualização será instalada agora.\n\n"
        "O aplicativo será fechado e reaberto automaticamente."
    )