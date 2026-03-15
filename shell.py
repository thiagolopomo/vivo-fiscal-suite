#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QStackedWidget, QGraphicsDropShadowEffect, QSizePolicy
)

from resources import carregar_logo_vivo
from pages.dashboard_page import DashboardPage
from pages.p9_page import P9Page
from pages.consolidator_page import ConsolidatorPage


class NavButton(QPushButton):
    clicked_index = Signal(int)

    def __init__(self, texto: str, index: int):
        super().__init__(texto)
        self.index = index
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(46)
        self.setObjectName("NavButton")
        self.clicked.connect(self._emit_index)

    def _emit_index(self):
        self.clicked_index.emit(self.index)


class MainShell(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("VIVO Fiscal Suite")
        self.resize(1450, 900)
        self.setMinimumSize(1180, 760)

        self._usuario = "—"
        self._maquina = "—"
        self._machine_id = "—"

        central = QWidget()
        central.setObjectName("ShellRoot")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)

        self.content_wrap = QWidget()
        self.content_wrap.setObjectName("ContentWrap")
        root.addWidget(self.content_wrap, 1)

        content_layout = QVBoxLayout(self.content_wrap)
        content_layout.setContentsMargins(22, 20, 22, 20)
        content_layout.setSpacing(18)

        self.topbar = self._build_topbar()
        content_layout.addWidget(self.topbar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")

        self.page_dashboard = DashboardPage()
        self.page_p9 = P9Page()
        self.page_consolidator = ConsolidatorPage()

        self.stack.addWidget(self.page_dashboard)      # index 0
        self.stack.addWidget(self.page_p9)             # index 1
        self.stack.addWidget(self.page_consolidator)   # index 2

        content_layout.addWidget(self.stack, 1)

        self.nav_buttons = []
        self._add_nav_button("Visão geral", 0, self.nav_layout)
        self._add_nav_button("Validação P9", 1, self.nav_layout)
        self._add_nav_button("Consolidador Fiscal", 2, self.nav_layout)

        self.set_current_page(0)

    def set_user_context(self, usuario: str, maquina: str, machine_id: str):
        self._usuario = usuario
        self._maquina = maquina
        self._machine_id = machine_id

        self.user_name.setText(usuario)
        self.user_meta.setText(f"{maquina}")
        self.machine_chip.setText(f"ID {machine_id[:18]}...")

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(290)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(2, 0)
        shadow.setColor(QColor(30, 20, 50, 18))
        side.setGraphicsEffect(shadow)

        layout = QVBoxLayout(side)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)

        brand = QFrame()
        brand.setObjectName("BrandCard")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(12)

        logo = QLabel()
        pix = carregar_logo_vivo(76)
        if pix:
            logo.setPixmap(pix)
        logo.setAlignment(Qt.AlignCenter)
        brand_layout.addWidget(logo, 0, Qt.AlignTop)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)

        title = QLabel("VIVO Fiscal Suite")
        title.setObjectName("BrandTitle")
        brand_text.addWidget(title)

        sub = QLabel("Workspace fiscal corporativo")
        sub.setObjectName("BrandSubtitle")
        brand_text.addWidget(sub)

        brand_text.addStretch()
        brand_layout.addLayout(brand_text, 1)

        layout.addWidget(brand)

        section = QLabel("NAVEGAÇÃO")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)

        nav_card = QFrame()
        nav_card.setObjectName("SidebarPanel")
        self.nav_layout = QVBoxLayout(nav_card)
        self.nav_layout.setContentsMargins(10, 10, 10, 10)
        self.nav_layout.setSpacing(8)
        layout.addWidget(nav_card)

        quick = QFrame()
        quick.setObjectName("SidebarPanel")
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(14, 14, 14, 14)
        quick_layout.setSpacing(8)

        q1 = QLabel("AMBIENTE")
        q1.setObjectName("SidebarSection")
        quick_layout.addWidget(q1)

        q2 = QLabel("Operação fiscal premium")
        q2.setObjectName("QuickTitle")
        quick_layout.addWidget(q2)

        q3 = QLabel(
            "Acesse os módulos principais pela navegação lateral e concentre a operação no painel central."
        )
        q3.setWordWrap(True)
        q3.setObjectName("QuickText")
        quick_layout.addWidget(q3)

        layout.addWidget(quick)

        layout.addStretch(1)

        profile = QFrame()
        profile.setObjectName("ProfileCard")
        profile_layout = QVBoxLayout(profile)
        profile_layout.setContentsMargins(14, 14, 14, 14)
        profile_layout.setSpacing(6)

        mini = QLabel("SESSÃO")
        mini.setObjectName("SidebarSection")
        profile_layout.addWidget(mini)

        self.user_name = QLabel("—")
        self.user_name.setObjectName("ProfileName")
        profile_layout.addWidget(self.user_name)

        self.user_meta = QLabel("—")
        self.user_meta.setObjectName("ProfileMeta")
        self.user_meta.setWordWrap(True)
        profile_layout.addWidget(self.user_meta)

        self.machine_chip = QLabel("ID —")
        self.machine_chip.setObjectName("MachineChip")
        self.machine_chip.setWordWrap(True)
        profile_layout.addWidget(self.machine_chip)

        layout.addWidget(profile)

        return side

    def _build_topbar(self):
        top = QFrame()
        top.setObjectName("Topbar")

        layout = QHBoxLayout(top)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)

        self.top_title = QLabel("Visão geral")
        self.top_title.setObjectName("TopbarTitle")
        left.addWidget(self.top_title)

        self.top_subtitle = QLabel("Resumo executivo dos módulos disponíveis no workspace.")
        self.top_subtitle.setObjectName("TopbarSubtitle")
        self.top_subtitle.setWordWrap(True)
        left.addWidget(self.top_subtitle)

        layout.addLayout(left, 1)

        self.top_action = QPushButton("Abrir módulo")
        self.top_action.setObjectName("PrimaryButton")
        self.top_action.setMinimumHeight(42)
        self.top_action.setMinimumWidth(170)
        self.top_action.clicked.connect(self._handle_top_action)
        layout.addWidget(self.top_action, 0, Qt.AlignRight | Qt.AlignVCenter)

        return top

    def _add_nav_button(self, texto: str, index: int, parent_layout):
        btn = NavButton(texto, index)
        btn.clicked_index.connect(self.set_current_page)
        parent_layout.addWidget(btn)
        self.nav_buttons.append(btn)

    def set_current_page(self, index: int):
        self.stack.setCurrentIndex(index)

        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        if index == 0:
            self.top_title.setText("Visão geral")
            self.top_subtitle.setText("Resumo executivo dos módulos disponíveis no workspace.")
            self.top_action.setText("Ir para Validação P9")
        elif index == 1:
            self.top_title.setText("Validação P9")
            self.top_subtitle.setText("Leitura de RAICMS em PDF, geração de Excel e acompanhamento do processamento.")
            self.top_action.setText("Executar P9")
        elif index == 2:
            self.top_title.setText("Consolidador Fiscal")
            self.top_subtitle.setText("Preparação da base interna e exportação nos layouts ANDERSEN e VIVO.")
            self.top_action.setText("Abrir Consolidador")

    def _handle_top_action(self):
        idx = self.stack.currentIndex()

        if idx == 0:
            self.set_current_page(1)
        elif idx == 1:
            self.page_p9.executar()
        elif idx == 2:
            # abre a página; execução continua sendo pelo botão da própria página
            self.set_current_page(2)