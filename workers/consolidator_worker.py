#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
import time

from PySide6.QtCore import QThread, Signal

from validar_logic import (
    consolidar_final,
    exportar_versao_andersen,
    exportar_versao_vivo,
)
from log_service import log_async


class ConsolidatorProcessWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, base_dir, pasta_destino, machine_id=""):
        super().__init__()
        self.base_dir = base_dir
        self.pasta_destino = pasta_destino
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "consolidador_processamento_iniciado",
                      {"base_dir": self.base_dir})
        try:
            parquet_final, total_linhas, tempo_total, tipo_movimento = consolidar_final(
                self.base_dir,
                progress_callback=self.callback
            )

            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "consolidador_processamento_concluido",
                          {"tempo_s": elapsed, "linhas": total_linhas,
                           "tipo_movimento": tipo_movimento})

            self.sucesso.emit({
                "parquet_final": parquet_final,
                "total_linhas": total_linhas,
                "tempo_total": tempo_total,
                "tipo_movimento": tipo_movimento,
            })

        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "consolidador_processamento_erro", {"erro": erro})
            self.erro.emit(erro)


class ConsolidatorExportWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(str)
    erro = Signal(str)

    def __init__(self, modo, parquet_path, pasta_destino, tipo_movimento, machine_id=""):
        super().__init__()
        self.modo = modo
        self.parquet_path = parquet_path
        self.pasta_destino = pasta_destino
        self.tipo_movimento = tipo_movimento
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "consolidador_exportacao_iniciada",
                      {"modo": self.modo, "tipo_movimento": self.tipo_movimento})
        try:
            if self.modo == "andersen":
                caminho_saida = exportar_versao_andersen(
                    self.parquet_path,
                    self.pasta_destino,
                    tipo_movimento=self.tipo_movimento,
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

            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "consolidador_exportacao_concluida",
                          {"tempo_s": elapsed, "modo": self.modo})

            self.sucesso.emit(str(caminho_saida))

        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "consolidador_exportacao_erro", {"erro": erro})
            self.erro.emit(erro)
