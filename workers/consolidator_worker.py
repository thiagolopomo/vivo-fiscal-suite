#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback

from PySide6.QtCore import QThread, Signal

from validar_logic import (
    consolidar_final,
    exportar_versao_andersen,
    exportar_versao_vivo,
)


class ConsolidatorProcessWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, base_dir, pasta_destino):
        super().__init__()
        self.base_dir = base_dir
        self.pasta_destino = pasta_destino

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        try:
            parquet_final, total_linhas, tempo_total, tipo_movimento = consolidar_final(
                self.base_dir,
                progress_callback=self.callback
            )

            self.sucesso.emit({
                "parquet_final": parquet_final,
                "total_linhas": total_linhas,
                "tempo_total": tempo_total,
                "tipo_movimento": tipo_movimento,
            })

        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)


class ConsolidatorExportWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(str)
    erro = Signal(str)

    def __init__(self, modo, parquet_path, pasta_destino, tipo_movimento):
        super().__init__()
        self.modo = modo
        self.parquet_path = parquet_path
        self.pasta_destino = pasta_destino
        self.tipo_movimento = tipo_movimento

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        try:
            if self.modo == "andersen":
                caminho_saida = exportar_versao_andersen(
                    self.parquet_path,
                    self.pasta_destino,
                    progress_callback=self.callback
                )
            elif self.modo == "vivo":
                caminho_saida = exportar_versao_vivo(
                    self.parquet_path,
                    self.pasta_destino,
                    self.tipo_movimento,
                    progress_callback=self.callback
                )
            else:
                raise ValueError(f"Modo de exportação inválido: {self.modo}")

            if not caminho_saida:
                caminho_saida = self.pasta_destino

            self.sucesso.emit(str(caminho_saida))

        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)