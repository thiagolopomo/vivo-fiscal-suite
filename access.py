#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import hashlib
import getpass
import socket
import platform
import uuid
import requests

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QColor

from resources import carregar_logo_vivo

APP_TITLE = "VIVO Fiscal Suite"
CHECK_INTERVAL_MS = 3000

SUPABASE_URL = "https://jhkqfacpobwnirioskii.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Impoa3FmYWNwb2J3bmlyaW9za2lpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyNzU2MDEsImV4cCI6MjA4ODg1MTYwMX0.lnRnP4ESzQc54LxX-6Y-qRZsfPEv1SGg3ozd2R0N4hY"
SUPABASE_TABLE = "solicitacoes_acesso"


def _supabase_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }


def gerar_machine_id():
    usuario = getpass.getuser()
    maquina = socket.gethostname()
    sistema = platform.platform()
    base = f"{usuario}|{maquina}|{sistema}|{APP_TITLE}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def consultar_status_acesso(session_id, machine_id):
    url = f"{SUPABASE_URL}/rest/v1/rpc/consultar_status_acesso"
    payload = {"p_session_id": session_id, "p_machine_id": machine_id}
    resp = requests.post(url, headers=_supabase_headers(), data=json.dumps(payload), timeout=20)
    resp.raise_for_status()
    dados = resp.json()
    return dados[0] if dados else None


def solicitar_acesso_remoto(machine_id, session_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    payload = {
        "app": APP_TITLE,
        "machine_id": machine_id,
        "session_id": session_id,
        "usuario_windows": getpass.getuser(),
        "maquina": socket.gethostname(),
        "status": "pendente",
    }
    headers = _supabase_headers()
    headers["Prefer"] = "return=representation"
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
    resp.raise_for_status()
    dados = resp.json()
    return dados[0] if dados else payload


class TelaAcesso(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Acesso seguro")
        self.setModal(True)
        self.resize(860, 540)
        self.setMinimumSize(760, 500)

        self.session_id = str(uuid.uuid4())
        self.machine_id = gerar_machine_id()
        self.usuario_windows = getpass.getuser()
        self.nome_maquina = socket.gethostname()

        self.acesso_liberado = False
        self._polling = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_status)

        self._montar_tela()
        self._animar_entrada()
        QTimer.singleShot(250, self.verificar_status_inicial)

    def _montar_tela(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 26, 26, 26)

        card = QFrame()
        card.setObjectName("PageCard")
        root.addWidget(card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(89, 48, 146, 28))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(6)

        eyebrow = QLabel("SECURE ACCESS")
        eyebrow.setObjectName("SectionEyebrow")
        left.addWidget(eyebrow)

        title = QLabel("Acesso ao workspace fiscal")
        title.setObjectName("SectionTitle")
        left.addWidget(title)

        subtitle = QLabel(
            "Uma única suíte para Validação P9 e Consolidador Fiscal, com liberação remota e identificação da estação."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("SectionText")
        left.addWidget(subtitle)

        chips = QHBoxLayout()
        for txt in ["Identidade da estação", "Liberação remota", "Ambiente corporativo"]:
            lb = QLabel(txt)
            lb.setObjectName("TopBadge")
            chips.addWidget(lb, 0, Qt.AlignLeft)
        chips.addStretch()
        left.addLayout(chips)

        header.addLayout(left, 1)

        logo = QLabel()
        pix = carregar_logo_vivo(110)
        if pix:
            logo.setPixmap(pix)
        header.addWidget(logo, alignment=Qt.AlignTop | Qt.AlignRight)

        layout.addLayout(header)

        row = QHBoxLayout()
        row.setSpacing(16)

        info_card = QFrame()
        info_card.setObjectName("AccentPanel")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(18, 16, 18, 16)
        info_layout.setSpacing(6)

        lb1 = QLabel("LOGADO COMO")
        lb1.setObjectName("SectionEyebrow")
        info_layout.addWidget(lb1)

        val_user = QLabel(self.usuario_windows)
        val_user.setObjectName("MetricValue")
        info_layout.addWidget(val_user)

        val_machine = QLabel(f"Estação: {self.nome_maquina}")
        val_machine.setObjectName("FieldText")
        val_machine.setWordWrap(True)
        info_layout.addWidget(val_machine)

        row.addWidget(info_card, 1)

        id_card = QFrame()
        id_card.setObjectName("SoftCard")
        id_layout = QVBoxLayout(id_card)
        id_layout.setContentsMargins(18, 16, 18, 16)
        id_layout.setSpacing(6)

        lb2 = QLabel("ID DA ESTAÇÃO")
        lb2.setObjectName("SectionEyebrow")
        id_layout.addWidget(lb2)

        self.id_lbl = QLabel(self.machine_id[:26] + "...")
        self.id_lbl.setObjectName("InfoValue")
        self.id_lbl.setWordWrap(True)
        id_layout.addWidget(self.id_lbl)

        sub_id = QLabel("Identificador criptográfico da máquina para controle de acesso.")
        sub_id.setObjectName("FieldText")
        sub_id.setWordWrap(True)
        id_layout.addWidget(sub_id)

        row.addWidget(id_card, 1)

        layout.addLayout(row)

        status_card = QFrame()
        status_card.setObjectName("GlassCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(6)

        lb3 = QLabel("STATUS DA LIBERAÇÃO")
        lb3.setObjectName("SectionEyebrow")
        status_layout.addWidget(lb3)

        self.lbl_status = QLabel("Verificando acesso...")
        self.lbl_status.setObjectName("InfoValue")
        self.lbl_status.setWordWrap(True)
        status_layout.addWidget(self.lbl_status)

        foot = QLabel("A aprovação é refletida em tempo real assim que a solicitação for tratada.")
        foot.setObjectName("FieldText")
        foot.setWordWrap(True)
        status_layout.addWidget(foot)

        layout.addWidget(status_card)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        self.btn_solicitar = QPushButton("Solicitar liberação")
        self.btn_solicitar.setObjectName("PrimaryButton")
        self.btn_solicitar.setMinimumHeight(44)
        self.btn_solicitar.clicked.connect(self.solicitar_acesso)
        botoes.addWidget(self.btn_solicitar)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setObjectName("SecondaryButton")
        self.btn_fechar.setMinimumHeight(44)
        self.btn_fechar.clicked.connect(self.reject)
        botoes.addWidget(self.btn_fechar)

        botoes.addStretch()
        layout.addLayout(botoes)

    def _animar_entrada(self):
        self.setWindowOpacity(0.0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(280)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def _set_status(self, texto, erro=False):
        if erro:
            self.lbl_status.setStyleSheet(
                "color:#C64369;font-size:14px;font-weight:700;background:transparent;"
            )
        else:
            self.lbl_status.setStyleSheet(
                "color:#241B31;font-size:14px;font-weight:700;background:transparent;"
            )
        self.lbl_status.setText(texto)

    def verificar_status_inicial(self):
        try:
            registro = consultar_status_acesso(self.session_id, self.machine_id)
            if not registro:
                self._set_status("Nenhuma solicitação enviada ainda.")
                return

            status = (registro.get("status") or "").lower()

            if status == "aprovado":
                self.acesso_liberado = True
                self._set_status("Acesso aprovado. Abrindo suíte...")
                QTimer.singleShot(600, self.accept)
                return

            if status == "negado":
                self._set_status("Sua solicitação foi negada.", erro=True)
                return

            if status == "pendente":
                self._set_status("Solicitação em análise. Aguardando aprovação...")
                self.iniciar_polling()
                return

        except requests.HTTPError as e:
            codigo = getattr(e.response, "status_code", None)
            if codigo == 401:
                self._set_status("Falha de autorização no Supabase. Revise chave, URL e permissões.", erro=True)
            else:
                self._set_status(f"Falha ao verificar acesso: {e}", erro=True)
        except Exception as e:
            self._set_status(f"Falha ao verificar acesso: {e}", erro=True)

    def solicitar_acesso(self):
        try:
            self.btn_solicitar.setEnabled(False)
            solicitar_acesso_remoto(self.machine_id, self.session_id)
            self._set_status("Solicitação enviada. Aguardando aprovação...")
            self.iniciar_polling()
        except Exception as e:
            self.btn_solicitar.setEnabled(True)
            self._set_status("Falha ao solicitar acesso.", erro=True)
            QMessageBox.critical(self, "Erro", f"Não foi possível solicitar acesso:\n{e}")

    def iniciar_polling(self):
        if self._polling:
            return
        self._polling = True
        self.timer.start(CHECK_INTERVAL_MS)

    def _poll_status(self):
        try:
            registro = consultar_status_acesso(self.session_id, self.machine_id)
            status = (registro or {}).get("status", "").lower()

            if status == "aprovado":
                self.timer.stop()
                self._polling = False
                self.acesso_liberado = True
                self._set_status("Acesso aprovado. Abrindo suíte...")
                QTimer.singleShot(600, self.accept)
                return

            if status == "negado":
                self.timer.stop()
                self._polling = False
                self.btn_solicitar.setEnabled(True)
                self._set_status("Sua solicitação foi negada.", erro=True)
                return

            self._set_status("Aguardando aprovação...")

        except Exception as e:
            self._set_status(f"Falha ao consultar aprovação: {e}", erro=True)