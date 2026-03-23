#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QTextEdit, QSizePolicy, QProgressBar,
    QBoxLayout, QLineEdit, QTabWidget, QLayout, QGraphicsDropShadowEffect,
)
from workers.ztmm_worker import ZtmmConsolidatorWorker, ZtmmExportWorker, ZtmmAnaliseWorker
from ztmm_logic import carregar_meta_ztmm
from pages.p9_page import MetricBox, HoverCard, ResponsiveGrid


# ================================================================
# FlowLayout — layout que faz wrap automático como texto
# ================================================================
class FlowLayout(QLayout):
    def __init__(self, parent=None, h_spacing=6, v_spacing=6):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        s += QSize(m.left() + m.right(), m.top() + m.bottom())
        return s

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            sz = item.sizeHint()
            next_x = x + sz.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._v_spacing
                next_x = x + sz.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sz))
            x = next_x
            line_height = max(line_height, sz.height())

        return y + line_height - rect.y() + m.bottom()


# ================================================================
# DivChip — chip toggle para divisão
# ================================================================
class DivChip(QPushButton):
    def __init__(self, divisao_text):
        super().__init__(divisao_text)
        self._selected = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("DivChip")
        self.clicked.connect(self._on_toggle)

    def sizeHint(self):
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self.text()) + 20
        h = fm.height() + 10
        return QSize(max(40, w), max(20, h))

    def _on_toggle(self):
        self._selected = self.isChecked()

    def is_selected(self):
        return self._selected

    def set_selected(self, val):
        self._selected = val
        self.setChecked(val)


# ================================================================
# Widget compacto: linha de seleção (label + input + botão)
# ================================================================
class CompactPathRow(QWidget):
    def __init__(self, label_text, placeholder, btn_text, on_click, is_file=False, file_filter=""):
        super().__init__()
        self.is_file = is_file
        self.file_filter = file_filter
        self._on_click = on_click

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lb = QLabel(label_text)
        lb.setObjectName("FieldTitle")
        lb.setMinimumWidth(90)
        lb.setMaximumWidth(140)
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
            path, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", "", self.file_filter)
            if path:
                self.input.setText(path)
        else:
            self._on_click()


# ================================================================
# Aba: Consolidação ZTMM
# ================================================================
class _TabConsolidacao(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setStyleSheet("_TabConsolidacao { background: transparent; }")

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
        lay.setSpacing(6)

        # ---- Paths compactos ----
        self.path_base = CompactPathRow(
            "Base ZTMM:", "Pasta com TXTs SAP",
            "Selecionar", self._sel_base,
        )
        self.path_destino = CompactPathRow(
            "Destino:", "Pasta de exportação",
            "Selecionar", self._sel_destino,
        )
        lay.addWidget(self.path_base)
        lay.addWidget(self.path_destino)

        # ---- Botão consolidar ----
        cons_row = QHBoxLayout()
        cons_row.setSpacing(8)
        cons_row.setContentsMargins(0, 2, 0, 2)
        self.btn_consolidar = QPushButton("Consolidar ZTMM")
        self.btn_consolidar.setObjectName("PrimaryButton")
        self.btn_consolidar.clicked.connect(self.page.executar_consolidacao)
        cons_row.addWidget(self.btn_consolidar, 0)
        cons_row.addStretch(1)
        lay.addLayout(cons_row)

        # ---- Card de divisões premium ----
        div_card = QFrame()
        div_card.setObjectName("DivisoesCard")
        div_card.setAttribute(Qt.WA_StyledBackground, True)
        div_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        dc_lay = QVBoxLayout(div_card)
        dc_lay.setContentsMargins(14, 10, 14, 10)
        dc_lay.setSpacing(6)

        # Linha 1: ícone + título + info
        dc_row1 = QHBoxLayout()
        dc_row1.setSpacing(8)
        dc_row1.setContentsMargins(0, 0, 0, 0)

        div_icon = QFrame()
        div_icon.setObjectName("AnaliseIconFrame")
        div_icon.setFixedSize(24, 24)
        di_lay = QVBoxLayout(div_icon)
        di_lay.setContentsMargins(0, 0, 0, 0)
        di_lb = QLabel("CSV")
        di_lb.setObjectName("AnaliseIconText")
        di_lb.setAlignment(Qt.AlignCenter)
        di_lb.setStyleSheet("font-size:8px; font-weight:800; color:#FFF; background:transparent;")
        di_lay.addWidget(di_lb)
        dc_row1.addWidget(div_icon, 0, Qt.AlignVCenter)

        dc_t = QLabel("Exportar por Divisão")
        dc_t.setObjectName("FieldTitle")
        dc_row1.addWidget(dc_t, 0, Qt.AlignVCenter)

        self.div_info = QLabel("Consolide os TXTs primeiro.")
        self.div_info.setObjectName("FieldText")
        dc_row1.addWidget(self.div_info, 1, Qt.AlignVCenter)

        # Botões compactos na mesma linha do header
        self.btn_select_all = QPushButton("Selecionar tudo")
        self.btn_select_all.setObjectName("DivActionBtn")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self._toggle_select_all)
        dc_row1.addWidget(self.btn_select_all, 0, Qt.AlignVCenter)

        self.btn_exportar = QPushButton("Exportar CSV")
        self.btn_exportar.setObjectName("DivExportBtn")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.setEnabled(False)
        self.btn_exportar.clicked.connect(self.page.executar_exportacao)
        dc_row1.addWidget(self.btn_exportar, 0, Qt.AlignVCenter)

        dc_lay.addLayout(dc_row1)

        # Linha 2: chips (flow layout, ocupa todo o espaço restante)
        self.chips_container = QWidget()
        self.chips_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chips_flow = FlowLayout(self.chips_container, h_spacing=5, v_spacing=5)
        self.chips_flow.setContentsMargins(0, 0, 0, 0)
        dc_lay.addWidget(self.chips_container, 1)

        lay.addWidget(div_card, 1)

        self._all_selected = False
        self._div_chips = []

    def _toggle_select_all(self):
        self._all_selected = not self._all_selected
        for chip in self._div_chips:
            chip.set_selected(self._all_selected)
        self.btn_select_all.setText("Desmarcar tudo" if self._all_selected else "Selecionar tudo")

    def get_selected_divisoes(self):
        return [chip.text() for chip in self._div_chips if chip.is_selected()]

    def _sel_base(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta com TXTs ZTMM")
        if p:
            self.path_base.input.setText(p)

    def _sel_destino(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta de destino")
        if p:
            self.path_destino.input.setText(p)


# ================================================================
# Aba: Análise ZTMM x Livro
# ================================================================
class _TabAnalise(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setStyleSheet("_TabAnalise { background: transparent; }")

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
        lay.setSpacing(6)

        # ---- Cache info ----
        self.cache_label = QLabel("Nenhuma base ZTMM consolidada em cache.")
        self.cache_label.setObjectName("FieldText")
        self.cache_label.setWordWrap(True)
        lay.addWidget(self.cache_label)

        # ---- Paths compactos ----
        self.path_nc = CompactPathRow(
            "Arquivo NC:", "Não Conciliados (.parquet ou .csv)",
            "Selecionar", None,
            is_file=True, file_filter="Parquet ou CSV (*.parquet *.csv)",
        )
        self.path_razoes = CompactPathRow(
            "Razões:", "Pasta com CSVs 222/223",
            "Selecionar", self._sel_razoes,
        )
        self.path_destino = CompactPathRow(
            "Destino:", "Pasta de saída",
            "Selecionar", self._sel_destino,
        )
        lay.addWidget(self.path_nc)
        lay.addWidget(self.path_razoes)
        lay.addWidget(self.path_destino)

        # ---- Painel de ação premium ----
        action_card = HoverCard()
        action_card.setObjectName("AnaliseActionCard")
        action_card.setAttribute(Qt.WA_StyledBackground, True)
        action_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        ac_outer = QHBoxLayout(action_card)
        ac_outer.setContentsMargins(10, 8, 10, 8)
        ac_outer.setSpacing(8)

        # Ícone à esquerda (fixo, alinhado ao topo)
        icon_frame = QFrame()
        icon_frame.setObjectName("AnaliseIconFrame")
        icon_frame.setFixedSize(22, 22)
        i_lay = QVBoxLayout(icon_frame)
        i_lay.setContentsMargins(0, 0, 0, 0)
        i_lb = QLabel("ZTM")
        i_lb.setAlignment(Qt.AlignCenter)
        i_lb.setStyleSheet("font-size:7px; font-weight:800; color:#FFF; background:transparent;")
        i_lay.addWidget(i_lb)
        ac_outer.addWidget(icon_frame, 0, Qt.AlignTop)

        # Conteúdo à direita do ícone
        ac_right = QVBoxLayout()
        ac_right.setSpacing(3)
        ac_right.setContentsMargins(0, 0, 0, 0)

        info_t = QLabel("Conciliação automática")
        info_t.setStyleSheet("font-size:11px; font-weight:700; color:#1F293B; background:transparent;")
        ac_right.addWidget(info_t)

        info_d = QLabel("Cruza ZTMM com NC, enriquecendo com ICMS, ST, CFOP, NF Entrada e Razões.")
        info_d.setStyleSheet("font-size:9px; color:#708097; background:transparent;")
        info_d.setWordWrap(True)
        ac_right.addWidget(info_d)

        # Chips
        chips_w = QWidget()
        chips_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        chips_fl = FlowLayout(chips_w, h_spacing=4, v_spacing=3)
        chips_fl.setContentsMargins(0, 0, 0, 0)
        for t in ["Chave 1: N:N", "Chave 2: Multi", "Razões", "Parquet+CSV"]:
            chip = QLabel(t)
            chip.setObjectName("AnaliseChip")
            chips_fl.addWidget(chip)
        ac_right.addWidget(chips_w)

        ac_outer.addLayout(ac_right, 1)

        # Botão ao lado direito do card
        self.btn_analise = QPushButton("Executar Análise")
        self.btn_analise.setObjectName("PrimaryButton")
        self.btn_analise.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.btn_analise.clicked.connect(self.page.executar_analise)
        ac_outer.addWidget(self.btn_analise, 0, Qt.AlignVCenter)

        lay.addWidget(action_card, 1)

    def _sel_razoes(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta CSVs Razão")
        if p:
            self.path_razoes.input.setText(p)

    def _sel_destino(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta de destino")
        if p:
            self.path_destino.input.setText(p)


# ================================================================
# Página principal ZTMM
# ================================================================
class ZtmmPage(QWidget):
    def __init__(self):
        super().__init__()
        self.consolidator_worker = None
        self.export_worker = None
        self.analise_worker = None
        self.parquet_ztmm_path = None
        self.divisoes_disponiveis = []
        self._last_layout_mode = None

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

        # ---- Header Premium ----
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
        hi_lb = QLabel("ZTM")
        hi_lb.setObjectName("AnaliseIconText")
        hi_lb.setAlignment(Qt.AlignCenter)
        hi_lay.addWidget(hi_lb)
        hero_lay.addWidget(hero_icon, 0, Qt.AlignVCenter)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        ht1 = QLabel("ZTMM x Livro")
        ht1.setObjectName("SectionTitle")
        ht1.setStyleSheet("font-size:17px; font-weight:800; color:#182235; background:transparent;")
        hero_text.addWidget(ht1)
        ht2 = QLabel("Consolide TXTs ZTMM do SAP e execute a análise de conciliação com a base fiscal.")
        ht2.setObjectName("FieldText")
        ht2.setWordWrap(True)
        hero_text.addWidget(ht2)
        hero_lay.addLayout(hero_text, 1)

        outer.addWidget(hero)

        # ---- Abas (área principal) ----
        self.tabs = QTabWidget()
        self.tabs.setObjectName("ZtmmTabs")
        self.tabs.setDocumentMode(True)

        self.tab_cons = _TabConsolidacao(self)
        self.tab_analise = _TabAnalise(self)

        self.tabs.addTab(self.tab_cons, "Consolidação ZTMM")
        self.tabs.addTab(self.tab_analise, "Análise ZTMM x Livro")

        outer.addWidget(self.tabs, 1)

        # ---- Seção inferior: Progresso + Log + Resumo (lado a lado) ----
        self.bottom_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(10)

        # Painel esquerdo: progresso + log
        left_panel = QFrame()
        left_panel.setObjectName("TransparentPanel")
        left_panel.setAttribute(Qt.WA_StyledBackground, True)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
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

        # Log
        log_card = HoverCard()
        log_card.setObjectName("PremiumLogCard")
        log_card.setAttribute(Qt.WA_StyledBackground, True)
        log_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
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
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        ll_.addWidget(self.saida, 1)

        left_col.addWidget(log_card, 1)

        self.bottom_layout.addWidget(left_panel, 1)

        # Painel direito: resumo compacto
        self.summary = HoverCard()
        self.summary.setObjectName("PremiumSummaryCard")
        self.summary.setAttribute(Qt.WA_StyledBackground, True)
        self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.summary.setMinimumWidth(200)
        self.summary.setMaximumWidth(360)

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
        self.metric_linhas = MetricBox("Linhas ZTMM")
        self.metric_divisoes = MetricBox("Divisões")
        self.metric_chaves = MetricBox("Chaves conciliadas")
        self.metric_icms = MetricBox("ICMS preenchidos")
        self.metric_grid.addItemWidget(self.metric_linhas)
        self.metric_grid.addItemWidget(self.metric_divisoes)
        self.metric_grid.addItemWidget(self.metric_chaves)
        self.metric_grid.addItemWidget(self.metric_icms)
        sm_lay.addWidget(self.metric_grid)

        self.bottom_layout.addWidget(self.summary, 0)

        outer.addLayout(self.bottom_layout, 0)

        self._carregar_cache_ztmm()

    # ---- Lifecycle ----

    def showEvent(self, event):
        super().showEvent(event)
        self._carregar_cache_ztmm()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive()

    # ---- Responsividade ----

    def _apply_responsive(self):
        w = self.width()
        vertical = w < 920
        state = vertical
        if self._last_layout_mode != state:
            self._last_layout_mode = state
            if vertical:
                self.bottom_layout.setDirection(QBoxLayout.TopToBottom)
                self.bottom_layout.setSpacing(8)
                self.summary.setMinimumWidth(0)
                self.summary.setMaximumWidth(16777215)
                self.summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            else:
                self.bottom_layout.setDirection(QBoxLayout.LeftToRight)
                self.bottom_layout.setSpacing(10)
                sm_max = max(280, min(380, int(w * 0.28)))
                self.summary.setMinimumWidth(240)
                self.summary.setMaximumWidth(sm_max)
                self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    # ---- Cache ZTMM ----

    def _carregar_cache_ztmm(self):
        meta = carregar_meta_ztmm()
        if meta and Path(meta.get("parquet_path", "")).exists():
            self.parquet_ztmm_path = meta["parquet_path"]
            self.divisoes_disponiveis = meta.get("divisoes", [])
            self.tab_analise.cache_label.setText(
                f"Base ZTMM em cache: {Path(self.parquet_ztmm_path).name} "
                f"({meta.get('total_linhas', '?'):,} linhas, "
                f"{len(self.divisoes_disponiveis)} divisões)"
            )
            self._atualizar_lista_divisoes()
            self.tab_cons.btn_exportar.setEnabled(True)
        else:
            self.parquet_ztmm_path = None
            self.divisoes_disponiveis = []
            self.tab_analise.cache_label.setText("Nenhuma base ZTMM consolidada em cache.")
            self.tab_cons.btn_exportar.setEnabled(False)

    def _atualizar_lista_divisoes(self):
        # Limpa chips antigos
        for chip in self.tab_cons._div_chips:
            chip.deleteLater()
        self.tab_cons._div_chips.clear()
        self.tab_cons._all_selected = False
        self.tab_cons.btn_select_all.setText("Selecionar tudo")

        for d in self.divisoes_disponiveis:
            chip = DivChip(d)
            self.tab_cons._div_chips.append(chip)

        for chip in self.tab_cons._div_chips:
            self.tab_cons.chips_flow.addWidget(chip)

        n = len(self.divisoes_disponiveis)
        if n:
            self.tab_cons.div_info.setText(
                f"{n} divisões encontradas. Selecione as desejadas para exportação."
            )
        else:
            self.tab_cons.div_info.setText("Nenhuma divisão encontrada.")

    # ---- Progresso ----

    def atualizar(self, etapa, atual, total, detalhe):
        total_safe = max(total, 1)
        self.progress.setValue(int((atual / total_safe) * 100))
        self.progresso_texto.setText(f"{atual} / {total_safe}")
        self.status_texto.setText(detalhe)
        self.saida.setPlainText(detalhe)

    # ---- Consolidação ----

    def executar_consolidacao(self):
        pasta = self.tab_cons.path_base.input.text().strip()
        if not pasta or not os.path.isdir(pasta):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta válida com os TXTs ZTMM.")
            return
        self._set_buttons_enabled(False)
        self.status_texto.setText("Consolidando TXTs ZTMM...")
        self.saida.clear()
        self.progress.setValue(0)

        self.consolidator_worker = ZtmmConsolidatorWorker(pasta)
        self.consolidator_worker.progresso.connect(self.atualizar)
        self.consolidator_worker.sucesso.connect(self._consolidacao_sucesso)
        self.consolidator_worker.erro.connect(self._consolidacao_erro)
        self.consolidator_worker.start()

    def _consolidacao_sucesso(self, resultado):
        self._set_buttons_enabled(True)
        self.parquet_ztmm_path = resultado["parquet_path"]
        self.divisoes_disponiveis = resultado["divisoes"]
        self._atualizar_lista_divisoes()
        self._carregar_cache_ztmm()

        self.metric_linhas.lb_v.setText(f'{resultado["total_linhas"]:,}'.replace(",", "."))
        self.metric_divisoes.lb_v.setText(str(len(resultado["divisoes"])))
        self.atualizar("finalizado", 1, 1, f"Consolidado: {resultado['parquet_path']}")

        QMessageBox.information(
            self, "Sucesso",
            f"ZTMM consolidado.\n\n"
            f"Linhas: {resultado['total_linhas']:,}\n"
            f"Divisões: {len(resultado['divisoes'])}\n"
            f"Base: {resultado['parquet_path']}"
        )

    def _consolidacao_erro(self, erro):
        self._set_buttons_enabled(True)
        self.status_texto.setText("Falha na consolidação.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    # ---- Exportação ----

    def executar_exportacao(self):
        if not self.parquet_ztmm_path or not Path(self.parquet_ztmm_path).exists():
            QMessageBox.critical(self, "Erro", "Nenhuma base ZTMM consolidada encontrada.")
            return
        pasta_destino = self.tab_cons.path_destino.input.text().strip()
        if not pasta_destino or not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de destino válida.")
            return
        selecionadas = self.tab_cons.get_selected_divisoes()
        if not selecionadas:
            QMessageBox.critical(self, "Erro", "Selecione ao menos uma divisão.")
            return

        self._set_buttons_enabled(False)
        self.status_texto.setText("Exportando CSV por divisão...")
        self.progress.setValue(0)

        self.export_worker = ZtmmExportWorker(self.parquet_ztmm_path, selecionadas, pasta_destino)
        self.export_worker.progresso.connect(self.atualizar)
        self.export_worker.sucesso.connect(self._exportacao_sucesso)
        self.export_worker.erro.connect(self._exportacao_erro)
        self.export_worker.start()

    def _exportacao_sucesso(self, caminho):
        self._set_buttons_enabled(True)
        self.saida.setPlainText(f"Exportado: {caminho}")
        QMessageBox.information(self, "Sucesso", f"CSV exportado:\n{caminho}")

    def _exportacao_erro(self, erro):
        self._set_buttons_enabled(True)
        self.status_texto.setText("Falha na exportação.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    # ---- Análise ----

    def executar_analise(self):
        if not self.parquet_ztmm_path or not Path(self.parquet_ztmm_path).exists():
            QMessageBox.critical(
                self, "Erro",
                "Nenhuma base ZTMM consolidada em cache.\nExecute a consolidação primeiro."
            )
            return
        nc = self.tab_analise.path_nc.input.text().strip()
        if not nc or not os.path.isfile(nc):
            QMessageBox.critical(self, "Erro", "Selecione o arquivo Não Conciliados.")
            return
        razoes = self.tab_analise.path_razoes.input.text().strip()
        if not razoes or not os.path.isdir(razoes):
            QMessageBox.critical(self, "Erro", "Selecione a pasta com os CSVs de Razão.")
            return
        dest = self.tab_analise.path_destino.input.text().strip()
        if not dest or not os.path.isdir(dest):
            QMessageBox.critical(self, "Erro", "Selecione a pasta de destino da análise.")
            return

        self._set_buttons_enabled(False)
        self.status_texto.setText("Executando análise ZTMM x Livro...")
        self.saida.clear()
        self.progress.setValue(0)

        self.analise_worker = ZtmmAnaliseWorker(self.parquet_ztmm_path, nc, razoes, dest)
        self.analise_worker.progresso.connect(self.atualizar)
        self.analise_worker.sucesso.connect(self._analise_sucesso)
        self.analise_worker.erro.connect(self._analise_erro)
        self.analise_worker.start()

    def _analise_sucesso(self, resultado):
        self._set_buttons_enabled(True)
        self.metric_chaves.lb_v.setText(
            f'Ch1: {resultado["chaves_1"]:,} | Ch2: {resultado["chaves_2"]:,}'.replace(",", ".")
        )
        self.metric_icms.lb_v.setText(
            f'{resultado["preenchidos_icms"]:,}'.replace(",", ".")
        )
        self.atualizar("finalizado", 1, 1, f"Análise concluída: {resultado['csv_saida']}")
        self.saida.setPlainText(
            f"Parquet: {resultado['parquet_saida']}\n"
            f"CSV: {resultado['csv_saida']}\n"
            f"Linhas NC original: {resultado['linhas_nc']:,}\n"
            f"Linhas NC final: {resultado['linhas_nc_final']:,}\n"
            f"Linhas ZTM: {resultado['linhas_ztm']:,}\n"
            f"Chave 1: {resultado['chaves_1']:,} | Chave 2: {resultado['chaves_2']:,}\n"
            f"ICMS preenchidos: {resultado['preenchidos_icms']:,}\n"
            f"ST preenchidos: {resultado['preenchidos_st']:,}\n"
            f"Razão 222: {resultado['razao_222']}\n"
            f"Razão 223: {resultado['razao_223']}\n"
            f"Tempo: {resultado['tempo_total']}s"
        )
        QMessageBox.information(
            self, "Sucesso",
            f"Análise concluída.\n\n"
            f"Chave 1: {resultado['chaves_1']:,}\n"
            f"Chave 2: {resultado['chaves_2']:,}\n"
            f"ICMS preenchidos: {resultado['preenchidos_icms']:,}\n"
            f"Tempo: {resultado['tempo_total']}s\n\n"
            f"CSV: {resultado['csv_saida']}"
        )

    def _analise_erro(self, erro):
        self._set_buttons_enabled(True)
        self.status_texto.setText("Falha na análise.")
        QMessageBox.critical(self, "Erro", f"Falha:\n{erro}")

    # ---- Helpers ----

    def _set_buttons_enabled(self, enabled):
        self.tab_cons.btn_consolidar.setEnabled(enabled)
        self.tab_cons.btn_exportar.setEnabled(enabled and bool(self.parquet_ztmm_path))
        self.tab_analise.btn_analise.setEnabled(enabled)
