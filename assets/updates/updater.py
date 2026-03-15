#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path


RENAME_RETRIES = 40
RENAME_DELAY = 0.5
REMOVE_RETRIES = 20
REMOVE_DELAY = 0.8
REOPEN_RETRIES = 6
REOPEN_DELAY = 1.0
WAIT_PID_TIMEOUT = 60.0
WAIT_PID_DELAY = 0.5


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


def wait_for_pid_exit(pid: int, base_log: Path, timeout=WAIT_PID_TIMEOUT, delay=WAIT_PID_DELAY) -> bool:
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


def remove_dir_safe(path: Path, base_log: Path, retries=REMOVE_RETRIES, delay=REMOVE_DELAY) -> bool:
    for i in range(1, retries + 1):
        try:
            if path.exists():
                shutil.rmtree(path)
            write_log(base_log, f"[REMOVE DIR OK] {path}")
            return True
        except Exception as e:
            write_log(base_log, f"[REMOVE DIR RETRY {i}/{retries}] {path} -> {repr(e)}")
            time.sleep(delay)
    return not path.exists()


def remove_file_safe(path: Path, base_log: Path, retries=REMOVE_RETRIES, delay=REMOVE_DELAY) -> bool:
    for i in range(1, retries + 1):
        try:
            if path.exists():
                path.unlink()
            write_log(base_log, f"[REMOVE FILE OK] {path}")
            return True
        except Exception as e:
            write_log(base_log, f"[REMOVE FILE RETRY {i}/{retries}] {path} -> {repr(e)}")
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


def copy_tree_with_retry(src: Path, dst: Path, base_log: Path, retries=10, delay=0.8) -> bool:
    for i in range(1, retries + 1):
        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            write_log(base_log, f"[COPY OK] {src} -> {dst}")
            return True
        except Exception as e:
            write_log(base_log, f"[COPY RETRY {i}/{retries}] {src} -> {dst} -> {repr(e)}")
            time.sleep(delay)
    return False


def relaunch_app(app_exe: Path, app_dir: Path, base_log: Path) -> bool:
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )

    for i in range(1, REOPEN_RETRIES + 1):
        try:
            subprocess.Popen(
                [str(app_exe)],
                cwd=str(app_dir),
                shell=False,
                creationflags=creationflags
            )
            write_log(base_log, f"[REOPEN OK] subprocess.Popen -> {app_exe}")
            return True
        except Exception as e:
            write_log(base_log, f"[REOPEN RETRY {i}/{REOPEN_RETRIES}] Popen -> {repr(e)}")
            time.sleep(REOPEN_DELAY)

    for i in range(1, REOPEN_RETRIES + 1):
        try:
            os.startfile(str(app_exe))
            write_log(base_log, f"[REOPEN OK] os.startfile -> {app_exe}")
            return True
        except Exception as e:
            write_log(base_log, f"[REOPEN RETRY {i}/{REOPEN_RETRIES}] startfile -> {repr(e)}")
            time.sleep(REOPEN_DELAY)

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--app-exe", required=True)
    parser.add_argument("--wait-pid", type=int, default=0)
    args = parser.parse_args()

    zip_path = Path(args.zip).resolve()
    app_dir = Path(args.app_dir).resolve()
    exe_name = Path(args.app_exe).name or "main.exe"
    wait_pid = int(args.wait_pid or 0)

    base_log = app_dir.parent
    backup_dir = app_dir.parent / f"{app_dir.name}_backup"
    temp_root = Path(tempfile.gettempdir()) / f"vivo_fiscal_suite_extract_{os.getpid()}"

    write_log(base_log, "\n===== NOVA EXECUÇÃO DO UPDATER =====")
    write_log(base_log, f"[START] zip={zip_path}")
    write_log(base_log, f"[START] app_dir={app_dir}")
    write_log(base_log, f"[START] exe_name={exe_name}")
    write_log(base_log, f"[START] wait_pid={wait_pid}")

    if not zip_path.exists():
        write_log(base_log, "[FATAL] ZIP não encontrado")
        sys.exit(1)

    try:
        if wait_pid > 0:
            if not wait_for_pid_exit(wait_pid, base_log):
                write_log(base_log, f"[FATAL] PID {wait_pid} não encerrou no tempo esperado")
                sys.exit(11)

        if temp_root.exists():
            remove_dir_safe(temp_root, base_log)
        temp_root.mkdir(parents=True, exist_ok=True)

        write_log(base_log, "[EXTRACT] extraindo pacote...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_root)

        package_dir = temp_root / "package"
        if not package_dir.exists():
            package_dir = temp_root

        write_log(base_log, f"[EXTRACT OK] package_dir={package_dir}")

        if backup_dir.exists():
            write_log(base_log, f"[CLEAN] removendo backup antigo: {backup_dir}")
            if not remove_dir_safe(backup_dir, base_log):
                write_log(base_log, "[FATAL] não foi possível remover backup antigo")
                sys.exit(2)

        if not app_dir.exists():
            write_log(base_log, "[WARN] app_dir não existia; copiando nova versão direto")
            if not copy_tree_with_retry(package_dir, app_dir, base_log):
                write_log(base_log, "[FATAL] falha ao copiar nova versão para pasta inexistente")
                sys.exit(3)
        else:
            write_log(base_log, "[MOVE] tentando mover pasta atual para backup...")
            if not rename_dir_with_retry(app_dir, backup_dir, base_log):
                write_log(base_log, "[FATAL] não foi possível mover a pasta atual para backup")
                sys.exit(4)

            write_log(base_log, f"[COPY] copiando nova versão: {package_dir} -> {app_dir}")
            if not copy_tree_with_retry(package_dir, app_dir, base_log):
                write_log(base_log, "[ERROR] falha ao copiar nova versão; iniciando rollback")
                if app_dir.exists():
                    remove_dir_safe(app_dir, base_log)
                if backup_dir.exists():
                    if not rename_dir_with_retry(backup_dir, app_dir, base_log):
                        write_log(base_log, "[FATAL] rollback falhou")
                        sys.exit(5)
                sys.exit(6)

        new_app_exe = app_dir / exe_name
        write_log(base_log, f"[CHECK] new_app_exe={new_app_exe}")
        write_log(base_log, f"[CHECK] exists={new_app_exe.exists()}")

        if not new_app_exe.exists():
            write_log(base_log, "[ERROR] main.exe não encontrado após cópia; iniciando rollback")
            if app_dir.exists():
                remove_dir_safe(app_dir, base_log)
            if backup_dir.exists():
                if not rename_dir_with_retry(backup_dir, app_dir, base_log):
                    write_log(base_log, "[FATAL] rollback falhou")
                    sys.exit(7)
            sys.exit(8)

        if backup_dir.exists():
            write_log(base_log, f"[CLEAN] removendo backup final: {backup_dir}")
            remove_dir_safe(backup_dir, base_log)

        time.sleep(1.0)

        if not relaunch_app(new_app_exe, app_dir, base_log):
            write_log(base_log, "[FATAL] não foi possível reabrir o app")
            sys.exit(9)

    except Exception as e:
        write_log(base_log, f"[UNHANDLED ERROR] {repr(e)}")
        try:
            if app_dir.exists() and backup_dir.exists():
                remove_dir_safe(app_dir, base_log)
                rename_dir_with_retry(backup_dir, app_dir, base_log)
                write_log(base_log, "[ROLLBACK] backup restaurado")
            elif (not app_dir.exists()) and backup_dir.exists():
                rename_dir_with_retry(backup_dir, app_dir, base_log)
                write_log(base_log, "[ROLLBACK] backup restaurado")
        except Exception as restore_err:
            write_log(base_log, f"[ROLLBACK ERROR] {repr(restore_err)}")
        sys.exit(10)

    finally:
        remove_dir_safe(temp_root, base_log)
        remove_file_safe(zip_path, base_log)

    sys.exit(0)


if __name__ == "__main__":
    main()