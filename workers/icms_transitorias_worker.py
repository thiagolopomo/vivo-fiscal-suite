#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import traceback
from PySide6.QtCore import QThread, Signal

from icms_transitorias_logic import (
    consolidar_razoes,
    validar_contra_balancete,
    extrair_razoes_aa,
    extrair_transitorias_livro,
)
from log_service import log_async


class TransitConsolidatorWorker(QThread):
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
            log_async(self.machine_id, "transit_consolidacao_iniciada")
        try:
            parquet_path, total_linhas, total_contas = consolidar_razoes(
                self.pasta_txts,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(
                    self.machine_id,
                    "transit_consolidacao_concluida",
                    {"tempo_s": elapsed, "linhas": total_linhas, "contas": total_contas},
                )
            self.sucesso.emit({
                "parquet_path": parquet_path,
                "total_linhas": total_linhas,
                "total_contas": total_contas,
                "tempo_s": elapsed,
            })
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "transit_consolidacao_erro", {"erro": erro})
            self.erro.emit(erro)


class TransitExtracaoAAWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, parquet_razoes, destino, tipo_filtro, machine_id=""):
        super().__init__()
        self.parquet_razoes = parquet_razoes
        self.destino = destino
        self.tipo_filtro = tipo_filtro  # "WE", "WL" ou "BOTH"
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(
                self.machine_id,
                "transit_extracao_aa_iniciada",
                {"tipo_filtro": self.tipo_filtro},
            )
        try:
            resultado = extrair_razoes_aa(
                self.parquet_razoes,
                self.destino,
                tipo_filtro=self.tipo_filtro,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(
                    self.machine_id,
                    "transit_extracao_aa_concluida",
                    {
                        "tempo_s": elapsed,
                        "linhas": resultado["linhas"],
                        "tipo_filtro": self.tipo_filtro,
                    },
                )
            resultado["tempo_s"] = elapsed
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(
                    self.machine_id,
                    "transit_extracao_aa_erro",
                    {"erro": erro, "tipo_filtro": self.tipo_filtro},
                )
            self.erro.emit(erro)


class TransitLivroExtractWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, caminho_livro, destino, tipo_movimento, machine_id=""):
        super().__init__()
        self.caminho_livro = caminho_livro
        self.destino = destino
        self.tipo_movimento = tipo_movimento  # "ENTRADA" ou "SAIDA"
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(
                self.machine_id,
                "transit_livro_extracao_iniciada",
                {"tipo": self.tipo_movimento},
            )
        try:
            resultado = extrair_transitorias_livro(
                self.caminho_livro,
                self.destino,
                tipo_movimento=self.tipo_movimento,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(
                    self.machine_id,
                    "transit_livro_extracao_concluida",
                    {
                        "tempo_s": elapsed,
                        "linhas": resultado["linhas"],
                        "tipo": resultado["tipo"],
                    },
                )
            resultado["tempo_s"] = elapsed
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(
                    self.machine_id,
                    "transit_livro_extracao_erro",
                    {"erro": erro, "tipo": self.tipo_movimento},
                )
            self.erro.emit(erro)


class TransitValidacaoWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, parquet_razoes, caminho_balancete, machine_id=""):
        super().__init__()
        self.parquet_razoes = parquet_razoes
        self.caminho_balancete = caminho_balancete
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "transit_validacao_iniciada")
        try:
            resultado = validar_contra_balancete(
                self.parquet_razoes,
                self.caminho_balancete,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(
                    self.machine_id,
                    "transit_validacao_concluida",
                    {
                        "tempo_s": elapsed,
                        "total_contas": resultado["total_contas"],
                        "batendo": resultado["batendo"],
                        "divergentes": resultado["divergentes"],
                    },
                )
            # Não enviamos o DataFrame inteiro pelo signal — a UI lê do parquet.
            payload = {k: v for k, v in resultado.items() if k != "df_validacao"}
            payload["tempo_s"] = elapsed
            self.sucesso.emit(payload)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "transit_validacao_erro", {"erro": erro})
            self.erro.emit(erro)
