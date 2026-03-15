#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QMessageBox, QTextEdit, QLineEdit, QSizePolicy
)

from workers.p9_worker import P9Worker


class PathCard(QFrame):
    def __init__(self, eyebrow, titulo, subtitulo, texto_botao, on_click):
        super().__init__()
        self.setObjectName("SoftCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        lb_eyebrow = QLabel(eyebrow)
        lb_eyebrow.setObjectName("SectionEyebrow")
        layout.addWidget(lb_eyebrow)

        lb_title = QLabel(titulo)
        lb_title.setObjectName("FieldTitle")
        layout.addWidget(lb_title)

        lb_sub = QLabel(subtitulo)
        lb_sub.setObjectName("FieldText")
        lb_sub.setWordWrap(True)
        layout.addWidget(lb_sub)

        self.input = QLineEdit()
        self.input.setReadOnly(True)
        self.input.setPlaceholderText("Nenhuma pasta selecionada")
        self.input.setMinimumHeight(44)
        layout.addWidget(self.input)

        self.btn = QPushButton(texto_botao)
        self.btn.setObjectName("SecondaryButton")
        self.btn.setMinimumHeight(40)
        self.btn.clicked.connect(on_click)
        layout.addWidget(self.btn, 0, Qt.AlignLeft)


class MetricBox(QFrame):
    def __init__(self, titulo, valor="—"):
        super().__init__()
        self.setObjectName("AccentPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        lb_t = QLabel(titulo)
        lb_t.setObjectName("MetricTitle")
        layout.addWidget(lb_t)

        self.lb_v = QLabel(valor)
        self.lb_v.setObjectName("MetricValue")
        self.lb_v.setWordWrap(True)
        layout.addWidget(self.lb_v)


class P9Page(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        card = QFrame()
        card.setObjectName("PageCard")
        root.addWidget(card)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(16)

        left_header = QVBoxLayout()
        left_header.setSpacing(5)

        eyebrow = QLabel("PDF VALIDATION")
        eyebrow.setObjectName("SectionEyebrow")
        left_header.addWidget(eyebrow)

        title = QLabel("Validação P9")
        title.setObjectName("SectionTitle")
        left_header.addWidget(title)

        subtitle = QLabel(
            "Leitura de RAICMS em PDF com geração de Excel, resumo executivo e acompanhamento do processamento em tempo real."
        )
        subtitle.setObjectName("SectionText")
        subtitle.setWordWrap(True)
        left_header.addWidget(subtitle)

        header.addLayout(left_header, 1)

        self.run_btn = QPushButton("Executar validação")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setMinimumHeight(46)
        self.run_btn.setMinimumWidth(180)
        self.run_btn.clicked.connect(self.executar)
        header.addWidget(self.run_btn, 0, Qt.AlignRight | Qt.AlignTop)

        outer.addLayout(header)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        self.card_pdfs = PathCard(
            "ORIGEM",
            "Biblioteca de PDFs",
            "Escolha a pasta onde estão os arquivos que serão lidos pelo motor de validação.",
            "Selecionar PDFs",
            self.selecionar_pasta_pdfs,
        )
        top_row.addWidget(self.card_pdfs, 1)

        self.card_destino = PathCard(
            "DESTINO",
            "Saída dos arquivos",
            "Defina a pasta onde serão gravados o consolidado geral e os arquivos por período.",
            "Selecionar destino",
            self.selecionar_pasta_destino,
        )
        top_row.addWidget(self.card_destino, 1)

        outer.addLayout(top_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        outer.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(14)
        body.addLayout(left, 7)

        right = QVBoxLayout()
        right.setSpacing(14)
        body.addLayout(right, 4)

        flow_card = QFrame()
        flow_card.setObjectName("GlassCard")
        flow_layout = QVBoxLayout(flow_card)
        flow_layout.setContentsMargins(18, 16, 18, 16)
        flow_layout.setSpacing(10)

        l1 = QLabel("PROCESS FLOW")
        l1.setObjectName("SectionEyebrow")
        flow_layout.addWidget(l1)

        self.status_texto = QLabel("Pronto para iniciar.")
        self.status_texto.setObjectName("InfoValue")
        self.status_texto.setWordWrap(True)
        flow_layout.addWidget(self.status_texto)

        from PySide6.QtWidgets import QProgressBar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        flow_layout.addWidget(self.progress)

        self.progresso_texto = QLabel("0 / 0")
        self.progresso_texto.setObjectName("FieldText")
        flow_layout.addWidget(self.progresso_texto)

        left.addWidget(flow_card)

        log_card = QFrame()
        log_card.setObjectName("SoftCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(10)

        tx1 = QLabel("OUTPUT STREAM")
        tx1.setObjectName("SectionEyebrow")
        log_layout.addWidget(tx1)

        tx2 = QLabel("Acompanhe o arquivo atual, mensagens do processo e caminho final gerado.")
        tx2.setObjectName("FieldText")
        tx2.setWordWrap(True)
        log_layout.addWidget(tx2)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("A saída do processamento aparecerá aqui sem cortes.")
        self.saida.setMinimumHeight(300)
        log_layout.addWidget(self.saida, 1)

        left.addWidget(log_card, 1)

        summary_card = QFrame()
        summary_card.setObjectName("SoftCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(12)

        s1 = QLabel("EXECUTIVE SUMMARY")
        s1.setObjectName("SectionEyebrow")
        summary_layout.addWidget(s1)

        s2 = QLabel("Indicadores finais do processamento.")
        s2.setObjectName("FieldText")
        s2.setWordWrap(True)
        summary_layout.addWidget(s2)

        self.stat_pdfs = MetricBox("PDFs processados")
        self.stat_cfop = MetricBox("Linhas CFOP")
        self.stat_resumo = MetricBox("Linhas Resumo")
        self.stat_final = MetricBox("Arquivo final", "Nenhum arquivo gerado")

        summary_layout.addWidget(self.stat_pdfs)
        summary_layout.addWidget(self.stat_cfop)
        summary_layout.addWidget(self.stat_resumo)
        summary_layout.addWidget(self.stat_final)
        summary_layout.addStretch(1)

        right.addWidget(summary_card)

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
            self.status_texto.setText("Gerando arquivos Excel...")
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

        self.stat_pdfs.lb_v.setText(str(resultado["arquivos_pdf"]))
        self.stat_cfop.lb_v.setText(f'{resultado["linhas_cfop"]:,}'.replace(",", "."))
        self.stat_resumo.lb_v.setText(f'{resultado["linhas_resumo"]:,}'.replace(",", "."))
        self.stat_final.lb_v.setText(Path(resultado["arquivo_final"]).name)

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