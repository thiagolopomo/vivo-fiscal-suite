#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback
from PySide6.QtCore import QThread, Signal
from ztmm_logic import consolidar_ztmm, exportar_ztmm_por_divisao
from ztmm_analise_logic import executar_analise_ztmm


class ZtmmConsolidatorWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, pasta_txts):
        super().__init__()
        self.pasta_txts = pasta_txts

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        try:
            parquet_path, total_linhas, divisoes = consolidar_ztmm(
                self.pasta_txts,
                progress_callback=self.callback,
            )
            self.sucesso.emit({
                "parquet_path": parquet_path,
                "total_linhas": total_linhas,
                "divisoes": divisoes,
            })
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)


class ZtmmExportWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(str)
    erro = Signal(str)

    def __init__(self, parquet_path, divisoes, pasta_destino):
        super().__init__()
        self.parquet_path = parquet_path
        self.divisoes = divisoes
        self.pasta_destino = pasta_destino

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        try:
            caminho = exportar_ztmm_por_divisao(
                self.parquet_path,
                self.divisoes,
                self.pasta_destino,
                progress_callback=self.callback,
            )
            self.sucesso.emit(caminho)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)


class ZtmmAnaliseWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, parquet_ztm, caminho_nc, pasta_razoes, pasta_destino):
        super().__init__()
        self.parquet_ztm = parquet_ztm
        self.caminho_nc = caminho_nc
        self.pasta_razoes = pasta_razoes
        self.pasta_destino = pasta_destino

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        try:
            resultado = executar_analise_ztmm(
                parquet_ztm=self.parquet_ztm,
                caminho_nc=self.caminho_nc,
                pasta_razoes=self.pasta_razoes,
                pasta_destino=self.pasta_destino,
                progress_callback=self.callback,
            )
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)
