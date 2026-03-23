#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QMessageBox, QTextEdit, QLineEdit, QSizePolicy, QProgressBar,
    QGraphicsDropShadowEffect, QBoxLayout, QCheckBox, QComboBox
)
from conferencia_logic import listar_execucoes_conferencia

from workers.p9_worker import P9Worker
from workers.conference_worker import ConferenceWorker


class HoverCard(QFrame):
    def __init__(self):
        super().__init__()

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 3)
        self._shadow.setColor(QColor(112, 55, 190, 24))
        self.setGraphicsEffect(self._shadow)

        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim_blur.setDuration(170)
        self._anim_blur.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"offset", self)
        self._anim_offset.setDuration(170)
        self._anim_offset.setEasingCurve(QEasingCurve.OutCubic)

        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._anim_blur.stop()
        self._anim_blur.setStartValue(self._shadow.blurRadius())
        self._anim_blur.setEndValue(28)
        self._anim_blur.start()

        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._shadow.offset())
        self._anim_offset.setEndValue(QPointF(0, 5))
        self._anim_offset.start()

        self._shadow.setColor(QColor(140, 70, 230, 72))

        self.setProperty("hover", True)
        self.style().unpolish(self)
        self.style().polish(self)

        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim_blur.stop()
        self._anim_blur.setStartValue(self._shadow.blurRadius())
        self._anim_blur.setEndValue(18)
        self._anim_blur.start()

        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._shadow.offset())
        self._anim_offset.setEndValue(QPointF(0, 3))
        self._anim_offset.start()

        self._shadow.setColor(QColor(112, 55, 190, 24))

        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)

        super().leaveEvent(event)


class ResponsiveGrid(QWidget):
    def __init__(self, min_item_width=220, parent=None):
        super().__init__(parent)
        self.min_item_width = min_item_width
        self.items = []
        self._current_cols = None

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(8)
        self._layout.setVerticalSpacing(8)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def addItemWidget(self, widget):
        self.items.append(widget)
        self._rebuild(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild(force=False)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if not self.items:
            return 0

        cols = max(1, min(len(self.items), width // max(1, self.min_item_width)))

        row_heights = []
        for i, w in enumerate(self.items):
            row = i // cols
            hint_h = max(w.minimumSizeHint().height(), w.sizeHint().height())
            if row >= len(row_heights):
                row_heights.append(hint_h)
            else:
                row_heights[row] = max(row_heights[row], hint_h)

        margins = self._layout.contentsMargins()
        total = margins.top() + margins.bottom()
        total += sum(row_heights)

        if len(row_heights) > 1:
            total += self._layout.verticalSpacing() * (len(row_heights) - 1)

        return total

    def sizeHint(self):
        w = max(1, self.width())
        if w <= 1:
            w = self.min_item_width * max(1, len(self.items))
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        w = max(1, self.width())
        if w <= 1:
            w = self.min_item_width * max(1, len(self.items))
        return self.sizeHintForWidth(w)

    def sizeHintForWidth(self, width):
        h = self.heightForWidth(width)
        return self._layout.geometry().size().expandedTo(self.minimumSize()).grownBy(
            self.contentsMargins()
        ) if h <= 0 else self._fallback_size(width, h)

    def _fallback_size(self, width, height):
        from PySide6.QtCore import QSize
        return QSize(width, height)

    def _calc_cols(self):
        if not self.items:
            return 1

        width = max(1, self.width())
        parent_w = self.parentWidget().width() if self.parentWidget() else width

        if parent_w >= 430:
            return 1

        cols = max(1, width // max(1, self.min_item_width))
        return min(cols, len(self.items))

    def _clear_layout_only(self):
        while self._layout.count():
            self._layout.takeAt(0)

    def _rebuild(self, force=False):
        if not self.items:
            self.setMinimumHeight(0)
            self.updateGeometry()
            return

        cols = self._calc_cols()

        if not force and cols == self._current_cols:
            h = self.heightForWidth(max(1, self.width()))
            self.setMinimumHeight(h)
            self.updateGeometry()
            return

        self._current_cols = cols
        self._clear_layout_only()

        for i, w in enumerate(self.items):
            row = i // cols
            col = i % cols
            self._layout.addWidget(w, row, col)

        self._layout.activate()

        h = self.heightForWidth(max(1, self.width()))
        self.setMinimumHeight(h)
        self.updateGeometry()


class PathCard(HoverCard):
    def __init__(self, eyebrow, titulo, subtitulo, texto_botao, on_click):
        super().__init__()

        self.setObjectName("PremiumPathCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(4)

        accent = QFrame()
        accent.setObjectName("CardAccentLine")
        accent.setAttribute(Qt.WA_StyledBackground, True)
        accent.setFixedHeight(2)
        layout.addWidget(accent)

        lb_eyebrow = QLabel(eyebrow)
        lb_eyebrow.setObjectName("SectionEyebrow")
        layout.addWidget(lb_eyebrow)

        lb_title = QLabel(titulo)
        lb_title.setObjectName("FieldTitle")
        lb_title.setWordWrap(True)
        layout.addWidget(lb_title)

        lb_sub = QLabel(subtitulo)
        lb_sub.setObjectName("FieldText")
        lb_sub.setWordWrap(True)
        layout.addWidget(lb_sub)

        self.input = QLineEdit()
        self.input.setReadOnly(True)
        self.input.setPlaceholderText("Nenhuma pasta selecionada")
        self.input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.input.setObjectName("PathInput")
        layout.addWidget(self.input)

        self.btn = QPushButton(texto_botao)
        self.btn.setObjectName("SecondaryButton")
        self.btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.btn.clicked.connect(on_click)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(0)
        btn_row.addWidget(self.btn, 0, Qt.AlignLeft)
        btn_row.addStretch(1)

        layout.addLayout(btn_row)


class MetricBox(QFrame):
    def __init__(self, titulo, valor="—"):
        super().__init__()

        self.setObjectName("PremiumMetricBox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        accent = QFrame()
        accent.setObjectName("MetricAccentLine")
        accent.setAttribute(Qt.WA_StyledBackground, True)
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        self.lb_t = QLabel(titulo)
        self.lb_t.setObjectName("MetricTitle")
        self.lb_t.setWordWrap(True)
        layout.addWidget(self.lb_t)

        self.lb_v = QLabel(valor)
        self.lb_v.setObjectName("MetricValue")
        self.lb_v.setWordWrap(True)
        layout.addWidget(self.lb_v)

        layout.addStretch(1)


class P9Page(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.conference_worker = None

        self._last_layout_mode = None
        self._last_action_mode = None
        self._last_paths_mode = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("PageCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(card, 1)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(8)

        # ── HERO HEADER (compacto, mesmo padrão ZTMM) ──
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
        hi_lb = QLabel("P9")
        hi_lb.setAlignment(Qt.AlignCenter)
        hi_lb.setStyleSheet("font-size:11px; font-weight:800; color:#FFF; background:transparent;")
        hi_lay.addWidget(hi_lb)
        hero_lay.addWidget(hero_icon, 0, Qt.AlignVCenter)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        ht1 = QLabel("Validação P9")
        ht1.setStyleSheet("font-size:17px; font-weight:800; color:#182235; background:transparent;")
        hero_text.addWidget(ht1)
        ht2 = QLabel("Leitura de PDFs fiscais com geração de consolidado em Excel.")
        ht2.setObjectName("FieldText")
        ht2.setWordWrap(True)
        hero_text.addWidget(ht2)
        hero_lay.addLayout(hero_text, 1)

        outer.addWidget(hero)

        divider = QFrame()
        divider.setObjectName("SectionDivider")
        divider.setAttribute(Qt.WA_StyledBackground, True)
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        # ── PATH CARDS ────────────────────────────────────────────────
        self.paths_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.paths_layout.setSpacing(12)

        self.card_pdfs = PathCard(
            "ORIGEM",
            "Biblioteca de PDFs",
            "Selecione a pasta com os PDFs fiscais de entrada.",
            "Selecionar PDFs",
            self.selecionar_pasta_pdfs,
        )

        self.card_destino = PathCard(
            "DESTINO",
            "Pasta de saída",
            "Defina onde serão gravados o consolidado e os auxiliares.",
            "Selecionar destino",
            self.selecionar_pasta_destino,
        )

        self.paths_layout.addWidget(self.card_pdfs, 1)
        self.paths_layout.addWidget(self.card_destino, 1)
        outer.addLayout(self.paths_layout)

        # ── ACTION ROW ────────────────────────────────────────────────
        self.action_row = QBoxLayout(QBoxLayout.LeftToRight)
        self.action_row.setSpacing(8)
        self.action_row.setContentsMargins(0, 0, 0, 0)

        self.run_btn = QPushButton("Executar validação")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setMinimumHeight(36)
        self.run_btn.setMaximumHeight(40)
        self.run_btn.setMinimumWidth(150)
        self.run_btn.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.run_btn.clicked.connect(self.executar)

        self.action_row.addWidget(self.run_btn, 0)
        self.action_row.addStretch(1)
        outer.addLayout(self.action_row)

        # ── CONFERÊNCIA SECTION ───────────────────────────────────────
        # ── CONFERÊNCIA (compacta, mesmo padrão ZTMM) ──
        self.conf_card = HoverCard()
        self.conf_card.setObjectName("PremiumPathCard")
        self.conf_card.setAttribute(Qt.WA_StyledBackground, True)
        self.conf_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        conf_layout = QVBoxLayout(self.conf_card)
        conf_layout.setContentsMargins(14, 10, 14, 10)
        conf_layout.setSpacing(5)

        conf_acc = QFrame()
        conf_acc.setObjectName("CardAccentLine")
        conf_acc.setAttribute(Qt.WA_StyledBackground, True)
        conf_acc.setFixedHeight(2)
        conf_layout.addWidget(conf_acc)

        # Header: título + botão na mesma linha
        conf_hdr = QHBoxLayout()
        conf_hdr.setSpacing(8)
        conf_hdr.setContentsMargins(0, 0, 0, 0)

        conf_title = QLabel("Conferência P9 x Base Fiscal")
        conf_title.setObjectName("FieldTitle")
        conf_title.setStyleSheet("font-size:12px; font-weight:700; color:#1F293B; background:transparent;")
        conf_hdr.addWidget(conf_title, 1, Qt.AlignVCenter)

        self.btn_conferencia = QPushButton("Executar Conferência")
        self.btn_conferencia.setObjectName("SecondaryButton")
        self.btn_conferencia.setCursor(Qt.PointingHandCursor)
        self.btn_conferencia.setMinimumHeight(32)
        self.btn_conferencia.setMaximumHeight(36)
        self.btn_conferencia.setEnabled(False)
        self.btn_conferencia.clicked.connect(self.executar_conferencia)
        conf_hdr.addWidget(self.btn_conferencia, 0, Qt.AlignVCenter)
        conf_layout.addLayout(conf_hdr)

        # Controles inline
        base_row = QHBoxLayout()
        base_row.setSpacing(8)
        base_row.setContentsMargins(0, 0, 0, 0)
        lb_base = QLabel("Base:")
        lb_base.setObjectName("FieldText")
        lb_base.setStyleSheet("font-size:10px; background:transparent;")
        lb_base.setFixedWidth(70)
        base_row.addWidget(lb_base, 0)
        self.chk_andersen = QCheckBox("Andersen")
        self.chk_vivo = QCheckBox("Vivo")
        self.chk_andersen.setStyleSheet("font-size:10px;")
        self.chk_vivo.setStyleSheet("font-size:10px;")
        self.chk_andersen.stateChanged.connect(self.atualizar_estado_conferencia)
        self.chk_vivo.stateChanged.connect(self.atualizar_estado_conferencia)
        base_row.addWidget(self.chk_andersen, 0)
        base_row.addWidget(self.chk_vivo, 0)
        base_row.addStretch(1)
        conf_layout.addLayout(base_row)

        livro_row = QHBoxLayout()
        livro_row.setSpacing(8)
        livro_row.setContentsMargins(0, 0, 0, 0)
        lb_livro = QLabel("Livro:")
        lb_livro.setObjectName("FieldText")
        lb_livro.setStyleSheet("font-size:10px; background:transparent;")
        lb_livro.setFixedWidth(70)
        livro_row.addWidget(lb_livro, 0)
        self.cmb_livro = QComboBox()
        self.cmb_livro.addItems(["Ambos", "Livro de Entrada", "Livro de Saída"])
        self.cmb_livro.currentIndexChanged.connect(self.on_livro_changed)
        self.cmb_livro.setMinimumHeight(28)
        self.cmb_livro.setMaximumHeight(30)
        self.cmb_livro.setStyleSheet("font-size:10px;")
        self.cmb_livro.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        livro_row.addWidget(self.cmb_livro, 1)
        conf_layout.addLayout(livro_row)

        exec_row = QHBoxLayout()
        exec_row.setSpacing(8)
        exec_row.setContentsMargins(0, 0, 0, 0)
        lb_exec = QLabel("Base:")
        lb_exec.setObjectName("FieldText")
        lb_exec.setStyleSheet("font-size:10px; background:transparent;")
        lb_exec.setFixedWidth(70)
        exec_row.addWidget(lb_exec, 0)
        self.cmb_execucao = QComboBox()
        self.cmb_execucao.setMinimumHeight(28)
        self.cmb_execucao.setMaximumHeight(30)
        self.cmb_execucao.setStyleSheet("font-size:10px;")
        self.cmb_execucao.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cmb_execucao.currentIndexChanged.connect(self.atualizar_estado_conferencia)
        exec_row.addWidget(self.cmb_execucao, 1)
        conf_layout.addLayout(exec_row)

        outer.addWidget(self.conf_card)

        # ── EXEC CARD (progress) ─────────────────────────────────────
        self.exec_card = HoverCard()
        self.exec_card.setObjectName("PremiumExecCard")
        self.exec_card.setAttribute(Qt.WA_StyledBackground, True)
        self.exec_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        exec_layout = QVBoxLayout(self.exec_card)
        exec_layout.setContentsMargins(10, 8, 10, 8)
        exec_layout.setSpacing(4)

        e_acc = QFrame()
        e_acc.setObjectName("CardAccentLine")
        e_acc.setAttribute(Qt.WA_StyledBackground, True)
        e_acc.setFixedHeight(2)
        exec_layout.addWidget(e_acc)

        e1 = QLabel("ANDAMENTO")
        e1.setObjectName("SectionEyebrow")
        exec_layout.addWidget(e1)

        self.status_texto = QLabel("Pronto para iniciar.")
        self.status_texto.setObjectName("InfoValue")
        self.status_texto.setWordWrap(True)
        exec_layout.addWidget(self.status_texto)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(16)
        exec_layout.addWidget(self.progress)

        self.progresso_texto = QLabel("0 / 0")
        self.progresso_texto.setObjectName("FieldText")
        exec_layout.addWidget(self.progresso_texto)

        # ── BOTTOM LAYOUT (log + summary) ─────────────────────────────
        self.bottom_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(12)

        self.left_panel = QFrame()
        self.left_panel.setObjectName("TransparentPanel")
        self.left_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

        self.left_col = QVBoxLayout(self.left_panel)
        self.left_col.setContentsMargins(0, 0, 0, 0)
        self.left_col.setSpacing(12)

        self.left_col.addWidget(self.exec_card, 0)

        self.log_card = HoverCard()
        self.log_card.setObjectName("PremiumLogCard")
        self.log_card.setAttribute(Qt.WA_StyledBackground, True)
        self.log_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(8, 6, 8, 6)
        log_layout.setSpacing(4)

        lg_acc = QFrame()
        lg_acc.setObjectName("CardAccentLine")
        lg_acc.setAttribute(Qt.WA_StyledBackground, True)
        lg_acc.setFixedHeight(2)
        log_layout.addWidget(lg_acc)

        tx1 = QLabel("SAÍDA DO PROCESSO")
        tx1.setObjectName("SectionEyebrow")
        log_layout.addWidget(tx1)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("A saída do processamento aparecerá aqui.")
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.saida, 1)

        self.left_col.addWidget(self.log_card, 1)

        self.summary = HoverCard()
        self.summary.setObjectName("PremiumSummaryCard")
        self.summary.setAttribute(Qt.WA_StyledBackground, True)
        self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.summary.setMinimumWidth(200)
        self.summary.setMaximumWidth(360)

        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(6)

        sm_acc = QFrame()
        sm_acc.setObjectName("CardAccentLine")
        sm_acc.setAttribute(Qt.WA_StyledBackground, True)
        sm_acc.setFixedHeight(2)
        summary_layout.addWidget(sm_acc)

        sm1 = QLabel("RESUMO")
        sm1.setObjectName("SectionEyebrow")
        summary_layout.addWidget(sm1)

        self.metric_grid = ResponsiveGrid(min_item_width=170)
        self.metric_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.metric_pdfs = MetricBox("PDFs processados")
        self.metric_cfop = MetricBox("Linhas CFOP")
        self.metric_resumo = MetricBox("Linhas resumo")

        self.metric_grid.addItemWidget(self.metric_pdfs)
        self.metric_grid.addItemWidget(self.metric_cfop)
        self.metric_grid.addItemWidget(self.metric_resumo)

        summary_layout.addWidget(self.metric_grid)

        self.bottom_layout.addWidget(self.left_panel, 1)
        self.bottom_layout.addWidget(self.summary, 0)
        outer.addLayout(self.bottom_layout, 1)

        self._apply_responsive_mode()
        self._apply_scale_mode()
        self.carregar_execucoes_conferencia()

    # ── LOGIC METHODS (unchanged) ─────────────────────────────────────

    def _agrupar_execucoes_para_combo(self, execucoes, livro):
        livro = (livro or "").strip()

        if livro == "Livro de Entrada":
            itens = []
            for meta in execucoes:
                if str(meta.get("tipo_movimento", "")).strip().upper() == "ENTRADA":
                    label = meta.get("label", "Execução sem identificação")
                    itens.append((label, meta))
            return itens

        if livro == "Livro de Saída":
            itens = []
            for meta in execucoes:
                if str(meta.get("tipo_movimento", "")).strip().upper() == "SAIDA":
                    label = meta.get("label", "Execução sem identificação")
                    itens.append((label, meta))
            return itens

        # AMBOS: agrupa só por período
        # porque entrada e saída normalmente vêm de pastas diferentes
        pares = {}
        for meta in execucoes:
            periodo = str(meta.get("periodo", "")).strip()
            tipo = str(meta.get("tipo_movimento", "")).strip().upper()

            if not periodo:
                continue

            if periodo not in pares:
                pares[periodo] = {"entrada": None, "saida": None}

            if tipo == "ENTRADA" and pares[periodo]["entrada"] is None:
                pares[periodo]["entrada"] = meta
            elif tipo == "SAIDA" and pares[periodo]["saida"] is None:
                pares[periodo]["saida"] = meta

        itens = []
        for periodo, par in pares.items():
            if par["entrada"] and par["saida"]:
                dir_ent = str(par["entrada"].get("base_dir_resumido") or par["entrada"].get("base_dir") or "")
                dir_sai = str(par["saida"].get("base_dir_resumido") or par["saida"].get("base_dir") or "")

                if dir_ent == dir_sai:
                    label = f"{periodo} | Entrada + Saída | {dir_ent}"
                else:
                    label = f"{periodo} | Entrada + Saída | ENT: {dir_ent} | SAI: {dir_sai}"

                data = {
                    "modo": "AMBOS",
                    "periodo": periodo,
                    "entrada": par["entrada"],
                    "saida": par["saida"],
                }
                itens.append((label, data))

        itens.sort(key=lambda x: x[0], reverse=True)
        return itens

    def on_livro_changed(self):
        self.carregar_execucoes_conferencia()
        self.atualizar_estado_conferencia()

    def showEvent(self, event):
        super().showEvent(event)
        self.carregar_execucoes_conferencia()
        self.atualizar_estado_conferencia()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_mode()
        self._apply_scale_mode()
        self._sync_summary_height()

    def _sync_summary_height(self):
        self.metric_grid._rebuild(force=True)

    def _apply_responsive_mode(self):
        w = self.width()
        h = self.height()

        narrow = w < 920
        action_vertical = w < 700
        compact = h < 760

        layout_state = (narrow, compact)
        if self._last_layout_mode != layout_state:
            self._last_layout_mode = layout_state

            if narrow:
                self.bottom_layout.setDirection(QBoxLayout.TopToBottom)
                self.bottom_layout.setSpacing(8)

                self.summary.setMinimumWidth(0)
                self.summary.setMaximumWidth(16777215)
                self.summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            else:
                self.bottom_layout.setDirection(QBoxLayout.LeftToRight)
                self.bottom_layout.setSpacing(10)

                summary_max = max(330, min(520, int(w * 0.34)))

                self.summary.setMinimumWidth(250)
                self.summary.setMaximumWidth(summary_max)
                self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)


        # Paths direction
        paths_vertical = narrow
        if self._last_paths_mode != paths_vertical:
            self._last_paths_mode = paths_vertical
            self.paths_layout.setDirection(
                QBoxLayout.TopToBottom if paths_vertical else QBoxLayout.LeftToRight
            )

        # Action row direction
        if self._last_action_mode != action_vertical:
            self._last_action_mode = action_vertical
            if action_vertical:
                self.action_row.setDirection(QBoxLayout.TopToBottom)
                self.run_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            else:
                self.action_row.setDirection(QBoxLayout.LeftToRight)
                self.run_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _apply_scale_mode(self):
        w = self.width()
        if w >= 1200:
            self.metric_grid.min_item_width = 120
        elif w >= 1000:
            self.metric_grid.min_item_width = 130
        else:
            self.metric_grid.min_item_width = 100
        self.metric_grid._rebuild(force=True)

    def carregar_execucoes_conferencia(self):
        self.cmb_execucao.clear()
        self.cmb_execucao.addItem("Selecione uma base consolidada", None)

        try:
            execucoes = listar_execucoes_conferencia()
        except Exception:
            execucoes = []

        livro = self.cmb_livro.currentText().strip() if hasattr(self, "cmb_livro") else "Ambos"
        itens = self._agrupar_execucoes_para_combo(execucoes, livro)

        for label, data in itens:
            self.cmb_execucao.addItem(label, data)

    def atualizar_estado_conferencia(self):
        tem_base = self.chk_andersen.isChecked() or self.chk_vivo.isChecked()
        tem_destino = bool(self.card_destino.input.text().strip())
        tem_execucao = hasattr(self, "cmb_execucao") and self.cmb_execucao.currentData() is not None
        self.btn_conferencia.setEnabled(tem_base and tem_destino and tem_execucao)

    def executar_conferencia(self):
        pasta_destino = self.card_destino.input.text().strip()

        if not pasta_destino or not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de destino válida.")
            return

        bases = []
        if self.chk_andersen.isChecked():
            bases.append("Andersen")
        if self.chk_vivo.isChecked():
            bases.append("Vivo")

        if not bases:
            QMessageBox.critical(self, "Erro", "Selecione ao menos uma base para conferência.")
            return

        livro = self.cmb_livro.currentText().strip()

        meta_execucao = self.cmb_execucao.currentData()
        if not meta_execucao:
            QMessageBox.critical(self, "Erro", "Selecione uma base consolidada.")
            return

        self.run_btn.setEnabled(False)
        self.btn_conferencia.setEnabled(False)
        self.status_texto.setText("Montando conferência...")
        self.saida.setPlainText("Iniciando conferência P9 x Fiscal...")
        self.progress.setValue(0)

        self.conference_worker = ConferenceWorker(
            bases_selecionadas=bases,
            livro_filtro=livro,
            pasta_destino=pasta_destino,
            meta_execucao=meta_execucao,
        )
        self.conference_worker.progresso.connect(self.atualizar)
        self.conference_worker.sucesso.connect(self.finalizar_conferencia_sucesso)
        self.conference_worker.erro.connect(self.finalizar_conferencia_erro)
        self.conference_worker.start()

    def finalizar_conferencia_sucesso(self, resultado):
        self.run_btn.setEnabled(True)
        self.atualizar_estado_conferencia()
        self.status_texto.setText("Conferência concluída.")
        self.saida.setPlainText(f"Arquivo gerado: {resultado['arquivo_saida']}")
        self.progress.setValue(100)
        self.progresso_texto.setText("1 / 1")

        QMessageBox.information(
            self,
            "Sucesso",
            f"Conferência concluída.\n\n"
            f"Linhas Fiscal: {resultado['linhas_fiscal']:,}\n"
            f"Linhas P9: {resultado['linhas_p9']:,}\n"
            f"Linhas Conferência: {resultado['linhas_conferencia']:,}\n\n"
            f"Arquivo:\n{resultado['arquivo_saida']}"
        )

    def finalizar_conferencia_erro(self, erro):
        self.run_btn.setEnabled(True)
        self.atualizar_estado_conferencia()
        self.status_texto.setText("Falha na conferência.")
        QMessageBox.critical(self, "Erro", f"Falha ao executar conferência:\n{erro}")

    def selecionar_pasta_pdfs(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta com os PDFs")
        if pasta:
            self.card_pdfs.input.setText(pasta)

    def selecionar_pasta_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino")
        if pasta:
            self.card_destino.input.setText(pasta)
            self.atualizar_estado_conferencia()

    def atualizar(self, etapa, atual, total, detalhe):
        total_safe = total if total > 0 else 1
        percentual = int((atual / total_safe) * 100)
        self.progress.setValue(percentual)
        self.progresso_texto.setText(f"{atual} / {total_safe}")

        if etapa == "processando_pdf":
            self.status_texto.setText("Lendo PDFs...")
            self.saida.setPlainText(f"Arquivo atual: {detalhe}")
        elif etapa == "gerando_excel":
            self.status_texto.setText("Gerando Excel...")
            self.saida.setPlainText(detalhe)
        elif etapa == "finalizado":
            self.status_texto.setText("Processamento concluído.")
            self.saida.setPlainText(detalhe)
        elif etapa == "conferencia":
            self.status_texto.setText("Executando conferência...")
            self.saida.setPlainText(detalhe)

    def executar(self):
        pasta_pdfs = self.card_pdfs.input.text().strip()
        pasta_destino = self.card_destino.input.text().strip()

        if not pasta_pdfs:
            QMessageBox.critical(self, "Erro", "Selecione a pasta com os PDFs.")
            return
        if not os.path.isdir(pasta_pdfs):
            QMessageBox.critical(self, "Erro", "A pasta de PDFs informada não existe.")
            return
        if not pasta_destino:
            QMessageBox.critical(self, "Erro", "Selecione a pasta de destino.")
            return
        if not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "A pasta de destino informada não existe.")
            return

        self.run_btn.setEnabled(False)
        self.status_texto.setText("Preparando processamento...")
        self.progresso_texto.setText("0 / 0")
        self.saida.clear()
        self.progress.setValue(0)

        self.worker = P9Worker(pasta_pdfs, pasta_destino)
        self.worker.progresso.connect(self.atualizar)
        self.worker.sucesso.connect(self.finalizar_sucesso)
        self.worker.erro.connect(self.finalizar_erro)
        self.worker.start()

    def finalizar_sucesso(self, resultado):
        self.run_btn.setEnabled(True)

        self.metric_pdfs.lb_v.setText(str(resultado["arquivos_pdf"]))
        self.metric_cfop.lb_v.setText(f'{resultado["linhas_cfop"]:,}'.replace(",", "."))
        self.metric_resumo.lb_v.setText(f'{resultado["linhas_resumo"]:,}'.replace(",", "."))

        self.atualizar("finalizado", 1, 1, f"Arquivo final: {resultado['arquivo_final']}")

        QMessageBox.information(
            self,
            "Sucesso",
            f"Processamento concluído.\n\n"
            f"PDFs processados: {resultado['arquivos_pdf']}\n"
            f"Linhas CFOP: {resultado['linhas_cfop']:,}\n"
            f"Linhas Resumo: {resultado['linhas_resumo']:,}\n"
            f"Tempo total: {resultado['tempo_total']}s\n\n"
            f"Arquivo consolidado:\n{resultado['arquivo_final']}"
        )
        self.carregar_execucoes_conferencia()
        self.atualizar_estado_conferencia()

    def finalizar_erro(self, erro):
        self.run_btn.setEnabled(True)
        self.status_texto.setText("Falha no processamento.")
        QMessageBox.critical(self, "Erro", f"Falha ao processar:\n{erro}")
