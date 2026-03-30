#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
import time
from PySide6.QtCore import QThread, Signal
from conferencia_logic import executar_conferencia
from log_service import log_async


class ConferenceWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, bases_selecionadas, livro_filtro, pasta_destino, meta_execucao, machine_id=""):
        super().__init__()
        self.bases_selecionadas = bases_selecionadas
        self.livro_filtro = livro_filtro
        self.pasta_destino = pasta_destino
        self.meta_execucao = meta_execucao
        self.machine_id = machine_id

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "conferencia_iniciada",
                      {"bases": len(self.bases_selecionadas)})
        try:
            self.progresso.emit("conferencia", 0, 1, "Montando conferência...")
            resultado = executar_conferencia(
                bases_selecionadas=self.bases_selecionadas,
                livro_filtro=self.livro_filtro,
                pasta_destino=self.pasta_destino,
                meta_execucao=self.meta_execucao,
            )
            self.progresso.emit("conferencia", 1, 1, resultado["arquivo_saida"])
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "conferencia_concluida",
                          {"tempo_s": elapsed})
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "conferencia_erro", {"erro": erro})
            self.erro.emit(erro)
