#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QTextEdit, QSizePolicy, QProgressBar,
    QBoxLayout
)

from workers.consolidator_worker import ConsolidatorProcessWorker, ConsolidatorExportWorker
from pages.p9_page import PathCard, MetricBox, HoverCard, ResponsiveGrid


class ConsolidatorPage(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.export_worker = None
        self.parquet_cache_path = None
        self.tipo_movimento = None

        self._last_layout_mode = None
        self._last_action_mode = None
        self._last_paths_mode = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("PageCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(card, 1)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(8)

        # ── Premium Hero Header ──────────────────────────────────────
        hero = QFrame()
        hero.setObjectName("PageHeroCard")
        hero.setAttribute(Qt.WA_StyledBackground, True)
        hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 12, 16, 12)
        hero_layout.setSpacing(12)

        icon_frame = QFrame()
        icon_frame.setObjectName("AnaliseIconFrame")
        icon_frame.setFixedSize(36, 36)
        i_lay = QVBoxLayout(icon_frame)
        i_lay.setContentsMargins(0, 0, 0, 0)
        i_lb = QLabel("TXT")
        i_lb.setObjectName("AnaliseIconText")
        i_lb.setAlignment(Qt.AlignCenter)
        i_lb.setStyleSheet("font-size:10px; font-weight:800; color:#FFF; background:transparent;")
        i_lay.addWidget(i_lb)
        hero_layout.addWidget(icon_frame, 0, Qt.AlignVCenter)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(2)

        hero_title = QLabel("Consolidador Fiscal")
        hero_title.setStyleSheet("font-size:17px; font-weight:800; color:#182235; background:transparent;")
        hero_title.setWordWrap(True)
        hero_text_col.addWidget(hero_title)

        hero_desc = QLabel(
            "Consolide arquivos TXT fiscais em base interna e exporte no layout desejado."
        )
        hero_desc.setObjectName("FieldText")
        hero_desc.setWordWrap(True)
        hero_text_col.addWidget(hero_desc)

        hero_layout.addLayout(hero_text_col, 1)
        outer.addWidget(hero)

        # ── Divider ──────────────────────────────────────────────────
        divider = QFrame()
        divider.setObjectName("SectionDivider")
        divider.setAttribute(Qt.WA_StyledBackground, True)
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        # ── Path cards ───────────────────────────────────────────────
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
            "Pasta de saida",
            "Selecione a pasta onde serao salvos a base interna e os arquivos finais.",
            "Selecionar destino",
            self.selecionar_pasta_destino,
        )

        self.paths_layout.addWidget(self.card_base, 1)
        self.paths_layout.addWidget(self.card_destino, 1)
        outer.addLayout(self.paths_layout)

        # ── Action buttons ───────────────────────────────────────────
        self.action_row = QBoxLayout(QBoxLayout.LeftToRight)
        self.action_row.setSpacing(8)
        self.action_row.setContentsMargins(0, 0, 0, 0)

        self.btn_processar = QPushButton("Preparar base interna")
        self.btn_processar.setObjectName("PrimaryButton")
        self.btn_processar.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.btn_processar.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.btn_processar.clicked.connect(self.executar)

        self.btn_andersen = QPushButton("Exportar ANDERSEN")
        self.btn_andersen.setObjectName("SecondaryButton")
        self.btn_andersen.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.btn_andersen.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.btn_andersen.clicked.connect(self.exportar_andersen)

        self.btn_vivo = QPushButton("Exportar VIVO")
        self.btn_vivo.setObjectName("GhostButton")
        self.btn_vivo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.btn_vivo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.btn_vivo.setEnabled(False)
        self.btn_vivo.clicked.connect(self.exportar_vivo)

        self.action_row.addWidget(self.btn_processar, 0)
        self.action_row.addWidget(self.btn_andersen, 0)
        self.action_row.addWidget(self.btn_vivo, 0)
        self.action_row.addStretch(1)
        outer.addLayout(self.action_row)

        # ── Execution card ───────────────────────────────────────────
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

        self.status_texto = QLabel("Aguardando inicio...")
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

        # ── Bottom area (left panel + summary) ───────────────────────
        self.bottom_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(12)

        self.left_panel = QFrame()
        self.left_panel.setObjectName("TransparentPanel")
        self.left_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.left_col = QVBoxLayout(self.left_panel)
        self.left_col.setContentsMargins(0, 0, 0, 0)
        self.left_col.setSpacing(12)

        self.left_col.addWidget(self.exec_card, 0)

        # ── Stream / log card ────────────────────────────────────────
        self.stream_card = HoverCard()
        self.stream_card.setObjectName("PremiumLogCard")
        self.stream_card.setAttribute(Qt.WA_StyledBackground, True)
        self.stream_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stream_card.setMinimumHeight(50)

        stream_layout = QVBoxLayout(self.stream_card)
        stream_layout.setContentsMargins(10, 8, 10, 8)
        stream_layout.setSpacing(6)

        st_acc = QFrame()
        st_acc.setObjectName("CardAccentLine")
        st_acc.setAttribute(Qt.WA_StyledBackground, True)
        st_acc.setFixedHeight(2)
        stream_layout.addWidget(st_acc)

        st1 = QLabel("SAIDA DO PROCESSO")
        st1.setObjectName("SectionEyebrow")
        stream_layout.addWidget(st1)

        self.saida = QTextEdit()
        self.saida.setReadOnly(True)
        self.saida.setPlaceholderText("Os logs do processamento e da exportacao aparecerao aqui.")
        self.saida.setMinimumHeight(30)
        self.saida.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        stream_layout.addWidget(self.saida, 1)

        self.left_col.addWidget(self.stream_card, 1)

        # ── Summary card ─────────────────────────────────────────────
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

        self.metric_tipo = MetricBox("Tipo detectado")
        self.metric_linhas = MetricBox("Linhas")
        self.metric_base = MetricBox("Base interna", "Nenhuma base processada")

        self.metric_grid.addItemWidget(self.metric_tipo)
        self.metric_grid.addItemWidget(self.metric_linhas)
        self.metric_grid.addItemWidget(self.metric_base)

        summary_layout.addWidget(self.metric_grid)

        self.bottom_layout.addWidget(self.left_panel, 1)
        self.bottom_layout.addWidget(self.summary, 0)
        outer.addLayout(self.bottom_layout, 1)

        self._apply_responsive_mode()
        self._apply_scale_mode()

    # ── Responsive handling ──────────────────────────────────────────

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
        compact = h < 760

        # ── Paths direction ──────────────────────────────────────────
        if self._last_paths_mode != narrow:
            self._last_paths_mode = narrow
            self.paths_layout.setDirection(
                QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
            )

        # ── Action buttons direction + sizing ────────────────────────
        if self._last_action_mode != narrow:
            self._last_action_mode = narrow
            if narrow:
                self.action_row.setDirection(QBoxLayout.TopToBottom)
                self.btn_processar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.btn_andersen.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.btn_vivo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            else:
                self.action_row.setDirection(QBoxLayout.LeftToRight)
                self.btn_processar.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
                self.btn_andersen.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
                self.btn_vivo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        # ── Bottom layout + summary constraints ──────────────────────
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


    def _apply_scale_mode(self):
        w = self.width()
        if w >= 1200:
            self.metric_grid.min_item_width = 120
        elif w >= 1000:
            self.metric_grid.min_item_width = 130
        else:
            self.metric_grid.min_item_width = 100
        self.metric_grid._rebuild(force=True)

    # ── Logic methods (unchanged) ────────────────────────────────────

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
            self.status_texto.setText("Gerando exportacao final...")
            self.saida.setPlainText(detalhe)
        elif etapa == "finalizado_csv":
            self.status_texto.setText("Exportacao concluida.")
            self.saida.setPlainText(detalhe)

    def executar(self):
        base_dir = self.card_base.input.text().strip()
        pasta_destino = self.card_destino.input.text().strip()

        if not base_dir:
            QMessageBox.critical(self, "Erro", "Selecione a pasta base com os TXT.")
            return
        if not os.path.isdir(base_dir):
            QMessageBox.critical(self, "Erro", "A pasta base informada nao existe.")
            return
        if not pasta_destino:
            QMessageBox.critical(self, "Erro", "Selecione a pasta de destino.")
            return
        if not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "A pasta de destino informada nao existe.")
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
        self.saida.append("Bases internas de conferencia atualizadas: Andersen e Vivo.")

    def finalizar_erro(self, erro):
        self.btn_processar.setEnabled(True)
        self.btn_andersen.setEnabled(True)
        self.btn_vivo.setEnabled(bool(self.parquet_cache_path))
        self.status_texto.setText("Falha no processamento.")
        QMessageBox.critical(self, "Erro", f"Falha ao processar:\n{erro}")

    def _start_export(self, modo):
        if not self.parquet_cache_path or not Path(self.parquet_cache_path).exists():
            QMessageBox.critical(self, "Erro", "Nenhuma base processada foi encontrada.")
            return

        pasta_destino = self.card_destino.input.text().strip()
        if not pasta_destino or not os.path.isdir(pasta_destino):
            QMessageBox.critical(self, "Erro", "Selecione uma pasta de destino valida.")
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
        QMessageBox.information(self, "Sucesso", f"Exportacao concluida.\n\n{caminho}")

    def finalizar_export_erro(self, erro):
        self.btn_processar.setEnabled(True)
        self.btn_andersen.setEnabled(True)
        self.btn_vivo.setEnabled(True)
        self.status_texto.setText("Falha na exportacao.")
        QMessageBox.critical(self, "Erro", f"Falha ao exportar:\n{erro}")
