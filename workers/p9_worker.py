#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback

from PySide6.QtCore import QThread, Signal
from raicms_logic import processar_raicms


class P9Worker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, pasta_pdfs, pasta_destino):
        super().__init__()
        self.pasta_pdfs = pasta_pdfs
        self.pasta_destino = pasta_destino

    def callback(self, etapa, atual, total, detalhe):
        self.progresso.emit(etapa, atual, total, detalhe)

    def run(self):
        try:
            resultado = processar_raicms(
                pasta_pdfs=self.pasta_pdfs,
                pasta_destino=self.pasta_destino,
                progress_callback=self.callback,
            )
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)