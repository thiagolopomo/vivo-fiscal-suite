#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QFontDatabase


def caminho_recurso(*partes) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *partes)


def obter_icone() -> QIcon:
    candidatos = [
        caminho_recurso("icone.ico"),
        caminho_recurso("icone.png"),
        caminho_recurso("logo_vivo.png"),
    ]
    for caminho in candidatos:
        if os.path.exists(caminho):
            return QIcon(caminho)
    return QIcon()


def carregar_logo_vivo(largura: int = 120):
    caminho = caminho_recurso("logo_vivo.png")
    if not os.path.exists(caminho):
        return None

    pix = QPixmap(caminho)
    if pix.isNull():
        return None

    return pix.scaledToWidth(largura, Qt.SmoothTransformation)


def carregar_fontes_app() -> str:
    arquivos = [
        caminho_recurso("assets", "fonts", "Poppins-Regular.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-Medium.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-SemiBold.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-Bold.ttf"),
        caminho_recurso("assets", "fonts", "Inter-Regular.ttf"),
        caminho_recurso("assets", "fonts", "Inter-Medium.ttf"),
        caminho_recurso("assets", "fonts", "Inter-SemiBold.ttf"),
        caminho_recurso("assets", "fonts", "Inter-Bold.ttf"),
    ]

    familias = []
    for arq in arquivos:
        if os.path.exists(arq):
            font_id = QFontDatabase.addApplicationFont(arq)
            if font_id != -1:
                familias.extend(QFontDatabase.applicationFontFamilies(font_id))

    for preferida in ("Poppins", "Inter", "Montserrat"):
        if preferida in familias:
            return preferida

    return familias[0] if familias else "Segoe UI"