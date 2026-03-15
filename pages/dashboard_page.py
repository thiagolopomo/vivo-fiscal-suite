#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from pages.p9_page import MetricBox


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("PageCard")
        root.addWidget(hero)

        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 22, 22, 22)
        hero_layout.setSpacing(14)

        e1 = QLabel("WORKSPACE OVERVIEW")
        e1.setObjectName("SectionEyebrow")
        hero_layout.addWidget(e1)

        t1 = QLabel("Operação fiscal centralizada")
        t1.setObjectName("SectionTitle")
        hero_layout.addWidget(t1)

        t2 = QLabel(
            "Acesse os módulos de validação e consolidação a partir da navegação lateral. "
            "Esta visão geral serve como ponto inicial do workspace."
        )
        t2.setObjectName("SectionText")
        t2.setWordWrap(True)
        hero_layout.addWidget(t2)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)

        stats_row.addWidget(MetricBox("Módulos principais", "2"), 1)
        stats_row.addWidget(MetricBox("Ambiente", "Corporativo"), 1)
        stats_row.addWidget(MetricBox("Status", "Pronto"), 1)

        hero_layout.addLayout(stats_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        root.addLayout(bottom_row, 1)

        left = QFrame()
        left.setObjectName("SoftCard")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        l1 = QLabel("VALIDAÇÃO P9")
        l1.setObjectName("SectionEyebrow")
        left_layout.addWidget(l1)

        l2 = QLabel("Leitura de PDFs fiscais")
        l2.setObjectName("FieldTitle")
        left_layout.addWidget(l2)

        l3 = QLabel(
            "Processamento de RAICMS em PDF com geração de consolidado, resumo executivo "
            "e acompanhamento da execução."
        )
        l3.setObjectName("FieldText")
        l3.setWordWrap(True)
        left_layout.addWidget(l3)

        left_layout.addStretch(1)
        bottom_row.addWidget(left, 1)

        right = QFrame()
        right.setObjectName("SoftCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(10)

        r1 = QLabel("CONSOLIDADOR FISCAL")
        r1.setObjectName("SectionEyebrow")
        right_layout.addWidget(r1)

        r2 = QLabel("Preparação e exportação de base")
        r2.setObjectName("FieldTitle")
        right_layout.addWidget(r2)

        r3 = QLabel(
            "Monte a base interna em parquet e depois gere exportações nos layouts "
            "necessários para operação e entrega."
        )
        r3.setObjectName("FieldText")
        r3.setWordWrap(True)
        right_layout.addWidget(r3)

        right_layout.addStretch(1)
        bottom_row.addWidget(right, 1)