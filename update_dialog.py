#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
)


class UpdateDialog(QDialog):
    def __init__(self, current_version, remote_version, notes="", mandatory=False, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Atualização disponível")
        self.resize(560, 320)
        self.setMinimumSize(520, 280)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        card = QFrame()
        card.setObjectName("PageCard")
        root.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        eyebrow = QLabel("SOFTWARE UPDATE")
        eyebrow.setObjectName("SectionEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel("Atualização disponível")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        sub = QLabel(
            "Uma nova versão da suíte está pronta para instalação."
            if not mandatory else
            "Uma atualização obrigatória está disponível para continuar usando a suíte."
        )
        sub.setObjectName("SectionText")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        info = QLabel(
            f"Versão atual: <b>{current_version}</b><br>"
            f"Nova versão: <b>{remote_version}</b>"
        )
        info.setObjectName("InfoValue")
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        layout.addWidget(info)

        notes_title = QLabel("Notas da atualização")
        notes_title.setObjectName("FieldTitle")
        layout.addWidget(notes_title)

        notes_lbl = QLabel(notes or "Correções e melhorias gerais.")
        notes_lbl.setObjectName("FieldText")
        notes_lbl.setWordWrap(True)
        layout.addWidget(notes_lbl)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.btn_later = QPushButton("Depois")
        self.btn_later.setObjectName("SecondaryButton")
        self.btn_later.setMinimumHeight(42)
        self.btn_later.setVisible(not mandatory)
        self.btn_later.clicked.connect(self.reject)
        buttons.addWidget(self.btn_later)

        self.btn_install = QPushButton("Instalar agora")
        self.btn_install.setObjectName("PrimaryButton")
        self.btn_install.setMinimumHeight(42)
        self.btn_install.clicked.connect(self.accept)
        buttons.addWidget(self.btn_install)

        layout.addLayout(buttons)