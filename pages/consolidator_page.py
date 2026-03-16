#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QTextEdit, QSizePolicy, QProgressBar,
    QBoxLayout
)

from workers.consolidator_worker import ConsolidatorProcessWorker, ConsolidatorExportWorker
from pages.p9_page import PathCard, MetricBox, HoverCard


class ConsolidatorPage(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.export_worker = None
        self.parquet_cache_path = None
        self.tipo_movimento = None

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

        lb1 = QLabel("CONSOLIDAÇÃO TXT")
        lb1.setObjectName("SectionEyebrow")
        header.addWidget(lb1)

        lb2 = QLabel("Consolidador Fiscal")
        lb2.setObjectName("SectionTitle")
        lb2.setWordWrap(True)
        header.addWidget(lb2)

        lb3 = QLabel(
            "Escolha a pasta com os arquivos TXT, gere a base interna em parquet e exporte no layout necessário."
        )
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

        self.card_base = PathCard(
            "BASE",
            "Arquivos TXT fiscais",
            "Selecione a pasta com os arquivos TXT de entrada.",
            "Selecionar base",
            self.selecionar_base_dir,
        )

        self.card_destino = PathCard(
            "DESTINO",
            "Pasta de saída",
            "Selecione a pasta onde serão salvos a base interna e os arquivos finais.",
            "Selecionar destino",
            self.selecionar_pasta_destino,
        )

        self.paths_layout.addWidget(self.card_base, 1)
        self.paths_layout.addWidget(self.card_destino, 1)
        outer.addLayout(self.paths_layout)

        self.action_row = QBoxLayout(QBoxLayout.LeftToRight)
        self.action_row.setSpacing(10)

        self.btn_processar = QPushButton("Preparar base interna")
        self.btn_processar.setObjectName("PrimaryButton")
        self.btn_processar.setMinimumHeight(40)
        self.btn_processar.setMinimumWidth(180)
        self.btn_processar.clicked.connect(self.executar)

        self.btn_andersen = QPushButton("Exportar ANDERSEN")
        self.btn_andersen.setObjectName("SecondaryButton")
        self.btn_andersen.setMinimumHeight(40)
        self.btn_andersen.setMinimumWidth(165)
        self.btn_andersen.setEnabled(False)
        self.btn_andersen.clicked.connect(self.exportar_andersen)

        self.btn_vivo = QPushButton("Exportar VIVO")
        self.btn_vivo.setObjectName("GhostButton")
        self.btn_vivo.setMinimumHeight(40)
        self.btn_vivo.setMinimumWidth(145)
        self.btn_vivo.setEnabled(False)
        self.btn_vivo.clicked.connect(self.exportar_vivo)

        self.action_row.addWidget(self.btn_processar, 0)
        self.action_row.addWidget(self.btn_andersen, 0)
        self.action_row.addWidget(self.btn_vivo, 0)
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

        self.status_texto = QLabel("Aguardando início...")
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

        self.stream_card = HoverCard()
        self.stream_card.setObjectName("PremiumLogCard")
        self.stream_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stream_card.setMinimumHeight(260)

        stream_layout = QVBoxLayout(self.stream_card)
        stream_layout.setContentsMargins(14, 12, 14, 12)
        stream_layout.setSpacing(8)

        st_acc = QFrame()
        st_acc.setObjectName("CardAccentLine")
        st_acc.setFixedHeight(2)
        stream_layout.addWidget(st_acc)

        st1 = QLabel("SAÍDA DO PROCESSO")
        st1.setObjectName("SectionEyebrow")
        stream_layout.addWidget(st1)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("Os logs do processamento e da exportação aparecerão aqui.")
        self.saida.setMinimumHeight(170)
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        stream_layout.addWidget(self.saida, 1)

        self.left_col.addWidget(self.stream_card, 1)

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

        self.metric_tipo = MetricBox("Tipo detectado")
        self.metric_linhas = MetricBox("Linhas")
        self.metric_base = MetricBox("Base interna", "Nenhuma base processada")

        self.summary_grid.addWidget(self.metric_tipo, 0, 0)
        self.summary_grid.addWidget(self.metric_linhas, 1, 0)
        self.summary_grid.addWidget(self.metric_base, 2, 0)

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

        if w < 980:
            self.action_row.setDirection(QBoxLayout.TopToBottom)
            self.btn_processar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.btn_andersen.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.btn_vivo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            self.action_row.setDirection(QBoxLayout.LeftToRight)
            self.btn_processar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.btn_andersen.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.btn_vivo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._clear_grid(self.summary_grid)

        if w < 980:
            self.bottom_layout.setDirection(QBoxLayout.TopToBottom)
            self.summary.setMinimumWidth(0)
            self.summary.setMaximumWidth(16777215)

            self.summary_grid.addWidget(self.metric_tipo, 0, 0)
            self.summary_grid.addWidget(self.metric_linhas, 0, 1)
            self.summary_grid.addWidget(self.metric_base, 0, 2)
        else:
            self.bottom_layout.setDirection(QBoxLayout.LeftToRight)
            self.summary.setMinimumWidth(300)
            self.summary.setMaximumWidth(360)

            self.summary_grid.addWidget(self.metric_tipo, 0, 0)
            self.summary_grid.addWidget(self.metric_linhas, 1, 0)
            self.summary_grid.addWidget(self.metric_base, 2, 0)

    def selecionar_base_dir(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta base com os TXT")
        if pasta:
            self.card_base.input.setText(pasta)

    def selecionar_pasta_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino")
        if pasta:
            self.card_destino.input.setText(pasta)

    def atualizar(self, etapa, atual, total, detalhe):
        total_safe = total if total > 0 else 1
        percentual = int((atual / total_safe) * 100)
        self.progress.setValue(percentual)
        self.progresso_texto.setText(f"{atual} / {total_safe}")

        if etapa == "preparando":
            self.status_texto.setText("Preparando processamento...")
            self.saida.setPlainText(detalhe)
        elif etapa == "processando_txt":
            self.status_texto.setText("Lendo e estruturando arquivos TXT...")
            self.saida.setPlainText(detalhe)
        elif etapa == "consolidando":
            self.status_texto.setText("Consolidando dados em base interna...")
            self.saida.setPlainText(detalhe)
        elif etapa == "finalizado":
            self.status_texto.setText("Base interna pronta.")
            self.saida.setPlainText(detalhe)
        elif etapa == "exportando_csv":
            self.status_texto.setText("Gerando exportação final...")
            self.saida.setPlainText(detalhe)
        elif etapa == "finalizado_csv":
            self.status_texto.setText("Exportação concluída.")
            self.saida.setPlainText(detalhe)

    def executar(self):
        base_dir = self.card_base.input.text().strip()
        pasta_destino = self.card_destino.input.text().strip()

        if not base_dir:
            QMessageBox.critical(self, "Erro", "Selecione a pasta base com os TXT.")
            return
        if not os.path.isdir(base_dir):
            QMessageBox.critical(self, "Erro", "A pasta base informada não existe.")
            return
        if not pasta_destino:
            QMessageBox.critical(self, "Erro", "Selecione a pasta de destino.")
            return
        if not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "A pasta de destino informada não existe.")
            return

        self.btn_processar.setEnabled(False)
        self.btn_andersen.setEnabled(False)
        self.btn_vivo.setEnabled(False)
        self.status_texto.setText("Preparando processamento...")
        self.progresso_texto.setText("0 / 0")
        self.saida.clear()
        self.progress.setValue(0)

        self.worker = ConsolidatorProcessWorker(base_dir, pasta_destino)
        self.worker.progresso.connect(self.atualizar)
        self.worker.sucesso.connect(self.finalizar_sucesso)
        self.worker.erro.connect(self.finalizar_erro)
        self.worker.start()

    def finalizar_sucesso(self, resultado):
        self.btn_processar.setEnabled(True)
        self.btn_andersen.setEnabled(True)
        self.btn_vivo.setEnabled(True)

        self.parquet_cache_path = resultado["parquet_final"]
        self.tipo_movimento = resultado["tipo_movimento"]

        self.metric_tipo.lb_v.setText(str(resultado["tipo_movimento"]))
        self.metric_linhas.lb_v.setText(f'{resultado["total_linhas"]:,}'.replace(",", "."))
        self.metric_base.lb_v.setText(Path(resultado["parquet_final"]).name)

        self.atualizar("finalizado", 1, 1, f"Base interna pronta: {resultado['parquet_final']}")

        QMessageBox.information(
            self,
            "Sucesso",
            f"Base processada com sucesso.\n\n"
            f"Tipo detectado: {resultado['tipo_movimento']}\n"
            f"Linhas: {resultado['total_linhas']:,}\n"
            f"Base interna: {resultado['parquet_final']}\n"
            f"Tempo total: {resultado['tempo_total']}s"
        )

    def finalizar_erro(self, erro):
        self.btn_processar.setEnabled(True)
        self.status_texto.setText("Falha no processamento.")
        QMessageBox.critical(self, "Erro", f"Falha ao processar:\n{erro}")

    def _start_export(self, modo):
        if not self.parquet_cache_path or not Path(self.parquet_cache_path).exists():
            QMessageBox.critical(self, "Erro", "Nenhuma base processada foi encontrada.")
            return

        pasta_destino = self.card_destino.input.text().strip()
        if not pasta_destino or not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de destino válida.")
            return

        self.btn_processar.setEnabled(False)
        self.btn_andersen.setEnabled(False)
        self.btn_vivo.setEnabled(False)

        self.export_worker = ConsolidatorExportWorker(
            modo=modo,
            parquet_path=self.parquet_cache_path,
            pasta_destino=pasta_destino,
            tipo_movimento=self.tipo_movimento,
        )
        self.export_worker.progresso.connect(self.atualizar)
        self.export_worker.sucesso.connect(self.finalizar_export_sucesso)
        self.export_worker.erro.connect(self.finalizar_export_erro)
        self.export_worker.start()

    def exportar_andersen(self):
        self._start_export("andersen")

    def exportar_vivo(self):
        self._start_export("vivo")

    def finalizar_export_sucesso(self, caminho):
        self.btn_processar.setEnabled(True)
        self.btn_andersen.setEnabled(True)
        self.btn_vivo.setEnabled(True)
        self.saida.setPlainText(f"Arquivo exportado: {caminho}")
        QMessageBox.information(self, "Sucesso", f"Exportação concluída.\n\n{caminho}")

    def finalizar_export_erro(self, erro):
        self.btn_processar.setEnabled(True)
        self.btn_andersen.setEnabled(True)
        self.btn_vivo.setEnabled(True)
        self.status_texto.setText("Falha na exportação.")
        QMessageBox.critical(self, "Erro", f"Falha ao exportar:\n{erro}")