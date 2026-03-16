#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QFontDatabase

_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

_ICON_CACHE = None
_LOGO_CACHE = {}
_FONT_FAMILY_CACHE = None


def caminho_recurso(*partes) -> str:
    return os.path.join(_BASE_DIR, *partes)


def obter_icone() -> QIcon:
    global _ICON_CACHE

    if _ICON_CACHE is not None:
        return _ICON_CACHE

    candidatos = [
        caminho_recurso("icone.ico"),
        caminho_recurso("icone.png"),
        caminho_recurso("logo_vivo.png"),
    ]

    for caminho in candidatos:
        if os.path.exists(caminho):
            _ICON_CACHE = QIcon(caminho)
            return _ICON_CACHE

    _ICON_CACHE = QIcon()
    return _ICON_CACHE


def carregar_logo_vivo(largura: int = 120):
    if largura in _LOGO_CACHE:
        return _LOGO_CACHE[largura]

    caminho = caminho_recurso("logo_vivo.png")
    if not os.path.exists(caminho):
        _LOGO_CACHE[largura] = None
        return None

    pix = QPixmap(caminho)
    if pix.isNull():
        _LOGO_CACHE[largura] = None
        return None

    escalado = pix.scaledToWidth(largura, Qt.SmoothTransformation)
    _LOGO_CACHE[largura] = escalado
    return escalado


def carregar_fontes_app() -> str:
    global _FONT_FAMILY_CACHE

    if _FONT_FAMILY_CACHE is not None:
        return _FONT_FAMILY_CACHE

    arquivos = [
        caminho_recurso("assets", "fonts", "Inter-Regular.ttf"),
        caminho_recurso("assets", "fonts", "Inter-Medium.ttf"),
        caminho_recurso("assets", "fonts", "Inter-SemiBold.ttf"),
        caminho_recurso("assets", "fonts", "Inter-Bold.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-Regular.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-Medium.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-SemiBold.ttf"),
        caminho_recurso("assets", "fonts", "Poppins-Bold.ttf"),
    ]

    familias = []
    for arq in arquivos:
        if os.path.exists(arq):
            font_id = QFontDatabase.addApplicationFont(arq)
            if font_id != -1:
                familias.extend(QFontDatabase.applicationFontFamilies(font_id))

    for preferida in ("Inter", "Poppins", "Montserrat"):
        if preferida in familias:
            _FONT_FAMILY_CACHE = preferida
            return _FONT_FAMILY_CACHE

    _FONT_FAMILY_CACHE = familias[0] if familias else "Segoe UI"
    return _FONT_FAMILY_CACHE