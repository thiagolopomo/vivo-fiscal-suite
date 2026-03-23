#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
from PySide6.QtCore import QThread, Signal
from conferencia_logic import executar_conferencia


class ConferenceWorker(QThread):
    progresso = Signal(str, int, int, str)
    sucesso = Signal(dict)
    erro = Signal(str)

    def __init__(self, bases_selecionadas, livro_filtro, pasta_destino, meta_execucao):
        super().__init__()
        self.bases_selecionadas = bases_selecionadas
        self.livro_filtro = livro_filtro
        self.pasta_destino = pasta_destino
        self.meta_execucao = meta_execucao

    def run(self):
        try:
            self.progresso.emit("conferencia", 0, 1, "Montando conferência...")
            resultado = executar_conferencia(
                bases_selecionadas=self.bases_selecionadas,
                livro_filtro=self.livro_filtro,
                pasta_destino=self.pasta_destino,
                meta_execucao=self.meta_execucao,
            )
            self.progresso.emit("conferencia", 1, 1, resultado["arquivo_saida"])
            self.sucesso.emit(resultado)
        except Exception as e:
            erro = "".join(traceback.format_exception_only(type(e), e)).strip()
            self.erro.emit(erro)