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


class PathCard(HoverCard):
    def __init__(self, eyebrow, titulo, subtitulo, texto_botao, on_click):
        super().__init__()

        self.setObjectName("PremiumPathCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        accent = QFrame()
        accent.setObjectName("CardAccentLine")
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
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(74)
        self.setMaximumHeight(74)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        accent = QFrame()
        accent.setObjectName("MetricAccentLine")
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        lb_t = QLabel(titulo)
        lb_t.setObjectName("MetricTitle")
        lb_t.setWordWrap(True)
        layout.addWidget(lb_t)

        self.lb_v = QLabel(valor)
        self.lb_v.setObjectName("MetricValue")
        self.lb_v.setWordWrap(True)
        layout.addWidget(self.lb_v)

        layout.addStretch(1)


class P9Page(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("PageCard")
        root.addWidget(card)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

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
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("SectionDivider")
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
        self.action_row.setSpacing(10)

        self.run_btn = QPushButton("Executar validação")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setMinimumWidth(185)
        self.run_btn.clicked.connect(self.executar)

        self.action_row.addWidget(self.run_btn, 0)
        self.action_row.addStretch(1)

        outer.addLayout(self.action_row)

        self.exec_card = HoverCard()
        self.exec_card.setObjectName("PremiumExecCard")
        self.exec_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.exec_card.setMinimumHeight(132)

        exec_layout = QVBoxLayout(self.exec_card)
        exec_layout.setContentsMargins(14, 12, 14, 12)
        exec_layout.setSpacing(8)

        e_acc = QFrame()
        e_acc.setObjectName("CardAccentLine")
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
        self.bottom_layout.setSpacing(12)

        self.left_col = QVBoxLayout()
        self.left_col.setSpacing(12)

        self.left_col.addWidget(self.exec_card, 0)

        self.log_card = HoverCard()
        self.log_card.setObjectName("PremiumLogCard")
        self.log_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_card.setMinimumHeight(260)

        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.setSpacing(8)

        lg_acc = QFrame()
        lg_acc.setObjectName("CardAccentLine")
        lg_acc.setFixedHeight(2)
        log_layout.addWidget(lg_acc)

        tx1 = QLabel("SAÍDA DO PROCESSO")
        tx1.setObjectName("SectionEyebrow")
        log_layout.addWidget(tx1)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("A saída do processamento aparecerá aqui.")
        self.saida.setMinimumHeight(170)
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.saida, 1)

        self.left_col.addWidget(self.log_card, 1)

        self.summary = HoverCard()
        self.summary.setObjectName("PremiumSummaryCard")
        self.summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.summary.setMinimumWidth(300)
        self.summary.setMaximumWidth(360)

        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(8)

        sm_acc = QFrame()
        sm_acc.setObjectName("CardAccentLine")
        sm_acc.setFixedHeight(2)
        summary_layout.addWidget(sm_acc)

        sm1 = QLabel("RESUMO")
        sm1.setObjectName("SectionEyebrow")
        summary_layout.addWidget(sm1)

        self.summary_grid = QGridLayout()
        self.summary_grid.setHorizontalSpacing(8)
        self.summary_grid.setVerticalSpacing(8)

        self.metric_pdfs = MetricBox("PDFs processados")
        self.metric_cfop = MetricBox("Linhas CFOP")
        self.metric_resumo = MetricBox("Linhas resumo")

        self.summary_grid.addWidget(self.metric_pdfs, 0, 0)
        self.summary_grid.addWidget(self.metric_cfop, 1, 0)
        self.summary_grid.addWidget(self.metric_resumo, 2, 0)

        summary_layout.addLayout(self.summary_grid)
        summary_layout.addStretch(1)

        left_wrap = QWidget()
        left_wrap.setLayout(self.left_col)
        left_wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.bottom_layout.addWidget(left_wrap, 1)
        self.bottom_layout.addWidget(self.summary, 0)

        outer.addLayout(self.bottom_layout, 1)

        self._apply_responsive_mode()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_mode()

    def _clear_grid(self, grid):
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _apply_responsive_mode(self):
        w = self.width()

        if w < 920:
            self.paths_layout.setDirection(QBoxLayout.TopToBottom)
        else:
            self.paths_layout.setDirection(QBoxLayout.LeftToRight)

        if w < 700:
            self.action_row.setDirection(QBoxLayout.TopToBottom)
            self.run_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            self.action_row.setDirection(QBoxLayout.LeftToRight)
            self.run_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._clear_grid(self.summary_grid)

        if w < 980:
            self.bottom_layout.setDirection(QBoxLayout.TopToBottom)
            self.summary.setMinimumWidth(0)
            self.summary.setMaximumWidth(16777215)

            self.summary_grid.addWidget(self.metric_pdfs, 0, 0)
            self.summary_grid.addWidget(self.metric_cfop, 0, 1)
            self.summary_grid.addWidget(self.metric_resumo, 0, 2)
        else:
            self.bottom_layout.setDirection(QBoxLayout.LeftToRight)
            self.summary.setMinimumWidth(300)
            self.summary.setMaximumWidth(360)

            self.summary_grid.addWidget(self.metric_pdfs, 0, 0)
            self.summary_grid.addWidget(self.metric_cfop, 1, 0)
            self.summary_grid.addWidget(self.metric_resumo, 2, 0)

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