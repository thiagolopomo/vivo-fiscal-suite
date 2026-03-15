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


def remove_dir_safe(path: Path, retries=10, delay=0.8):
    for _ in range(retries):
        try:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
            return True
        except Exception:
            time.sleep(delay)
    return not path.exists()


def rename_dir_safe(src: Path, dst: Path, retries=10, delay=0.8):
    for _ in range(retries):
        try:
            if src.exists():
                src.rename(dst)
            return True
        except Exception:
            time.sleep(delay)
    return False


def copytree_safe(src: Path, dst: Path, retries=10, delay=0.8):
    for _ in range(retries):
        try:
            shutil.copytree(src, dst)
            return True
        except Exception:
            time.sleep(delay)
    return False


def write_log(msg: str):
    try:
        log_path = Path(tempfile.gettempdir()) / "vivo_updater_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--app-exe", required=True)
    args = parser.parse_args()

    zip_path = Path(args.zip)
    app_dir = Path(args.app_dir)
    app_exe = Path(args.app_exe)

    write_log(f"ZIP: {zip_path}")
    write_log(f"APP_DIR: {app_dir}")
    write_log(f"APP_EXE recebido: {app_exe}")

    if not zip_path.exists():
        write_log("ERRO: zip não encontrado")
        sys.exit(10)

    time.sleep(3)

    temp_root = Path(tempfile.gettempdir()) / "vivo_fiscal_suite_updater"
    extract_dir = temp_root / "extract"
    backup_dir = app_dir.parent / f"{app_dir.name}_backup"

    remove_dir_safe(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    remove_dir_safe(backup_dir)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        write_log(f"ZIP extraído em: {extract_dir}")
    except Exception as e:
        write_log(f"ERRO extraindo zip: {e}")
        sys.exit(11)

    package_dir = extract_dir / "package"
    if not package_dir.exists():
        package_dir = extract_dir

    if not package_dir.exists():
        write_log("ERRO: package_dir não existe")
        sys.exit(12)

    if app_dir.exists():
        ok = rename_dir_safe(app_dir, backup_dir)
        if not ok:
            write_log("ERRO: não conseguiu renomear app atual para backup")
            sys.exit(13)
        write_log(f"App antigo movido para backup: {backup_dir}")

    ok = copytree_safe(package_dir, app_dir)
    if not ok:
        write_log("ERRO: não conseguiu copiar nova versão")
        remove_dir_safe(app_dir)
        if backup_dir.exists():
            rename_dir_safe(backup_dir, app_dir)
        sys.exit(14)

    write_log(f"Nova versão copiada para: {app_dir}")

    remove_dir_safe(backup_dir)

    # Recalcula o exe final pelo nome do exe recebido
    final_exe = app_dir / app_exe.name
    write_log(f"APP_EXE final recalculado: {final_exe}")

    # Pequena espera para garantir escrita em disco
    time.sleep(1.5)

    try:
        if not final_exe.exists():
            write_log("ERRO: exe final não existe após cópia")
            sys.exit(15)

        subprocess.Popen([str(final_exe)], cwd=str(app_dir))
        write_log("App reaberto com sucesso")
    except Exception as e:
        write_log(f"ERRO reabrindo app: {e}")
        sys.exit(16)

    sys.exit(0)


if __name__ == "__main__":
    main()