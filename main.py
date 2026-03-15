#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from resources import obter_icone, carregar_fontes_app
from theme import build_app_qss
from splash import SplashScreen
from access import TelaAcesso
from shell import MainShell

from app_info import APP_VERSION, UPDATE_MANIFEST_URL
from update_service import check_for_update, download_update_package
from update_dialog import UpdateDialog
from updater_client import iniciar_instalacao_update


def verificar_atualizacao(shell):
    from PySide6.QtWidgets import QMessageBox, QProgressDialog, QApplication

    info = check_for_update()

    QMessageBox.information(
        shell,
        "DEBUG UPDATE",
        f"APP_VERSION = {APP_VERSION}\n"
        f"UPDATE_MANIFEST_URL = {UPDATE_MANIFEST_URL}\n\n"
        f"INFO = {info}"
    )

    if info.get("error"):
        QMessageBox.critical(shell, "Erro no update", str(info["error"]))
        return

    if not info.get("update_available"):
        QMessageBox.information(
            shell,
            "Sem atualização",
            f"Atual: {info.get('current_version')} | Remota: {info.get('remote_version')}"
        )
        return

    dlg = UpdateDialog(
        current_version=info["current_version"],
        remote_version=info["remote_version"],
        notes=info.get("notes", ""),
        mandatory=info.get("mandatory", False),
        parent=shell
    )

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

            def on_progress(recebido, total):
                if total > 0:
                    pct = int((recebido / total) * 100)
                    progresso.setValue(min(pct, 100))
                    progresso.setLabelText(f"Baixando atualização... {pct}%")
                else:
                    progresso.setValue(0)
                    progresso.setLabelText("Baixando atualização...")
                QApplication.processEvents()

            zip_path = download_update_package(
                url=info["url"],
                expected_sha256=info.get("sha256", ""),
                progress_callback=on_progress
            )

            progresso.setValue(100)
            progresso.setLabelText("Instalando atualização e reiniciando o aplicativo...")
            QApplication.processEvents()

            iniciar_instalacao_update(zip_path, parent=shell)
            QApplication.instance().quit()

        except Exception as e:
            QMessageBox.critical(shell, "Erro", f"Falha ao instalar atualização:\n{e}")


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    familia = carregar_fontes_app()
    app.setStyleSheet(build_app_qss(familia))

    icone = obter_icone()
    app.setWindowIcon(icone)

    splash = SplashScreen()
    shell = MainShell()
    shell.setWindowIcon(icone)

    def abrir_fluxo():
        acesso = TelaAcesso()
        acesso.setWindowIcon(icone)

        if acesso.exec() == TelaAcesso.Accepted and acesso.acesso_liberado:
            shell.set_user_context(
                usuario=acesso.usuario_windows,
                maquina=acesso.nome_maquina,
                machine_id=acesso.machine_id
            )
            shell.show()

            QTimer.singleShot(700, lambda: verificar_atualizacao(shell))
        else:
            app.quit()

    splash.iniciar(abrir_fluxo)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()