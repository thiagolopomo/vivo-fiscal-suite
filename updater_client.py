#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
import tempfile
import time
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
    ready_file = temp_dir / "updater_ready.flag"

    if ready_file.exists():
        ready_file.unlink()

    shutil.copy2(updater_exe, temp_updater)

    args_str = (
        f'--source-dir "{extracted_dir}" '
        f'--app-dir "{base_dir}" '
        f'--app-exe "{app_exe}" '
        f'--wait-pid {os.getpid()} '
        f'--ready-file "{ready_file}"'
    )

    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", str(temp_updater), args_str, str(temp_dir), 1
        )
    else:
        subprocess.Popen(
            [
                str(temp_updater),
                "--source-dir", str(extracted_dir),
                "--app-dir", str(base_dir),
                "--app-exe", str(app_exe),
                "--wait-pid", str(os.getpid()),
                "--ready-file", str(ready_file),
            ],
            cwd=str(temp_dir),
            shell=False
        )

    # Espera real: só retorna quando o updater sinalizar que já abriu e assumiu a UX
    start = time.time()
    while time.time() - start < 15:
        if ready_file.exists():
            return
        time.sleep(0.05)

    raise RuntimeError("O instalador da atualização não sinalizou inicialização a tempo.")