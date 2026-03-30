#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
import time

from PySide6.QtCore import QThread, Signal
from raicms_logic import processar_raicms
from log_service import log_async


class P9Worker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, pasta_pdfs, pasta_destino, machine_id=""):
        super().__init__()
        self.pasta_pdfs = pasta_pdfs
        self.pasta_destino = pasta_destino
        self.machine_id = machine_id

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        t0 = time.time()
        if self.machine_id:
            log_async(self.machine_id, "p9_processamento_iniciado",
                      {"pasta": self.pasta_pdfs})
        try:
            resultado = processar_raicms(
                pasta_pdfs=self.pasta_pdfs,
                pasta_destino=self.pasta_destino,
                progress_callback=self.callback,
            )
            elapsed = round(time.time() - t0, 1)
            if self.machine_id:
                log_async(self.machine_id, "p9_processamento_concluido",
                          {"tempo_s": elapsed, "pdfs": resultado.get("total_pdfs", 0)})
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            if self.machine_id:
                log_async(self.machine_id, "p9_processamento_erro", {"erro": erro})
            self.erro.emit(erro)
