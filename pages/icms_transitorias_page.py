#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Aba ICMS Transitórias: consolida razões SAP (TXTs) e valida o
movimento por Conta contra um balancete (xlsx/xlsb/csv).

Layout segue o mesmo padrão visual do ZtmmPage: hero card, tabs, cards
premium, progresso + log + summary responsivos (flip horizontal/vertical
em telas estreitas).
"""
import os
from pathlib import Path

import polars as pl
from PySide6.QtCore import Qt, QObject, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QMessageBox, QTextEdit, QSizePolicy, QProgressBar,
    QBoxLayout, QLineEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QGraphicsOpacityEffect,
)

from workers.icms_transitorias_worker import (
    TransitConsolidatorWorker,
    TransitValidacaoWorker,
    TransitExtracaoAAWorker,
    TransitLivroExtractWorker,
)
from icms_transitorias_logic import carregar_meta_transitorias, CACHE_TRANSIT_VALID
from pages.p9_page import MetricBox, HoverCard, ResponsiveGrid
from log_service import get_machine_id


# =====================================================================
# Transição suave disabled -> enabled em botões
# =====================================================================
class EnableFadeTransition(QObject):
    """Adiciona um fade-in suave quando o botão passa de disabled para
    enabled — efeito "wake up" que apps modernos usam pra dar contexto
    visual ao usuário de que algo acabou de ficar disponível.

    Quando o estado vai pra disabled de novo, é instantâneo (o estilo
    cinza do stylesheet basta — não precisa animar).
    """

    def __init__(self, button, duracao_ms=380):
        super().__init__(button)
        self.button = button

        self._effect = QGraphicsOpacityEffect(button)
        self._effect.setOpacity(1.0)
        button.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(duracao_ms)
        # OutCubic dá uma desaceleração natural (rápido no início, suave no fim).
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        button.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.button and event.type() == QEvent.EnabledChange:
            if self.button.isEnabled():
                # disabled -> enabled : fade-in 0.35 -> 1.0
                self._anim.stop()
                self._anim.setStartValue(0.35)
                self._anim.setEndValue(1.0)
                self._anim.start()
            else:
                # enabled -> disabled : snap (o stylesheet cinza cuida do resto)
                self._anim.stop()
                self._effect.setOpacity(1.0)
        return False


# =====================================================================
# Linha compacta com label + input + botão (mesmo padrão do ZTMM)
# =====================================================================
class CompactPathRow(QWidget):
    def __init__(self, label_text, placeholder, btn_text, on_click,
                 is_file=False, file_filter=""):
        super().__init__()
        self.is_file = is_file
        self.file_filter = file_filter
        self._on_click = on_click

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lb = QLabel(label_text)
        lb.setObjectName("FieldTitle")
        lb.setMinimumWidth(110)
        lb.setMaximumWidth(160)
        lb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lay.addWidget(lb, 0)

        self.input = QLineEdit()
        self.input.setReadOnly(True)
        self.input.setPlaceholderText(placeholder)
        self.input.setObjectName("PathInput")
        lay.addWidget(self.input, 1)

        btn = QPushButton(btn_text)
        btn.setObjectName("SecondaryButton")
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.clicked.connect(self._handle_click)
        lay.addWidget(btn, 0)

    def _handle_click(self):
        if self.is_file:
            path, _ = QFileDialog.getOpenFileName(
                self, "Selecionar arquivo", "", self.file_filter
            )
            if path:
                self.input.setText(path)
        elif self._on_click:
            self._on_click()


# =====================================================================
# Aba 1: Consolidação dos Razões
# =====================================================================
class _TabConsolidacao(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 0)
        root.setSpacing(0)

        inner_card = HoverCard()
        inner_card.setObjectName("PremiumPathCard")
        inner_card.setAttribute(Qt.WA_StyledBackground, True)
        inner_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(inner_card, 1)

        lay = QVBoxLayout(inner_card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # ---- Caminho da pasta dos razões ----
        self.path_razoes = CompactPathRow(
            "Pasta Razões:", "Pasta com TXTs de razão SAP",
            "Selecionar", self._sel_razoes,
        )
        lay.addWidget(self.path_razoes)

        # ---- Botão consolidar ----
        cons_row = QHBoxLayout()
        cons_row.setSpacing(8)
        cons_row.setContentsMargins(0, 2, 0, 2)
        self.btn_consolidar = QPushButton("Consolidar Razões")
        self.btn_consolidar.setObjectName("PrimaryButton")
        self.btn_consolidar.clicked.connect(self.page.executar_consolidacao)
        cons_row.addWidget(self.btn_consolidar, 0)
        cons_row.addStretch(1)
        lay.addLayout(cons_row)

        # ===========================================================
        # Card 1: Extrair Razões Conciliados WE / WL
        # ===========================================================
        extr_card = HoverCard()
        extr_card.setObjectName("AnaliseActionCard")
        extr_card.setAttribute(Qt.WA_StyledBackground, True)
        extr_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        ec_outer = QVBoxLayout(extr_card)
        ec_outer.setContentsMargins(14, 12, 14, 12)
        ec_outer.setSpacing(8)

        # Linha 1: ícone + título + descrição
        ec_top = QHBoxLayout()
        ec_top.setSpacing(10)
        ec_top.setContentsMargins(0, 0, 0, 0)

        icon_frame = QFrame()
        icon_frame.setObjectName("AnaliseIconFrame")
        icon_frame.setFixedSize(32, 32)
        i_lay = QVBoxLayout(icon_frame)
        i_lay.setContentsMargins(0, 0, 0, 0)
        i_lb = QLabel("AA")
        i_lb.setAlignment(Qt.AlignCenter)
        i_lb.setStyleSheet(
            "font-size:10px; font-weight:800; color:#FFF; background:transparent;"
        )
        i_lay.addWidget(i_lb)
        ec_top.addWidget(icon_frame, 0, Qt.AlignTop)

        ec_text = QVBoxLayout()
        ec_text.setSpacing(2)
        ec_text.setContentsMargins(0, 0, 0, 0)

        info_t = QLabel("Razões Conciliados (Chave_02 = Div_NºDoc_Tipo)")
        info_t.setStyleSheet(
            "font-size:13px; font-weight:800; color:#1F293B; background:transparent;"
        )
        ec_text.addWidget(info_t)

        info_d = QLabel(
            "Filtra Tipo ∈ {WE, WL} e mantém apenas os grupos cuja soma de "
            "Montante Razão zera (Status AA = Conciliado). Adiciona Referência "
            "AA (sem a Série e sem zeros à esquerda) e Chave_01 = Div_RefAA. "
            "Linhas não conciliadas saem do arquivo final."
        )
        info_d.setStyleSheet(
            "font-size:10px; color:#5C6B85; background:transparent;"
        )
        info_d.setWordWrap(True)
        ec_text.addWidget(info_d)

        ec_top.addLayout(ec_text, 1)
        ec_outer.addLayout(ec_top)

        # Stretch no MEIO empurra os botões pro rodapé do card e o header
        # pro topo, deixando ar entre os dois.
        ec_outer.addStretch(1)

        # Linha 2: chips informativos (esquerda) + 3 botões (direita)
        ec_actions = QHBoxLayout()
        ec_actions.setSpacing(6)
        ec_actions.setContentsMargins(0, 4, 0, 0)

        for txt in ["Status AA", "Referência AA", "Chave_01", "Chave_02"]:
            chip = QLabel(txt)
            chip.setObjectName("AnaliseChip")
            ec_actions.addWidget(chip, 0, Qt.AlignVCenter)

        ec_actions.addStretch(1)

        self.btn_extrair_we = QPushButton("Extrair WE")
        self.btn_extrair_we.setObjectName("ExtractBtnWE")
        self.btn_extrair_we.setCursor(Qt.PointingHandCursor)
        self.btn_extrair_we.setEnabled(False)
        self.btn_extrair_we.setMinimumHeight(32)
        self.btn_extrair_we.clicked.connect(
            lambda: self.page.executar_extracao_aa("WE")
        )
        ec_actions.addWidget(self.btn_extrair_we, 0, Qt.AlignVCenter)

        self.btn_extrair_wl = QPushButton("Extrair WL")
        self.btn_extrair_wl.setObjectName("ExtractBtnWL")
        self.btn_extrair_wl.setCursor(Qt.PointingHandCursor)
        self.btn_extrair_wl.setEnabled(False)
        self.btn_extrair_wl.setMinimumHeight(32)
        self.btn_extrair_wl.clicked.connect(
            lambda: self.page.executar_extracao_aa("WL")
        )
        ec_actions.addWidget(self.btn_extrair_wl, 0, Qt.AlignVCenter)

        self.btn_extrair_both = QPushButton("Extrair WE + WL")
        self.btn_extrair_both.setObjectName("ExtractBtnBoth")
        self.btn_extrair_both.setCursor(Qt.PointingHandCursor)
        self.btn_extrair_both.setEnabled(False)
        self.btn_extrair_both.setMinimumHeight(32)
        self.btn_extrair_both.clicked.connect(
            lambda: self.page.executar_extracao_aa("BOTH")
        )
        ec_actions.addWidget(self.btn_extrair_both, 0, Qt.AlignVCenter)

        ec_outer.addLayout(ec_actions)

        lay.addWidget(extr_card, 1)

        # ===========================================================
        # Card 2: Livro Fiscal -> Transitórias (Entradas / Saídas)
        # ===========================================================
        livro_card = HoverCard()
        livro_card.setObjectName("DivisoesCard")
        livro_card.setAttribute(Qt.WA_StyledBackground, True)
        livro_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lc_outer = QVBoxLayout(livro_card)
        lc_outer.setContentsMargins(14, 10, 14, 12)
        lc_outer.setSpacing(8)

        # Cabeçalho do card
        lc_head = QHBoxLayout()
        lc_head.setSpacing(10)
        lc_head.setContentsMargins(0, 0, 0, 0)

        livro_icon = QFrame()
        livro_icon.setObjectName("AnaliseIconFrame")
        livro_icon.setFixedSize(30, 30)
        li_lay = QVBoxLayout(livro_icon)
        li_lay.setContentsMargins(0, 0, 0, 0)
        li_lb = QLabel("LF")
        li_lb.setAlignment(Qt.AlignCenter)
        li_lb.setStyleSheet(
            "font-size:9px; font-weight:800; color:#FFF; background:transparent;"
        )
        li_lay.addWidget(li_lb)
        lc_head.addWidget(livro_icon, 0, Qt.AlignVCenter)

        lc_text = QVBoxLayout()
        lc_text.setSpacing(0)
        lc_text.setContentsMargins(0, 0, 0, 0)

        livro_t = QLabel("Transitórias do Livro Fiscal")
        livro_t.setStyleSheet(
            "font-size:13px; font-weight:800; color:#1F293B; background:transparent;"
        )
        lc_text.addWidget(livro_t)

        livro_d = QLabel(
            "Importe o livro consolidado (xlsx, xlsb, csv ou parquet) e gere "
            "a base de Transitórias filtrando os CFOPs específicos. Cria "
            "CHAVE DA NOTA AA (com ponto final) e Chave_01 = Divisão_INFEM_NUM."
        )
        livro_d.setStyleSheet(
            "font-size:10px; color:#5C6B85; background:transparent;"
        )
        livro_d.setWordWrap(True)
        lc_text.addWidget(livro_d)

        lc_head.addLayout(lc_text, 1)
        lc_outer.addLayout(lc_head)

        # Linha do file picker
        self.path_livro = CompactPathRow(
            "Livro Fiscal:", "Selecione o arquivo do livro consolidado",
            "Selecionar", None,
            is_file=True,
            file_filter=(
                "Arquivos suportados (*.xlsx *.xlsb *.csv *.parquet);;"
                "Excel (*.xlsx *.xlsb);;CSV (*.csv);;Parquet (*.parquet);;"
                "Todos (*.*)"
            ),
        )
        lc_outer.addWidget(self.path_livro)

        # Stretch entre file-picker e botões — empurra os botões pro rodapé
        lc_outer.addStretch(1)

        # Botões de extração lado a lado
        livro_btns = QHBoxLayout()
        livro_btns.setSpacing(10)
        livro_btns.setContentsMargins(0, 4, 0, 0)
        livro_btns.addStretch(1)

        self.btn_livro_entradas = QPushButton("Extrair Entradas Transitórias")
        self.btn_livro_entradas.setObjectName("ExtractBtnLivroEntrada")
        self.btn_livro_entradas.setCursor(Qt.PointingHandCursor)
        self.btn_livro_entradas.setMinimumHeight(34)
        self.btn_livro_entradas.setEnabled(False)
        self.btn_livro_entradas.clicked.connect(
            lambda: self.page.executar_livro_transit("ENTRADA")
        )
        livro_btns.addWidget(self.btn_livro_entradas, 0)

        self.btn_livro_saidas = QPushButton("Extrair Saídas Transitórias")
        self.btn_livro_saidas.setObjectName("ExtractBtnLivroSaida")
        self.btn_livro_saidas.setCursor(Qt.PointingHandCursor)
        self.btn_livro_saidas.setMinimumHeight(34)
        self.btn_livro_saidas.setEnabled(False)
        self.btn_livro_saidas.clicked.connect(
            lambda: self.page.executar_livro_transit("SAIDA")
        )
        livro_btns.addWidget(self.btn_livro_saidas, 0)

        lc_outer.addLayout(livro_btns)

        # Reage a mudanças no campo do Livro Fiscal: habilita/desabilita botões
        self.path_livro.input.textChanged.connect(self.page._on_livro_path_changed)

        lay.addWidget(livro_card, 1)

    def _sel_razoes(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta com TXTs de razão")
        if p:
            self.path_razoes.input.setText(p)


# =====================================================================
# Aba 2: Validação contra Balancete
# =====================================================================
class _TabValidacao(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 0)
        root.setSpacing(0)

        inner_card = HoverCard()
        inner_card.setObjectName("PremiumPathCard")
        inner_card.setAttribute(Qt.WA_StyledBackground, True)
        inner_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(inner_card, 1)

        lay = QVBoxLayout(inner_card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # ---- Cache info ----
        self.cache_label = QLabel("Nenhum razão consolidado em cache.")
        self.cache_label.setObjectName("FieldText")
        self.cache_label.setWordWrap(True)
        lay.addWidget(self.cache_label)

        # ---- Caminho do balancete ----
        self.path_balancete = CompactPathRow(
            "Balancete:", "Arquivo .xlsx, .xlsb ou .csv",
            "Selecionar", None,
            is_file=True,
            file_filter="Planilhas (*.xlsx *.xlsb *.csv);;Todos (*.*)",
        )
        lay.addWidget(self.path_balancete)

        # ---- Botão validar ----
        val_row = QHBoxLayout()
        val_row.setSpacing(8)
        val_row.setContentsMargins(0, 2, 0, 2)
        self.btn_validar = QPushButton("Validar contra Balancete")
        self.btn_validar.setObjectName("PrimaryButton")
        self.btn_validar.setEnabled(False)
        self.btn_validar.clicked.connect(self.page.executar_validacao)
        val_row.addWidget(self.btn_validar, 0)
        val_row.addStretch(1)
        lay.addLayout(val_row)

        # ---- Card resultado: tabela de divergências ----
        res_card = QFrame()
        res_card.setObjectName("DivisoesCard")
        res_card.setAttribute(Qt.WA_StyledBackground, True)
        res_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rc_lay = QVBoxLayout(res_card)
        rc_lay.setContentsMargins(14, 10, 14, 10)
        rc_lay.setSpacing(6)

        rc_row1 = QHBoxLayout()
        rc_row1.setSpacing(8)
        rc_row1.setContentsMargins(0, 0, 0, 0)

        res_icon = QFrame()
        res_icon.setObjectName("AnaliseIconFrame")
        res_icon.setFixedSize(24, 24)
        ri_lay = QVBoxLayout(res_icon)
        ri_lay.setContentsMargins(0, 0, 0, 0)
        ri_lb = QLabel("VAL")
        ri_lb.setAlignment(Qt.AlignCenter)
        ri_lb.setStyleSheet(
            "font-size:8px; font-weight:800; color:#FFF; background:transparent;"
        )
        ri_lay.addWidget(ri_lb)
        rc_row1.addWidget(res_icon, 0, Qt.AlignVCenter)

        rt = QLabel("Resultado da Validação")
        rt.setObjectName("FieldTitle")
        rc_row1.addWidget(rt, 0, Qt.AlignVCenter)

        self.res_info = QLabel("Importe um balancete e clique em Validar.")
        self.res_info.setObjectName("FieldText")
        rc_row1.addWidget(self.res_info, 1, Qt.AlignVCenter)

        # Toggle: mostrar só razão vs todas
        self.btn_mostrar_todas = QPushButton("Mostrar todas")
        self.btn_mostrar_todas.setObjectName("DivActionBtn")
        self.btn_mostrar_todas.setCursor(Qt.PointingHandCursor)
        self.btn_mostrar_todas.setCheckable(True)
        self.btn_mostrar_todas.setEnabled(False)
        self.btn_mostrar_todas.toggled.connect(self.page._toggle_mostrar_todas)
        rc_row1.addWidget(self.btn_mostrar_todas, 0, Qt.AlignVCenter)

        # Botão exportar (habilita após validação)
        self.btn_exportar_res = QPushButton("Exportar resultado")
        self.btn_exportar_res.setObjectName("DivExportBtn")
        self.btn_exportar_res.setCursor(Qt.PointingHandCursor)
        self.btn_exportar_res.setEnabled(False)
        self.btn_exportar_res.clicked.connect(self.page.exportar_resultado)
        rc_row1.addWidget(self.btn_exportar_res, 0, Qt.AlignVCenter)

        rc_lay.addLayout(rc_row1)

        # Tabela
        self.tabela = QTableWidget()
        self.tabela.setObjectName("ValidTable")
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(
            ["Conta", "Razão (R$)", "Balancete (R$)", "Diferença (R$)", "Status"]
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setShowGrid(False)
        hh = self.tabela.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        rc_lay.addWidget(self.tabela, 1)

        lay.addWidget(res_card, 1)


# =====================================================================
# Página principal
# =====================================================================
class IcmsTransitoriasPage(QWidget):
    def __init__(self):
        super().__init__()
        self.consolidator_worker = None
        self.validacao_worker = None
        self.parquet_razoes_path = None
        self._last_layout_mode = None
        # Flag de sessão: True só depois que o usuário rodar a Consolidação
        # nesta abertura do app. Assim a UI não habilita os botões de
        # extração WE/WL com base num cache antigo da máquina.
        self._consolidado_nesta_sessao = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("PageCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(card, 1)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(6)

        # ---- Hero (mesmo estilo do ZTMM) ----
        hero = QFrame()
        hero.setObjectName("PageHeroCard")
        hero.setAttribute(Qt.WA_StyledBackground, True)
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(16, 12, 16, 12)
        hero_lay.setSpacing(10)

        hero_icon = QFrame()
        hero_icon.setObjectName("AnaliseIconFrame")
        hero_icon.setFixedSize(36, 36)
        hi_lay = QVBoxLayout(hero_icon)
        hi_lay.setContentsMargins(0, 0, 0, 0)
        hi_lb = QLabel("ICM")
        hi_lb.setObjectName("AnaliseIconText")
        hi_lb.setAlignment(Qt.AlignCenter)
        hi_lay.addWidget(hi_lb)
        hero_lay.addWidget(hero_icon, 0, Qt.AlignVCenter)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        ht1 = QLabel("ICMS Transitórias")
        ht1.setObjectName("SectionTitle")
        ht1.setStyleSheet(
            "font-size:17px; font-weight:800; color:#182235; background:transparent;"
        )
        hero_text.addWidget(ht1)
        ht2 = QLabel(
            "Consolide os razões SAP de contas transitórias e valide os "
            "movimentos contra o balancete do mesmo período."
        )
        ht2.setObjectName("FieldText")
        ht2.setWordWrap(True)
        hero_text.addWidget(ht2)
        hero_lay.addLayout(hero_text, 1)

        outer.addWidget(hero)

        # ---- Tabs ----
        self.tabs = QTabWidget()
        self.tabs.setObjectName("ZtmmTabs")
        self.tabs.setDocumentMode(True)

        self.tab_cons = _TabConsolidacao(self)
        self.tab_valid = _TabValidacao(self)

        self.tabs.addTab(self.tab_cons, "Consolidação Razões")
        self.tabs.addTab(self.tab_valid, "Validação x Balancete")

        outer.addWidget(self.tabs, 1)

        # OBS: o fade-in via QGraphicsOpacityEffect estava causando os botões
        # "desaparecerem" quando o usuário abria o file dialog (conflito de
        # re-render). Mantemos só o efeito do stylesheet (disabled cinza ⇄
        # enabled cor viva) — visualmente claro e sem efeitos colaterais.

        # ---- Bottom: progresso + log + summary (responsivo) ----
        self.bottom_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(10)

        # Painel esquerdo
        left_panel = QFrame()
        left_panel.setObjectName("TransparentPanel")
        left_panel.setAttribute(Qt.WA_StyledBackground, True)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_col = QVBoxLayout(left_panel)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(8)

        # Progresso compacto
        prog_card = HoverCard()
        prog_card.setObjectName("PremiumExecCard")
        prog_card.setAttribute(Qt.WA_StyledBackground, True)
        prog_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        pl_ = QVBoxLayout(prog_card)
        pl_.setContentsMargins(10, 6, 10, 6)
        pl_.setSpacing(3)

        pa = QFrame()
        pa.setObjectName("CardAccentLine")
        pa.setAttribute(Qt.WA_StyledBackground, True)
        pa.setFixedHeight(2)
        pl_.addWidget(pa)

        prog_top = QHBoxLayout()
        prog_top.setSpacing(8)
        pe = QLabel("ANDAMENTO")
        pe.setObjectName("SectionEyebrow")
        prog_top.addWidget(pe, 0)
        self.status_texto = QLabel("Aguardando início...")
        self.status_texto.setObjectName("InfoValue")
        self.status_texto.setWordWrap(True)
        prog_top.addWidget(self.status_texto, 1)
        self.progresso_texto = QLabel("0 / 0")
        self.progresso_texto.setObjectName("FieldText")
        prog_top.addWidget(self.progresso_texto, 0)
        pl_.addLayout(prog_top)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(12)
        pl_.addWidget(self.progress)

        left_col.addWidget(prog_card, 0)

        # Log — altura limitada pra não roubar espaço dos cards de cima
        log_card = HoverCard()
        log_card.setObjectName("PremiumLogCard")
        log_card.setAttribute(Qt.WA_StyledBackground, True)
        log_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        log_card.setMaximumHeight(150)
        ll_ = QVBoxLayout(log_card)
        ll_.setContentsMargins(10, 6, 10, 6)
        ll_.setSpacing(4)

        la = QFrame()
        la.setObjectName("CardAccentLine")
        la.setAttribute(Qt.WA_StyledBackground, True)
        la.setFixedHeight(2)
        ll_.addWidget(la)

        lh = QLabel("SAÍDA DO PROCESSO")
        lh.setObjectName("SectionEyebrow")
        ll_.addWidget(lh)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("Os logs aparecerão aqui.")
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ll_.addWidget(self.saida, 1)

        left_col.addWidget(log_card, 0)

        self.bottom_layout.addWidget(left_panel, 1)

        # Painel direito: summary — também limitado em altura
        self.summary = HoverCard()
        self.summary.setObjectName("PremiumSummaryCard")
        self.summary.setAttribute(Qt.WA_StyledBackground, True)
        self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.summary.setMinimumWidth(220)
        self.summary.setMaximumWidth(380)
        self.summary.setMaximumHeight(180)

        sm_lay = QVBoxLayout(self.summary)
        sm_lay.setContentsMargins(10, 8, 10, 8)
        sm_lay.setSpacing(6)

        sa = QFrame()
        sa.setObjectName("CardAccentLine")
        sa.setAttribute(Qt.WA_StyledBackground, True)
        sa.setFixedHeight(2)
        sm_lay.addWidget(sa)

        sl = QLabel("RESUMO")
        sl.setObjectName("SectionEyebrow")
        sm_lay.addWidget(sl)

        self.metric_grid = ResponsiveGrid(min_item_width=160)
        self.metric_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.metric_linhas = MetricBox("Linhas razão")
        self.metric_contas = MetricBox("Contas")
        self.metric_batendo = MetricBox("Batendo")
        self.metric_diverg = MetricBox("Divergentes")
        self.metric_grid.addItemWidget(self.metric_linhas)
        self.metric_grid.addItemWidget(self.metric_contas)
        self.metric_grid.addItemWidget(self.metric_batendo)
        self.metric_grid.addItemWidget(self.metric_diverg)
        sm_lay.addWidget(self.metric_grid)

        self.bottom_layout.addWidget(self.summary, 0)
        outer.addLayout(self.bottom_layout, 0)

        self._carregar_cache()

    # ---- Lifecycle ----

    def showEvent(self, event):
        super().showEvent(event)
        self._carregar_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    # ---- Responsividade ----

    def _apply_responsive(self):
        w = self.width()
        vertical = w < 920
        if self._last_layout_mode != vertical:
            self._last_layout_mode = vertical
            if vertical:
                self.bottom_layout.setDirection(QBoxLayout.TopToBottom)
                self.bottom_layout.setSpacing(8)
                self.summary.setMinimumWidth(0)
                self.summary.setMaximumWidth(16777215)
                self.summary.setSizePolicy(
                    QSizePolicy.Expanding, QSizePolicy.Preferred
                )
            else:
                self.bottom_layout.setDirection(QBoxLayout.LeftToRight)
                self.bottom_layout.setSpacing(10)
                sm_max = max(280, min(380, int(w * 0.28)))
                self.summary.setMinimumWidth(240)
                self.summary.setMaximumWidth(sm_max)
                self.summary.setSizePolicy(
                    QSizePolicy.Preferred, QSizePolicy.Preferred
                )

    # ---- Cache ----

    def _carregar_cache(self):
        """Carrega o estado do cache de razões. Comportamento intencional:

        - Btn Validar  : habilita se parquet em disco existe (validação
                          consegue rodar a partir do cache antigo).
        - Btn Extrair WE/WL/Both : NÃO habilita por cache; só fica vivo
                                    depois de rodar a Consolidação nesta
                                    mesma sessão (flag _consolidado_nesta_sessao).
        - Métricas do Resumo: nunca populadas automaticamente — só após ação.
        """
        meta = carregar_meta_transitorias()
        if meta and Path(meta.get("parquet_path", "")).exists():
            self.parquet_razoes_path = meta["parquet_path"]
            total_linhas = meta.get("total_linhas", 0)
            total_contas = meta.get("total_contas", 0)
            self.tab_valid.cache_label.setText(
                f"Razões em cache: {total_linhas:,} linhas, "
                f"{total_contas} contas — "
                f"consolidado em {meta.get('data_processamento', '?')}"
            )
            self.tab_valid.btn_validar.setEnabled(True)
        else:
            self.parquet_razoes_path = None
            self.tab_valid.cache_label.setText(
                "Nenhum razão consolidado em cache."
            )
            self.tab_valid.btn_validar.setEnabled(False)

        # Os botões de extração só ficam vivos após Consolidação nesta sessão.
        extract_ok = self._consolidado_nesta_sessao and bool(self.parquet_razoes_path)
        self.tab_cons.btn_extrair_we.setEnabled(extract_ok)
        self.tab_cons.btn_extrair_wl.setEnabled(extract_ok)
        self.tab_cons.btn_extrair_both.setEnabled(extract_ok)

    def _on_livro_path_changed(self, txt):
        """Habilita os botões de Transitórias do Livro só quando o caminho
        aponta pra um arquivo existente."""
        valido = bool(txt and Path(txt.strip()).is_file())
        self.tab_cons.btn_livro_entradas.setEnabled(valido)
        self.tab_cons.btn_livro_saidas.setEnabled(valido)

    # ---- Helpers ----

    def _set_buttons_enabled(self, enabled):
        self.tab_cons.btn_consolidar.setEnabled(enabled)
        # Validação só precisa do parquet em disco — o cache antigo já basta.
        tem_cache = bool(enabled and self.parquet_razoes_path)
        self.tab_valid.btn_validar.setEnabled(tem_cache)
        # Extração WE/WL/Both só fica viva depois da Consolidação NESTA sessão.
        extract_ok = bool(
            enabled and self._consolidado_nesta_sessao and self.parquet_razoes_path
        )
        self.tab_cons.btn_extrair_we.setEnabled(extract_ok)
        self.tab_cons.btn_extrair_wl.setEnabled(extract_ok)
        self.tab_cons.btn_extrair_both.setEnabled(extract_ok)

    def atualizar(self, etapa, atual, total, detalhe):
        if total > 0:
            pct = int((atual / total) * 100)
            self.progress.setValue(pct)
            self.progresso_texto.setText(f"{atual} / {total}")
        self.status_texto.setText(f"[{etapa}] {detalhe}")
        self.saida.append(f"[{etapa}] ({atual}/{total}) {detalhe}")

    # ---- Consolidação ----

    def executar_consolidacao(self):
        pasta = self.tab_cons.path_razoes.input.text().strip()
        if not pasta or not os.path.isdir(pasta):
            QMessageBox.critical(
                self, "Erro",
                "Selecione uma pasta válida com os TXTs de razão."
            )
            return

        self._set_buttons_enabled(False)
        self.status_texto.setText("Consolidando razões...")
        self.saida.clear()
        self.progress.setValue(0)

        self.consolidator_worker = TransitConsolidatorWorker(
            pasta, machine_id=get_machine_id()
        )
        self.consolidator_worker.progresso.connect(self.atualizar)
        self.consolidator_worker.sucesso.connect(self._consolidacao_sucesso)
        self.consolidator_worker.erro.connect(self._consolidacao_erro)
        self.consolidator_worker.start()

    def _consolidacao_sucesso(self, resultado):
        # Marca que a Consolidação rodou com sucesso nesta sessão — só
        # depois disso os botões de extração WE/WL/Both ficam ativos.
        self._consolidado_nesta_sessao = True
        self.parquet_razoes_path = resultado["parquet_path"]
        self._set_buttons_enabled(True)
        self._carregar_cache()
        # Popula métricas do resumo SOMENTE após uma ação concluída na sessão
        self.metric_linhas.lb_v.setText(
            f"{resultado['total_linhas']:,}".replace(",", ".")
        )
        self.metric_contas.lb_v.setText(str(resultado["total_contas"]))
        self.atualizar(
            "finalizado", 1, 1,
            f"Consolidado em {resultado.get('tempo_s', '?')}s"
        )
        QMessageBox.information(
            self, "Sucesso",
            f"Razões consolidados.\n\n"
            f"Linhas: {resultado['total_linhas']:,}\n"
            f"Contas: {resultado['total_contas']}\n"
            f"Tempo: {resultado.get('tempo_s', '?')}s\n\n"
            f"Base: {resultado['parquet_path']}"
        )

    def _consolidacao_erro(self, erro):
        self._set_buttons_enabled(True)
        self.status_texto.setText("Falha na consolidação.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    # ---- Validação ----

    def executar_validacao(self):
        if not self.parquet_razoes_path or not Path(self.parquet_razoes_path).exists():
            QMessageBox.critical(
                self, "Erro",
                "Nenhum razão consolidado em cache. Faça a consolidação primeiro."
            )
            return
        balancete = self.tab_valid.path_balancete.input.text().strip()
        if not balancete or not os.path.isfile(balancete):
            QMessageBox.critical(
                self, "Erro",
                "Selecione um arquivo válido de balancete (.xlsx, .xlsb ou .csv)."
            )
            return

        self._set_buttons_enabled(False)
        self.tab_valid.btn_exportar_res.setEnabled(False)
        self.status_texto.setText("Validando contra balancete...")
        self.saida.clear()
        self.progress.setValue(0)

        self.validacao_worker = TransitValidacaoWorker(
            self.parquet_razoes_path,
            balancete,
            machine_id=get_machine_id(),
        )
        self.validacao_worker.progresso.connect(self.atualizar)
        self.validacao_worker.sucesso.connect(self._validacao_sucesso)
        self.validacao_worker.erro.connect(self._validacao_erro)
        self.validacao_worker.start()

    def _validacao_sucesso(self, resultado):
        self._set_buttons_enabled(True)
        self.metric_batendo.lb_v.setText(str(resultado["batendo"]))
        self.metric_diverg.lb_v.setText(str(resultado["divergentes"]))
        self.tab_valid.res_info.setText(
            f"{resultado['total_contas']} contas comparadas | "
            f"{resultado['batendo']} OK | "
            f"{resultado['divergentes']} divergentes | "
            f"{resultado['ausentes_balancete']} só no razão | "
            f"{resultado['ausentes_razao']} só no balancete"
        )

        # Guarda o caminho pra alternar visualização sem reler o parquet
        self._parquet_validacao = resultado["parquet_validacao"]
        # Por padrão mostra só as contas com movimento no razão (10-20 linhas).
        # Evita popular 3000+ linhas no QTableWidget e travar a UI.
        self.tab_valid.btn_mostrar_todas.setEnabled(True)
        self.tab_valid.btn_mostrar_todas.setChecked(False)
        self.tab_valid.btn_mostrar_todas.setText("Mostrar todas")
        self._popular_tabela(self._parquet_validacao, somente_razao=True)
        self.tab_valid.btn_exportar_res.setEnabled(True)

        self.atualizar(
            "finalizado", 1, 1,
            f"Validação concluída em {resultado.get('tempo_s', '?')}s"
        )
        # Pula direto pra aba de validação se o usuário não estiver lá
        self.tabs.setCurrentIndex(1)

    def _validacao_erro(self, erro):
        self._set_buttons_enabled(True)
        self.status_texto.setText("Falha na validação.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    def _toggle_mostrar_todas(self, checked):
        if not getattr(self, "_parquet_validacao", None):
            return
        self.tab_valid.btn_mostrar_todas.setText(
            "Mostrar só com movimento" if checked else "Mostrar todas"
        )
        self._popular_tabela(self._parquet_validacao, somente_razao=not checked)

    def _popular_tabela(self, parquet_path, somente_razao=True):
        df = pl.read_parquet(parquet_path)

        if somente_razao:
            df = df.filter(pl.col("Soma_Razao") != 0)

        # Ordena: primeiro divergentes/anômalos, depois OK; dentro de cada
        # grupo, por Conta crescente.
        df = (
            df.with_columns((pl.col("Status") != "OK").alias("__nao_ok"))
              .sort(["__nao_ok", "Conta"], descending=[True, False])
              .drop("__nao_ok")
        )

        # Performance: setUpdatesEnabled(False) durante o bulk-insert evita
        # repaints intermediários. Faz diferença grande pra tabelas grandes.
        tabela = self.tab_valid.tabela
        tabela.setSortingEnabled(False)
        tabela.setUpdatesEnabled(False)
        try:
            tabela.clearContents()
            tabela.setRowCount(df.height)

            for row_idx, row in enumerate(df.iter_rows(named=True)):
                conta = str(row["Conta"])
                razao = float(row["Soma_Razao"] or 0.0)
                balancete = float(row["Soma_Balancete"] or 0.0)
                diff = float(row["Diferenca"] or 0.0)
                status = str(row["Status"])

                it_conta = QTableWidgetItem(conta)
                it_conta.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                it_raz = QTableWidgetItem(_fmt_brl(razao))
                it_raz.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                it_bal = QTableWidgetItem(_fmt_brl(balancete))
                it_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                it_diff = QTableWidgetItem(_fmt_brl(diff))
                it_diff.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                it_st = QTableWidgetItem(status)
                it_st.setTextAlignment(Qt.AlignCenter)
                if status == "OK":
                    it_st.setForeground(Qt.darkGreen)
                else:
                    it_st.setForeground(Qt.darkRed)

                tabela.setItem(row_idx, 0, it_conta)
                tabela.setItem(row_idx, 1, it_raz)
                tabela.setItem(row_idx, 2, it_bal)
                tabela.setItem(row_idx, 3, it_diff)
                tabela.setItem(row_idx, 4, it_st)
        finally:
            tabela.setUpdatesEnabled(True)

    # ---- Extração AA (Chave_02 / WE / WL) ----

    def executar_extracao_aa(self, tipo_filtro):
        """tipo_filtro: 'WE', 'WL' ou 'BOTH'."""
        if not self.parquet_razoes_path or not Path(self.parquet_razoes_path).exists():
            QMessageBox.critical(
                self, "Erro",
                "Nenhum razão consolidado em cache. Faça a consolidação primeiro."
            )
            return

        # Sugere nome de arquivo conforme o tipo. Default em XLSB porque é
        # ~5-10x mais rápido que XLSX para volumes grandes (a extração WE/WL
        # facilmente passa de 300k linhas).
        rotulos = {"WE": "WE", "WL": "WL", "BOTH": "WE_WL"}
        rotulo = rotulos.get(tipo_filtro, "EXTR")
        sugestao = f"Razões_Conciliados_{rotulo}.xlsb"

        destino, _ = QFileDialog.getSaveFileName(
            self, f"Salvar extração {rotulo}",
            sugestao,
            "Excel binário rápido (*.xlsb);;Excel (*.xlsx);;CSV (*.csv)",
        )
        if not destino:
            return

        self._set_buttons_enabled(False)
        self.status_texto.setText(f"Extraindo conciliados ({rotulo})...")
        self.saida.clear()
        self.progress.setValue(0)

        self.extracao_worker = TransitExtracaoAAWorker(
            self.parquet_razoes_path,
            destino,
            tipo_filtro,
            machine_id=get_machine_id(),
        )
        self.extracao_worker.progresso.connect(self.atualizar)
        self.extracao_worker.sucesso.connect(self._extracao_aa_sucesso)
        self.extracao_worker.erro.connect(self._extracao_aa_erro)
        self.extracao_worker.start()

    def _extracao_aa_sucesso(self, resultado):
        self._set_buttons_enabled(True)
        self.atualizar(
            "finalizado", 1, 1,
            f"Extração concluída em {resultado.get('tempo_s', '?')}s"
        )
        QMessageBox.information(
            self, "Sucesso",
            f"Extração {resultado['rotulo_tipo']} concluída.\n\n"
            f"Linhas conciliadas: {resultado['linhas']:,}\n"
            f"Tipos: {', '.join(resultado['tipos'])}\n"
            f"Tempo: {resultado.get('tempo_s', '?')}s\n\n"
            f"Arquivo: {resultado['destino']}"
        )

    def _extracao_aa_erro(self, erro):
        self._set_buttons_enabled(True)
        self.status_texto.setText("Falha na extração.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    # ---- Extração de Transitórias do Livro Fiscal ----

    def executar_livro_transit(self, tipo_movimento):
        """tipo_movimento: 'ENTRADA' ou 'SAIDA'."""
        livro = self.tab_cons.path_livro.input.text().strip()
        if not livro or not Path(livro).is_file():
            QMessageBox.critical(
                self, "Erro",
                "Selecione um arquivo de livro fiscal válido (xlsx, xlsb, csv ou parquet)."
            )
            return

        # Sugere nome no padrão "Entrada_Transitórias_<periodo>.xlsb" /
        # "Saída_Transitórias_<periodo>.xlsb". Se ainda não soubermos o
        # período (vamos descobrir só ao ler o livro), deixa um placeholder
        # — o nome final é só sugestão de Save dialog mesmo.
        rotulo = "Entrada" if tipo_movimento == "ENTRADA" else "Saída"
        sugestao_nome = f"{rotulo}_Transitórias.xlsb"
        # Tenta partir da pasta do livro pra facilitar a vida
        pasta_padrao = str(Path(livro).parent / sugestao_nome)

        destino, _ = QFileDialog.getSaveFileName(
            self,
            f"Salvar {rotulo} Transitórias",
            pasta_padrao,
            "Excel binário rápido (*.xlsb);;Excel (*.xlsx);;CSV (*.csv)",
        )
        if not destino:
            return

        self._set_buttons_enabled(False)
        self.tab_cons.btn_livro_entradas.setEnabled(False)
        self.tab_cons.btn_livro_saidas.setEnabled(False)
        self.status_texto.setText(f"Extraindo {rotulo} Transitórias...")
        self.saida.clear()
        self.progress.setValue(0)

        self.livro_worker = TransitLivroExtractWorker(
            livro,
            destino,
            tipo_movimento,
            machine_id=get_machine_id(),
        )
        self.livro_worker.progresso.connect(self.atualizar)
        self.livro_worker.sucesso.connect(self._livro_transit_sucesso)
        self.livro_worker.erro.connect(self._livro_transit_erro)
        self.livro_worker.start()

    def _livro_transit_sucesso(self, resultado):
        self._set_buttons_enabled(True)
        self.tab_cons.btn_livro_entradas.setEnabled(True)
        self.tab_cons.btn_livro_saidas.setEnabled(True)

        # Renomeia o arquivo final para incluir o período descoberto a partir
        # dos dados (ex: "Entrada_Transitórias_03_2026.xlsb"), respeitando a
        # extensão escolhida pelo usuário.
        destino_atual = Path(resultado["destino"])
        rotulo = resultado["tipo"]
        periodo = resultado.get("periodo", "PERIODO")
        nome_alvo = f"{rotulo}_Transitórias_{periodo}{destino_atual.suffix}"
        destino_final = destino_atual.with_name(nome_alvo)
        try:
            if destino_final != destino_atual:
                if destino_final.exists():
                    destino_final.unlink()
                destino_atual.rename(destino_final)
                resultado["destino"] = str(destino_final)
        except Exception:
            # Se não conseguir renomear (ex: permissão), mantém o nome original
            pass

        self.atualizar(
            "finalizado", 1, 1,
            f"Extração concluída em {resultado.get('tempo_s', '?')}s"
        )
        QMessageBox.information(
            self, "Sucesso",
            f"{rotulo} Transitórias extraídas.\n\n"
            f"Linhas: {resultado['linhas']:,}\n"
            f"Período: {periodo}\n"
            f"Tempo: {resultado.get('tempo_s', '?')}s\n\n"
            f"Arquivo: {resultado['destino']}"
        )

    def _livro_transit_erro(self, erro):
        self._set_buttons_enabled(True)
        self.tab_cons.btn_livro_entradas.setEnabled(True)
        self.tab_cons.btn_livro_saidas.setEnabled(True)
        self.status_texto.setText("Falha na extração do livro.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    def exportar_resultado(self):
        if not Path(CACHE_TRANSIT_VALID).exists():
            QMessageBox.critical(
                self, "Erro", "Nenhum resultado de validação em cache."
            )
            return
        destino, _ = QFileDialog.getSaveFileName(
            self, "Salvar resultado",
            "ICMS_Transitorias_Validacao.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)",
        )
        if not destino:
            return

        df = pl.read_parquet(CACHE_TRANSIT_VALID)
        try:
            if destino.lower().endswith(".csv"):
                df.write_csv(destino, separator=";", include_bom=True)
            else:
                df.write_excel(destino)
            QMessageBox.information(self, "Sucesso", f"Exportado:\n{destino}")
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Falha ao exportar:\n{e}"
            )


def _fmt_brl(v):
    """Formata número como BRL: 1.234,56."""
    if v is None:
        return ""
    try:
        s = f"{v:,.2f}"
        # converte 1,234.56 -> 1.234,56
        s = s.replace(",", "_TMP_").replace(".", ",").replace("_TMP_", ".")
        return s
    except Exception:
        return str(v)
