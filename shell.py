#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QStackedWidget, QGraphicsDropShadowEffect
)

from resources import carregar_logo_vivo

from pages.dashboard_page import DashboardPage
from pages.p9_page import P9Page
from pages.consolidator_page import ConsolidatorPage
import json
from pathlib import Path
import time


def obter_versao_app():
    try:
        caminho = Path(__file__).resolve().parent / "app_version.json"

        with open(caminho, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("version", "—")

    except Exception:
        return "—"


class NavButton(QPushButton):
    clicked_index = Signal(int)

    def __init__(self, texto: str, index: int):
        super().__init__(texto)
        self.index = index

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setObjectName("NavButton")

        self.clicked.connect(self._emit_index)

    def _emit_index(self):
        self.clicked_index.emit(self.index)


class MainShell(QMainWindow):
    def __init__(self):
        super().__init__()

        self._t0_shell = time.perf_counter()
        print("[SHELL] início: 0.000s")
        

        self.usuario = "—"
        self.maquina = "—"
        self.machine_id = "—"

        self.setWindowTitle("VIVO Fiscal Suite")
        self.setMinimumSize(1180, 720)
        self.resize(1280, 780)

        central = QWidget()
        central.setObjectName("ShellRoot")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        t = time.perf_counter()
        self.sidebar = self._build_sidebar()
        print(f"[SHELL] _build_sidebar: {time.perf_counter() - t:.3f}s")

        t = time.perf_counter()
        self.topbar = self._build_topbar()
        print(f"[SHELL] _build_topbar: {time.perf_counter() - t:.3f}s")

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar, 0)

        self.content_wrap = QWidget()
        self.content_wrap.setObjectName("ContentWrap")
        root.addWidget(self.content_wrap, 1)

        content_layout = QVBoxLayout(self.content_wrap)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        self.topbar = self._build_topbar()
        content_layout.addWidget(self.topbar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        content_layout.addWidget(self.stack, 1)

        print(f"[SHELL] antes DashboardPage: {time.perf_counter() - self._t0_shell:.3f}s")
        self.page_dashboard = DashboardPage()
        print(f"[SHELL] depois DashboardPage: {time.perf_counter() - self._t0_shell:.3f}s")

        self.page_p9 = None
        self.page_consolidator = None

        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(QWidget())  # placeholder p9
        self.stack.addWidget(QWidget())  # placeholder consolidator

        self.nav_buttons = []
        self._add_nav_button("Visão geral", 0)
        self._add_nav_button("Validação P9", 1)
        self._add_nav_button("Consolidador Fiscal", 2)

        btn_ztmm = NavButton("ZTMM X LIVRO (Em andamento)", 3)
        btn_ztmm.setEnabled(False)
        self.nav_layout.addWidget(btn_ztmm)

        self.set_current_page(0)

    def set_user_context(self, usuario: str, maquina: str, machine_id: str):
        self.usuario = usuario or "—"
        self.maquina = maquina or "—"
        self.machine_id = machine_id or "—"

        self.user_name.setText(self.usuario)
        self.user_meta.setText(self.maquina)

        if self.machine_id and self.machine_id != "—":
            hash_curto = (
                f"{self.machine_id[:10]}...{self.machine_id[-6:]}"
                if len(self.machine_id) > 20
                else self.machine_id
            )
        else:
            hash_curto = "—"

        self.machine_chip.setText(hash_curto)
        self.machine_chip.setToolTip(self.machine_id)

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setMinimumWidth(236)
        side.setMaximumWidth(236)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(2, 0)
        shadow.setColor(QColor(0, 0, 0, 80))
        side.setGraphicsEffect(shadow)

        layout = QVBoxLayout(side)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(12)

        # Brand
        brand = QFrame()
        brand.setObjectName("BrandCard")

        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(10)

        logo_wrap = QFrame()
        logo_wrap.setObjectName("BrandLogoWrap")
        logo_wrap.setFixedSize(42, 42)

        logo_wrap_layout = QVBoxLayout(logo_wrap)
        logo_wrap_layout.setContentsMargins(0, 0, 0, 0)

        logo = QLabel()
        pix = carregar_logo_vivo(30)
        if pix:
            logo.setPixmap(pix)

        logo.setAlignment(Qt.AlignCenter)
        logo_wrap_layout.addWidget(logo)

        brand_layout.addWidget(logo_wrap, 0, Qt.AlignVCenter)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)

        title = QLabel("VIVO Workspace")
        title.setObjectName("BrandTitle")
        brand_text.addWidget(title)

        sub = QLabel("Fiscal command center")
        sub.setObjectName("BrandSubtitle")
        brand_text.addWidget(sub)

        brand_layout.addLayout(brand_text, 1)

        layout.addWidget(brand)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(120, 70, 200, 60))
        brand.setGraphicsEffect(shadow)

        # Navegação
        section = QLabel("NAVEGAÇÃO")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)

        nav_panel = QFrame()
        nav_panel.setObjectName("SidebarPanel")

        self.nav_layout = QVBoxLayout(nav_panel)
        self.nav_layout.setContentsMargins(10, 10, 10, 10)
        self.nav_layout.setSpacing(6)

        layout.addWidget(nav_panel)

        # Ambiente
        env_card = QFrame()
        env_card.setObjectName("SidebarPanel")

        env_layout = QVBoxLayout(env_card)
        env_layout.setContentsMargins(12, 12, 12, 12)
        env_layout.setSpacing(4)

        env_tag = QLabel("AMBIENTE")
        env_tag.setObjectName("SidebarSection")
        env_layout.addWidget(env_tag)

        env_title = QLabel("Operação fiscal")
        env_title.setObjectName("QuickTitle")
        env_title.setWordWrap(True)
        env_layout.addWidget(env_title)

        env_text = QLabel(
            "Validação de PDFs, consolidação TXT e exportação centralizadas."
        )
        env_text.setObjectName("QuickText")
        env_text.setWordWrap(True)
        env_layout.addWidget(env_text)

        layout.addWidget(env_card)

        # Sessão
        profile = QFrame()
        profile.setObjectName("ProfileCard")

        profile_layout = QVBoxLayout(profile)
        profile_layout.setContentsMargins(12, 12, 12, 12)
        profile_layout.setSpacing(4)

        mini = QLabel("SESSÃO")
        mini.setObjectName("SidebarSection")
        profile_layout.addWidget(mini)

        self.user_name = QLabel("—")
        self.user_name.setObjectName("ProfileName")
        self.user_name.setWordWrap(True)
        profile_layout.addWidget(self.user_name)

        self.user_meta = QLabel("—")
        self.user_meta.setObjectName("ProfileMeta")
        self.user_meta.setWordWrap(True)
        profile_layout.addWidget(self.user_meta)

        self.machine_chip = QLabel("—")
        self.machine_chip.setObjectName("MachineChip")
        self.machine_chip.setWordWrap(False)
        self.machine_chip.setTextInteractionFlags(Qt.TextSelectableByMouse)
        profile_layout.addWidget(self.machine_chip)

        layout.addWidget(profile)

        # Info institucional / desenvolvimento
        about = QFrame()
        about.setObjectName("SidebarPanel")

        about_layout = QVBoxLayout(about)
        about_layout.setContentsMargins(12, 12, 12, 12)
        about_layout.setSpacing(4)

        ab_tag = QLabel("VERSÃO")
        ab_tag.setObjectName("SidebarSection")
        about_layout.addWidget(ab_tag)

        versao = obter_versao_app()
        self.version_label = QLabel(f"Versão {versao}")
        self.version_label.setObjectName("QuickTitle")
        self.version_label.setWordWrap(True)
        about_layout.addWidget(self.version_label)

        self.about_text = QLabel(
            "Powered by Andersen\n"
            "Uso interno exclusivo.\n"
            "Criação e desenvolvimento: Thiago Lopomo."
        )
        self.about_text.setObjectName("QuickText")
        self.about_text.setWordWrap(True)
        about_layout.addWidget(self.about_text)

        layout.addWidget(about)

        layout.addStretch(1)
        return side

    def _build_topbar(self):
        top = QFrame()
        top.setObjectName("Topbar")

        layout = QHBoxLayout(top)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)

        self.top_badge = QLabel("WORKSPACE")
        self.top_badge.setObjectName("TopbarBadge")

        self.top_title = QLabel("Visão geral")
        self.top_title.setObjectName("TopbarTitle")

        self.top_subtitle = QLabel("Resumo dos módulos do ambiente.")
        self.top_subtitle.setObjectName("TopbarSubtitle")
        self.top_subtitle.setWordWrap(True)

        left.addWidget(self.top_badge)
        left.addWidget(self.top_title)
        left.addWidget(self.top_subtitle)

        layout.addLayout(left, 1)

        self.top_action = QPushButton("Ir para Validação P9")
        self.top_action.setObjectName("PrimaryButton")
        self.top_action.setMinimumHeight(34)
        self.top_action.setMinimumWidth(170)
        self.top_action.clicked.connect(self._handle_top_action)

        layout.addWidget(self.top_action, 0, Qt.AlignRight)

        return top

    def _add_nav_button(self, texto: str, index: int):
        btn = NavButton(texto, index)
        btn.clicked_index.connect(self.set_current_page)
        self.nav_layout.addWidget(btn)
        self.nav_buttons.append(btn)

    def set_current_page(self, index: int):
        if index == 1 and self.page_p9 is None:
            t = time.perf_counter()
            print(f"[SHELL] criando P9Page... {t - self._t0_shell:.3f}s")
            self.page_p9 = P9Page()
            print(f"[SHELL] P9Page criada em: {time.perf_counter() - t:.3f}s")

            old = self.stack.widget(1)
            self.stack.removeWidget(old)
            old.deleteLater()
            self.stack.insertWidget(1, self.page_p9)

        elif index == 2 and self.page_consolidator is None:
            t = time.perf_counter()
            print(f"[SHELL] criando ConsolidatorPage... {t - self._t0_shell:.3f}s")
            self.page_consolidator = ConsolidatorPage()
            print(f"[SHELL] ConsolidatorPage criada em: {time.perf_counter() - t:.3f}s")

            old = self.stack.widget(2)
            self.stack.removeWidget(old)
            old.deleteLater()
            self.stack.insertWidget(2, self.page_consolidator)

        self.stack.setCurrentIndex(index)

        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        if index == 0:
            self.topbar.setVisible(False)
        else:
            self.topbar.setVisible(False)

    def _handle_top_action(self):
        if self.stack.currentIndex() == 0:
            self.set_current_page(1)