#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time
import shutil
import multiprocessing
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from resources import obter_icone, carregar_fontes_app
from theme import build_app_qss
from splash import SplashScreen
from access import TelaAcesso
from shell import MainShell


def limpar_caches_bases():
    cache_dir = Path.home() / "AppData" / "Local" / "ValidadorVIVO"
    if not cache_dir.exists():
        return
    # Arquivos de cache de bases processadas (NÃO remove acesso_aprovado.json)
    arquivos_cache = [
        "base_processada.parquet",
        "base_processada_meta.json",
        "base_andersen_conferencia.parquet",
        "base_vivo_conferencia.parquet",
        "conferencia_bases_meta.json",
        "raicms_meta.json",
        "ztmm_meta.json",
        "ZTMM_Consolidado.parquet",
    ]
    for nome in arquivos_cache:
        f = cache_dir / nome
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
    # Pastas de cache
    pastas_cache = [
        "_tmp_shards_vivo",
        "execucoes_conferencia",
    ]
    for nome in pastas_cache:
        p = cache_dir / nome
        if p.exists() and p.is_dir():
            try:
                shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass
    # Parquets com nome dinâmico (BASE_INTERNA__*.parquet)
    for f in cache_dir.glob("BASE_INTERNA__*.parquet"):
        try:
            f.unlink()
        except Exception:
            pass

from update_service import (
    check_for_update,
    download_update_package,
    extract_update_package,
)
from update_dialog import UpdateDialog
from updater_client import iniciar_instalacao_update

T0 = time.perf_counter()


def log_tempo(etapa: str):
    print(f"[TEMPO] {etapa}: {time.perf_counter() - T0:.3f}s")


def verificar_atualizacao(shell):
    from PySide6.QtWidgets import QMessageBox, QProgressDialog, QApplication

    log_tempo("início verificar_atualizacao")

    info = check_for_update()
    log_tempo("fim check_for_update")

    if info.get("error"):
        QMessageBox.critical(shell, "Erro no update", str(info["error"]))
        return

    if not info.get("update_available"):
        return

    dlg = UpdateDialog(
        current_version=info["current_version"],
        remote_version=info["remote_version"],
        notes=info.get("notes", ""),
        mandatory=info.get("mandatory", False),
        parent=shell
    )

    log_tempo("antes dialog update")

    if dlg.exec() == UpdateDialog.Accepted:
        try:
            progresso = QProgressDialog("Baixando atualização...", None, 0, 100, shell)
            progresso.setWindowTitle("Atualização")
            progresso.setWindowModality(Qt.ApplicationModal)
            progresso.setMinimumDuration(0)
            progresso.setAutoClose(False)
            progresso.setAutoReset(False)
            progresso.setValue(0)
            progresso.show()
            QApplication.processEvents()

            def on_download_progress(recebido, total):
                if total > 0:
                    pct = int((recebido / total) * 50)
                    progresso.setValue(min(pct, 50))
                    progresso.setLabelText(
                        f"Baixando atualização... {int((recebido / total) * 100)}%"
                    )
                else:
                    progresso.setValue(0)
                    progresso.setLabelText("Baixando atualização...")
                QApplication.processEvents()

            zip_path = download_update_package(
                url=info["url"],
                expected_sha256=info.get("sha256", ""),
                progress_callback=on_download_progress
            )
            log_tempo("fim download_update_package")

            def on_extract_progress(done_bytes, total_bytes, current_name):
                pct_extract = int((done_bytes / total_bytes) * 50)
                pct_total = 50 + pct_extract
                progresso.setValue(min(pct_total, 100))
                progresso.setLabelText(f"Preparando instalação... {current_name}")
                QApplication.processEvents()

            extracted_dir = extract_update_package(
                zip_path=zip_path,
                progress_callback=on_extract_progress
            )
            log_tempo("fim extract_update_package")

            progresso.setValue(100)
            progresso.setLabelText("Concluindo preparação da atualização...")
            QApplication.processEvents()

            iniciar_instalacao_update(extracted_dir, parent=shell)
            log_tempo("fim iniciar_instalacao_update")

            progresso.close()
            QApplication.processEvents()

            shell.close()
            QApplication.processEvents()
            QApplication.instance().quit()

        except Exception as e:
            QMessageBox.critical(shell, "Erro", f"Falha ao instalar atualização:\n{e}")


def main():
    log_tempo("início main")

    limpar_caches_bases()
    log_tempo("limpar_caches_bases")

    app = QApplication(sys.argv)
    log_tempo("QApplication criada")

    familia = carregar_fontes_app()
    log_tempo("carregar_fontes_app")

    app.setStyleSheet(build_app_qss(familia))
    log_tempo("build_app_qss + setStyleSheet")

    icone = obter_icone()
    log_tempo("obter_icone")

    app.setWindowIcon(icone)
    log_tempo("setWindowIcon app")

    splash = SplashScreen()
    log_tempo("SplashScreen criada")

    shell = None

    def abrir_fluxo():
        nonlocal shell

        log_tempo("início abrir_fluxo")

        t_acesso = time.perf_counter()
        acesso = TelaAcesso()
        print(f"[TEMPO] TelaAcesso criada em: {time.perf_counter() - t_acesso:.3f}s")

        acesso.setWindowIcon(icone)
        log_tempo("setWindowIcon acesso")

        t_exec = time.perf_counter()
        result = acesso.exec()
        print(f"[TEMPO] acesso.exec() terminou em: {time.perf_counter() - t_exec:.3f}s")

        if result == TelaAcesso.Accepted and acesso.acesso_liberado:
            log_tempo("TelaAcesso aceita")

            t_shell = time.perf_counter()
            shell = MainShell()
            print(f"[TEMPO] MainShell criado pós-acesso em: {time.perf_counter() - t_shell:.3f}s")

            shell.setWindowIcon(icone)
            log_tempo("setWindowIcon shell")

            shell.set_user_context(
                usuario=acesso.usuario_windows,
                maquina=acesso.nome_maquina,
                machine_id=acesso.machine_id
            )
            log_tempo("set_user_context")

            shell.show()
            log_tempo("shell.show")

            shell.showMaximized()
            log_tempo("shell.showMaximized")

            QTimer.singleShot(700, lambda: verificar_atualizacao(shell))
        else:
            log_tempo("TelaAcesso recusada/fechada")
            app.quit()

    splash.iniciar(abrir_fluxo)
    log_tempo("splash.iniciar")

    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()