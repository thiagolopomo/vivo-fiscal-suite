#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
import time
from PySide6.QtCore import QThread, Signal
from ztmm_logic import consolidar_ztmm, exportar_ztmm_por_divisao
from ztmm_analise_logic import executar_analise_ztmm
from log_service import log_async


class ZtmmConsolidatorWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, pasta_txts, machine_id=""):
        super().__init__()
        self.pasta_txts = pasta_txts
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "ztmm_consolidacao_iniciada")
        try:
            parquet_path, total_linhas, divisoes = consolidar_ztmm(
                self.pasta_txts,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "ztmm_consolidacao_concluida",
                          {"tempo_s": elapsed, "linhas": total_linhas,
                           "divisoes": len(divisoes)})
            self.sucesso.emit({
                "parquet_path": parquet_path,
                "total_linhas": total_linhas,
                "divisoes": divisoes,
            })
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "ztmm_consolidacao_erro", {"erro": erro})
            self.erro.emit(erro)


class ZtmmExportWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(str)
    erro = Signal(str)

    def __init__(self, parquet_path, divisoes, pasta_destino, machine_id=""):
        super().__init__()
        self.parquet_path = parquet_path
        self.divisoes = divisoes
        self.pasta_destino = pasta_destino
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "ztmm_exportacao_iniciada",
                      {"divisoes": len(self.divisoes)})
        try:
            caminho = exportar_ztmm_por_divisao(
                self.parquet_path,
                self.divisoes,
                self.pasta_destino,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "ztmm_exportacao_concluida",
                          {"tempo_s": elapsed})
            self.sucesso.emit(caminho)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "ztmm_exportacao_erro", {"erro": erro})
            self.erro.emit(erro)


class ZtmmAnaliseWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, parquet_ztm, caminho_nc, pasta_razoes, pasta_destino, machine_id=""):
        super().__init__()
        self.parquet_ztm = parquet_ztm
        self.caminho_nc = caminho_nc
        self.pasta_razoes = pasta_razoes
        self.pasta_destino = pasta_destino
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "ztmm_analise_iniciada")
        try:
            resultado = executar_analise_ztmm(
                parquet_ztm=self.parquet_ztm,
                caminho_nc=self.caminho_nc,
                pasta_razoes=self.pasta_razoes,
                pasta_destino=self.pasta_destino,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "ztmm_analise_concluida",
                          {"tempo_s": elapsed})
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "ztmm_analise_erro", {"erro": erro})
            self.erro.emit(erro)
