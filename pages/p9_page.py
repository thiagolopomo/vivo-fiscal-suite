#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QMessageBox, QTextEdit, QLineEdit, QSizePolicy, QProgressBar,
    QGraphicsDropShadowEffect, QBoxLayout
)

from workers.p9_worker import P9Worker


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

        # Quando o container do resumo fica largo em telas 100%,
        # empilha os cards para aproveitar melhor a altura/largura visual.
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
        self.setMinimumHeight(168)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        accent = QFrame()
        accent.setObjectName("CardAccentLine")
        accent.setAttribute(Qt.WA_StyledBackground, True)
        accent.setFixedHeight(2)
        layout.addWidget(accent)

        lb_eyebrow = QLabel(eyebrow)
        lb_eyebrow.setObjectName("SectionEyebrow")
        lb_eyebrow.setWordWrap(True)
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
        self.input.setMinimumHeight(42)
        self.input.setMaximumHeight(42)
        self.input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.input.setObjectName("PathInput")
        layout.addWidget(self.input)

        layout.addSpacing(4)

        self.btn = QPushButton(texto_botao)
        self.btn.setObjectName("SecondaryButton")
        self.btn.setMinimumHeight(42)
        self.btn.setMaximumHeight(42)
        self.btn.setMinimumWidth(175)
        self.btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn.clicked.connect(on_click)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(0)
        btn_row.addWidget(self.btn, 0, Qt.AlignLeft | Qt.AlignTop)
        btn_row.addStretch(1)

        layout.addLayout(btn_row)
        layout.addStretch(1)


class MetricBox(QFrame):
    def __init__(self, titulo, valor="—"):
        super().__init__()

        self.setObjectName("PremiumMetricBox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(68)
        self.setMaximumHeight(96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

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

        header = QVBoxLayout()
        header.setSpacing(4)

        lb1 = QLabel("PDF VALIDATION")
        lb1.setObjectName("SectionEyebrow")
        header.addWidget(lb1)

        lb2 = QLabel("Validação P9")
        lb2.setObjectName("SectionTitle")
        lb2.setWordWrap(True)
        header.addWidget(lb2)

        lb3 = QLabel("Leitura de PDFs com geração de consolidado em Excel.")
        lb3.setObjectName("SectionText")
        lb3.setWordWrap(True)
        header.addWidget(lb3)

        outer.addLayout(header)

        divider = QFrame()
        divider.setObjectName("SectionDivider")
        divider.setAttribute(Qt.WA_StyledBackground, True)
        divider.setFixedHeight(1)
        outer.addWidget(divider)

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

        self.exec_card = HoverCard()
        self.exec_card.setObjectName("PremiumExecCard")
        self.exec_card.setAttribute(Qt.WA_StyledBackground, True)
        self.exec_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.exec_card.setMinimumHeight(96)
        self.exec_card.setMaximumHeight(145)

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
        self.log_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.log_card.setMinimumHeight(110)

        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(10, 8, 10, 8)
        log_layout.setSpacing(6)

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
        self.saida.setMinimumHeight(60)
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        log_layout.addWidget(self.saida, 1)

        self.left_col.addWidget(self.log_card, 1)

        self.summary = HoverCard()
        self.summary.setObjectName("PremiumSummaryCard")
        self.summary.setAttribute(Qt.WA_StyledBackground, True)
        self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.summary.setMinimumWidth(260)
        self.summary.setMaximumWidth(340)
        self.summary.setMinimumHeight(150)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_mode()
        self._apply_scale_mode()
        self._sync_summary_height()

    def _sync_summary_height(self):
        self.metric_grid._rebuild(force=True)
        self.metric_grid.updateGeometry()

        self.summary.layout().activate()
        self.summary.adjustSize()

        margins = self.summary.layout().contentsMargins()
        spacing = self.summary.layout().spacing()

        total_h = (
            margins.top()
            + margins.bottom()
            + 2
            + self.summary.layout().itemAt(1).sizeHint().height()
            + spacing * 2
            + self.metric_grid.minimumSizeHint().height()
            + 10
        )

        self.summary.setMinimumHeight(max(150, total_h))
        self.summary.updateGeometry()

    

    def _apply_responsive_mode(self):
        w = self.width()
        h = self.height()

        paths_vertical = w < 920
        action_vertical = w < 700
        bottom_vertical = w < 980
        compact = h < 760

        layout_state = (bottom_vertical, compact)
        if self._last_layout_mode != layout_state:
            self._last_layout_mode = layout_state

            if bottom_vertical:
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

            if compact:
                self.exec_card.setMinimumHeight(92)
                self.exec_card.setMaximumHeight(132)
                self.log_card.setMinimumHeight(108)
                self.summary.setMinimumHeight(140)
                self.saida.setMinimumHeight(58)
            else:
                self.exec_card.setMinimumHeight(96)
                self.exec_card.setMaximumHeight(145)
                self.log_card.setMinimumHeight(120)
                self.summary.setMinimumHeight(150)
                self.saida.setMinimumHeight(64)

        if self._last_paths_mode != paths_vertical:
            self._last_paths_mode = paths_vertical
            self.paths_layout.setDirection(
                QBoxLayout.TopToBottom if paths_vertical else QBoxLayout.LeftToRight
            )

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
        h = self.height()

        roomy = w >= 1280 and h >= 820
        medium = w >= 1080 and h >= 760
        high_scale_compact = h < 860 and w < 1500

        if roomy and not high_scale_compact:
            self.metric_grid.min_item_width = 125

            for box in (self.metric_pdfs, self.metric_cfop, self.metric_resumo):
                box.setMinimumHeight(76)
                box.setMaximumHeight(84)
                box.lb_t.setStyleSheet(
                    "font-size: 10px; font-weight: 700; color: #7F8BA0; background: transparent;"
                )
                box.lb_v.setStyleSheet(
                    "font-size: 13px; font-weight: 800; color: #182235; background: transparent;"
                )

        elif medium:
            self.metric_grid.min_item_width = 138

            for box in (self.metric_pdfs, self.metric_cfop, self.metric_resumo):
                box.setMinimumHeight(72)
                box.setMaximumHeight(80)
                box.lb_t.setStyleSheet(
                    "font-size: 10px; font-weight: 700; color: #7F8BA0; background: transparent;"
                )
                box.lb_v.setStyleSheet(
                    "font-size: 12px; font-weight: 800; color: #182235; background: transparent;"
                )

        else:
            self.metric_grid.min_item_width = 150

            for box in (self.metric_pdfs, self.metric_cfop, self.metric_resumo):
                box.setMinimumHeight(68)
                box.setMaximumHeight(76)
                box.lb_t.setStyleSheet(
                    "font-size: 9px; font-weight: 700; color: #7F8BA0; background: transparent;"
                )
                box.lb_v.setStyleSheet(
                    "font-size: 11px; font-weight: 800; color: #182235; background: transparent;"
                )

        self.metric_grid._rebuild(force=True)
        self._sync_summary_height()

    def selecionar_pasta_pdfs(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta com os PDFs")
        if pasta:
            self.card_pdfs.input.setText(pasta)

    def selecionar_pasta_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino")
        if pasta:
            self.card_destino.input.setText(pasta)

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

    def finalizar_erro(self, erro):
        self.run_btn.setEnabled(True)
        self.status_texto.setText("Falha no processamento.")
        QMessageBox.critical(self, "Erro", f"Falha ao processar:\n{erro}")