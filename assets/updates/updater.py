#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


RENAME_RETRIES = 40
RENAME_DELAY = 0.5
REMOVE_RETRIES = 20
REMOVE_DELAY = 0.8


def write_log(base: Path, msg: str):
    try:
        log_file = base / "updater_log.txt"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            output = (result.stdout or "") + (result.stderr or "")
            return str(pid) in output and "No tasks are running" not in output
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def wait_for_pid_exit(pid: int, base_log: Path, timeout=60.0, delay=0.5) -> bool:
    if pid <= 0:
        return True

    start = time.time()
    while time.time() - start < timeout:
        if not pid_exists(pid):
            write_log(base_log, f"[WAIT PID OK] PID {pid} encerrado")
            return True
        write_log(base_log, f"[WAIT PID] aguardando PID {pid} encerrar...")
        time.sleep(delay)

    return not pid_exists(pid)


def remove_dir_with_retry(path: Path, base_log: Path, retries=REMOVE_RETRIES, delay=REMOVE_DELAY) -> bool:
    for i in range(1, retries + 1):
        try:
            if path.exists():
                shutil.rmtree(path)
            write_log(base_log, f"[REMOVE OK] {path}")
            return True
        except Exception as e:
            write_log(base_log, f"[REMOVE RETRY {i}/{retries}] {path} -> {repr(e)}")
            time.sleep(delay)
    return not path.exists()


def rename_dir_with_retry(src: Path, dst: Path, base_log: Path, retries=RENAME_RETRIES, delay=RENAME_DELAY) -> bool:
    for i in range(1, retries + 1):
        try:
            if dst.exists():
                shutil.rmtree(dst)
            src.rename(dst)
            write_log(base_log, f"[RENAME OK] {src} -> {dst}")
            return True
        except Exception as e:
            write_log(base_log, f"[RENAME RETRY {i}/{retries}] {src} -> {dst} -> {repr(e)}")
            time.sleep(delay)
    return False


def relaunch_app(app_exe: Path, app_dir: Path, base_log: Path) -> bool:
    try:
        subprocess.Popen([str(app_exe)], cwd=str(app_dir), shell=False)
        write_log(base_log, f"[REOPEN OK] {app_exe}")
        return True
    except Exception as e:
        write_log(base_log, f"[REOPEN ERROR] {repr(e)}")
        return False


def rollback(app_dir: Path, backup_dir: Path, base_log: Path):
    write_log(base_log, "[ROLLBACK] iniciando restauração")

    if app_dir.exists():
        remove_dir_with_retry(app_dir, base_log)

    if backup_dir.exists():
        if rename_dir_with_retry(backup_dir, app_dir, base_log):
            write_log(base_log, "[ROLLBACK OK] backup restaurado")
        else:
            write_log(base_log, "[ROLLBACK ERROR] falha ao restaurar backup")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--app-exe", required=True)
    parser.add_argument("--wait-pid", type=int, default=0)
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    app_dir = Path(args.app_dir).resolve()
    exe_name = Path(args.app_exe).name or "main.exe"
    wait_pid = int(args.wait_pid or 0)

    base_log = app_dir.parent
    backup_dir = app_dir.parent / f"{app_dir.name}_backup"

    write_log(base_log, "\n===== NOVA EXECUÇÃO DO UPDATER =====")
    write_log(base_log, f"[START] source_dir={source_dir}")
    write_log(base_log, f"[START] app_dir={app_dir}")
    write_log(base_log, f"[START] exe_name={exe_name}")
    write_log(base_log, f"[START] wait_pid={wait_pid}")

    if not source_dir.exists():
        write_log(base_log, "[FATAL] source_dir não encontrado")
        sys.exit(1)

    if wait_pid > 0:
        if not wait_for_pid_exit(wait_pid, base_log):
            write_log(base_log, f"[FATAL] PID {wait_pid} não encerrou")
            sys.exit(2)

    if backup_dir.exists():
        if not remove_dir_with_retry(backup_dir, base_log):
            write_log(base_log, "[FATAL] não foi possível remover backup anterior")
            sys.exit(3)

    if not rename_dir_with_retry(app_dir, backup_dir, base_log):
        write_log(base_log, "[FATAL] não foi possível mover a pasta atual")
        sys.exit(4)

    try:
        shutil.copytree(source_dir, app_dir)
        write_log(base_log, f"[COPY OK] {source_dir} -> {app_dir}")
    except Exception as e:
        write_log(base_log, f"[COPY ERROR] {repr(e)}")
        rollback(app_dir, backup_dir, base_log)
        sys.exit(5)

    new_app_exe = app_dir / exe_name
    if not new_app_exe.exists():
        write_log(base_log, "[FATAL] main.exe não encontrado após cópia")
        rollback(app_dir, backup_dir, base_log)
        sys.exit(6)

    if backup_dir.exists():
        remove_dir_with_retry(backup_dir, base_log)
        write_log(base_log, f"[CLEAN OK] {backup_dir}")

    if not relaunch_app(new_app_exe, app_dir, base_log):
        sys.exit(7)

    if source_dir.exists():
        remove_dir_with_retry(source_dir, base_log)

    sys.exit(0)


if __name__ == "__main__":
    main()