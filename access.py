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

def consultar_aprovacao_existente(machine_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    params = {
        "select": "id,status,session_id,machine_id,usuario_windows,maquina,created_at",
        "machine_id": f"eq.{machine_id}",
        "status": "eq.aprovado",
        "order": "created_at.desc",
        "limit": "1",
    }

    resp = requests.get(url, headers=_supabase_headers(), params=params, timeout=20)
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
        self.resize(760, 460)
        self.setMinimumSize(640, 420)

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
        root.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("PageCard")
        root.addWidget(card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(89, 48, 146, 20))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(4)

        eyebrow = QLabel("SECURE ACCESS")
        eyebrow.setObjectName("SectionEyebrow")
        left.addWidget(eyebrow)

        title = QLabel("Acesso ao workspace fiscal")
        title.setObjectName("SectionTitle")
        left.addWidget(title)

        subtitle = QLabel("Liberação remota da estação para acesso à suíte fiscal.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("SectionText")
        left.addWidget(subtitle)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        for txt in ["Estação identificada", "Liberação remota", "Ambiente corporativo"]:
            lb = QLabel(txt)
            lb.setObjectName("TopBadge")
            chips.addWidget(lb, 0, Qt.AlignLeft)
        chips.addStretch()
        left.addLayout(chips)

        header.addLayout(left, 1)

        logo = QLabel()
        pix = carregar_logo_vivo(88)
        if pix:
            logo.setPixmap(pix)
        header.addWidget(logo, alignment=Qt.AlignTop | Qt.AlignRight)

        layout.addLayout(header)

        row = QHBoxLayout()
        row.setSpacing(12)

        info_card = QFrame()
        info_card.setObjectName("SoftCard")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(5)

        lb1 = QLabel("USUÁRIO")
        lb1.setObjectName("SectionEyebrow")
        info_layout.addWidget(lb1)

        self.lb_nome = QLabel(self.usuario_windows)
        self.lb_nome.setObjectName("AccessMainName")
        info_layout.addWidget(self.lb_nome)

        val_machine = QLabel(self.nome_maquina)
        val_machine.setObjectName("FieldText")
        val_machine.setWordWrap(True)
        info_layout.addWidget(val_machine)

        row.addWidget(info_card, 1)

        id_card = QFrame()
        id_card.setObjectName("SoftCard")
        id_layout = QVBoxLayout(id_card)
        id_layout.setContentsMargins(16, 14, 16, 14)
        id_layout.setSpacing(5)

        lb2 = QLabel("ID DA ESTAÇÃO")
        lb2.setObjectName("SectionEyebrow")
        id_layout.addWidget(lb2)

        self.lb_hash = QLabel()
        self.lb_hash.setObjectName("HashValue")
        self.lb_hash.setTextInteractionFlags(Qt.TextSelectableByMouse)

        hash_curto = (
            f"{self.machine_id[:18]}...{self.machine_id[-8:]}"
            if len(self.machine_id) > 28 else self.machine_id
        )
        self.lb_hash.setText(hash_curto)
        self.lb_hash.setToolTip(self.machine_id)
        self.lb_hash.setWordWrap(False)
        id_layout.addWidget(self.lb_hash)

        sub_id = QLabel("Passe o mouse para ver o hash completo.")
        sub_id.setObjectName("FieldText")
        sub_id.setWordWrap(True)
        id_layout.addWidget(sub_id)

        row.addWidget(id_card, 1)

        layout.addLayout(row)

        status_card = QFrame()
        status_card.setObjectName("GlassCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(5)

        lb3 = QLabel("STATUS DA LIBERAÇÃO")
        lb3.setObjectName("SectionEyebrow")
        status_layout.addWidget(lb3)

        self.lbl_status = QLabel("Verificando acesso...")
        self.lbl_status.setObjectName("AccessStatusValue")
        self.lbl_status.setWordWrap(True)
        status_layout.addWidget(self.lbl_status)

        foot = QLabel("Assim que a solicitação for aprovada, a suíte será aberta automaticamente.")
        foot.setObjectName("FieldText")
        foot.setWordWrap(True)
        status_layout.addWidget(foot)

        layout.addWidget(status_card)

        botoes = QHBoxLayout()
        botoes.setSpacing(8)

        self.btn_solicitar = QPushButton("Solicitar liberação")
        self.btn_solicitar.setObjectName("PrimaryButton")
        self.btn_solicitar.setMinimumHeight(36)
        self.btn_solicitar.clicked.connect(self.solicitar_acesso)
        botoes.addWidget(self.btn_solicitar)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setObjectName("SecondaryButton")
        self.btn_fechar.setMinimumHeight(36)
        self.btn_fechar.clicked.connect(self.reject)
        botoes.addWidget(self.btn_fechar)

        botoes.addStretch()
        layout.addLayout(botoes)

    def _animar_entrada(self):
        self.setWindowOpacity(0.0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(240)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def _set_status(self, texto, erro=False):
        if erro:
            self.lbl_status.setStyleSheet(
                "color:#C54B68;font-size:12px;font-weight:600;background:transparent;"
            )
        else:
            self.lbl_status.setStyleSheet(
                "color:#425166;font-size:12px;font-weight:600;background:transparent;"
            )
        self.lbl_status.setText(texto)

    def verificar_status_inicial(self):
        try:
            # 1) primeiro vê se essa máquina já foi aprovada antes
            aprovacao_existente = consultar_aprovacao_existente(self.machine_id)
            if aprovacao_existente:
                self.acesso_liberado = True
                self.btn_solicitar.setEnabled(False)
                self._set_status("Esta estação já foi validada anteriormente. Abrindo suíte...")
                QTimer.singleShot(500, self.accept)
                return

            # 2) se não houver aprovação antiga, segue a lógica normal da sessão atual
            registro = consultar_status_acesso(self.session_id, self.machine_id)
            if not registro:
                self._set_status("Nenhuma solicitação enviada ainda.")
                return

            status = (registro.get("status") or "").lower()

            if status == "aprovado":
                self.acesso_liberado = True
                self.btn_solicitar.setEnabled(False)
                self._set_status("Acesso aprovado. Abrindo suíte...")
                QTimer.singleShot(500, self.accept)
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
            aprovacao_existente = consultar_aprovacao_existente(self.machine_id)
            if aprovacao_existente:
                self.timer.stop()
                self._polling = False
                self.acesso_liberado = True
                self.btn_solicitar.setEnabled(False)
                self._set_status("Esta estação já foi validada anteriormente. Abrindo suíte...")
                QTimer.singleShot(500, self.accept)
                return

            registro = consultar_status_acesso(self.session_id, self.machine_id)
            status = (registro or {}).get("status", "").lower()

            if status == "aprovado":
                self.timer.stop()
                self._polling = False
                self.acesso_liberado = True
                self.btn_solicitar.setEnabled(False)
                self._set_status("Acesso aprovado. Abrindo suíte...")
                QTimer.singleShot(500, self.accept)
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