#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QLineEdit, QTextEdit, QProgressBar
)

from workers.consolidator_worker import ConsolidatorProcessWorker, ConsolidatorExportWorker
from pages.p9_page import PathCard, MetricBox


class ConsolidatorPage(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.export_worker = None
        self.parquet_cache_path = None
        self.tipo_movimento = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        card = QFrame()
        card.setObjectName("PageCard")
        root.addWidget(card)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(5)

        lb1 = QLabel("TXT CONSOLIDATION")
        lb1.setObjectName("SectionEyebrow")
        header.addWidget(lb1)

        lb2 = QLabel("Consolidador Fiscal")
        lb2.setObjectName("SectionTitle")
        header.addWidget(lb2)

        lb3 = QLabel(
            "Prepare a base interna em parquet e depois exporte no formato ANDERSEN ou VIVO a partir do mesmo workspace."
        )
        lb3.setObjectName("SectionText")
        lb3.setWordWrap(True)
        header.addWidget(lb3)

        outer.addLayout(header)

        top = QHBoxLayout()
        top.setSpacing(16)

        self.card_base = PathCard(
            "BASE",
            "Entrada TXT",
            "Selecione a pasta com os arquivos TXT fiscais que serão processados pelo motor de consolidação.",
            "Selecionar base",
            self.selecionar_base_dir,
        )
        top.addWidget(self.card_base, 1)

        self.card_destino = PathCard(
            "EXPORT",
            "Destino final",
            "Escolha a pasta onde ficarão as exportações finais e saídas auxiliares.",
            "Selecionar destino",
            self.selecionar_pasta_destino,
        )
        top.addWidget(self.card_destino, 1)

        outer.addLayout(top)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.btn_processar = QPushButton("Preparar base interna")
        self.btn_processar.setObjectName("PrimaryButton")
        self.btn_processar.setMinimumHeight(46)
        self.btn_processar.clicked.connect(self.executar)

        self.btn_andersen = QPushButton("Exportar ANDERSEN")
        self.btn_andersen.setObjectName("SecondaryButton")
        self.btn_andersen.setMinimumHeight(46)
        self.btn_andersen.setEnabled(False)
        self.btn_andersen.clicked.connect(self.exportar_andersen)

        self.btn_vivo = QPushButton("Exportar VIVO")
        self.btn_vivo.setObjectName("GhostButton")
        self.btn_vivo.setMinimumHeight(46)
        self.btn_vivo.setEnabled(False)
        self.btn_vivo.clicked.connect(self.exportar_vivo)

        action_row.addWidget(self.btn_processar)
        action_row.addWidget(self.btn_andersen)
        action_row.addWidget(self.btn_vivo)
        action_row.addStretch()

        outer.addLayout(action_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        outer.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(14)
        body.addLayout(left, 7)

        right = QVBoxLayout()
        right.setSpacing(14)
        body.addLayout(right, 4)

        exec_card = QFrame()
        exec_card.setObjectName("GlassCard")
        exec_layout = QVBoxLayout(exec_card)
        exec_layout.setContentsMargins(18, 16, 18, 16)
        exec_layout.setSpacing(10)

        e1 = QLabel("PROCESS FLOW")
        e1.setObjectName("SectionEyebrow")
        exec_layout.addWidget(e1)

        self.status_texto = QLabel("Aguardando início...")
        self.status_texto.setObjectName("InfoValue")
        self.status_texto.setWordWrap(True)
        exec_layout.addWidget(self.status_texto)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        exec_layout.addWidget(self.progress)

        self.progresso_texto = QLabel("0 / 0")
        self.progresso_texto.setObjectName("FieldText")
        exec_layout.addWidget(self.progresso_texto)

        left.addWidget(exec_card)

        stream_card = QFrame()
        stream_card.setObjectName("SoftCard")
        stream_layout = QVBoxLayout(stream_card)
        stream_layout.setContentsMargins(18, 16, 18, 16)
        stream_layout.setSpacing(10)

        st1 = QLabel("EXPORT / OUTPUT")
        st1.setObjectName("SectionEyebrow")
        stream_layout.addWidget(st1)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("Logs do processamento e exportações aparecerão aqui.")
        self.saida.setMinimumHeight(300)
        stream_layout.addWidget(self.saida, 1)

        left.addWidget(stream_card, 1)

        summary = QFrame()
        summary.setObjectName("SoftCard")
        sum_layout = QVBoxLayout(summary)
        sum_layout.setContentsMargins(18, 16, 18, 16)
        sum_layout.setSpacing(12)

        sm1 = QLabel("SESSION SUMMARY")
        sm1.setObjectName("SectionEyebrow")
        sum_layout.addWidget(sm1)

        self.metric_tipo = MetricBox("Tipo detectado")
        self.metric_linhas = MetricBox("Linhas")
        self.metric_base = MetricBox("Base interna", "Nenhuma base processada")

        sum_layout.addWidget(self.metric_tipo)
        sum_layout.addWidget(self.metric_linhas)
        sum_layout.addWidget(self.metric_base)
        sum_layout.addStretch(1)

        right.addWidget(summary)

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
        elif etapa == "processando_txt":
            self.status_texto.setText("Processando TXT...")
            self.saida.setPlainText(detalhe)
        elif etapa == "consolidando":
            self.status_texto.setText("Consolidando shards...")
            self.saida.setPlainText(detalhe)
        elif etapa == "finalizado":
            self.status_texto.setText("Processamento concluído.")
            self.saida.setPlainText(detalhe)
        elif etapa == "exportando_csv":
            self.status_texto.setText("Exportando arquivo...")
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