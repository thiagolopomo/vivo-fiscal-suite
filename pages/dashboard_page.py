#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect
)


class ResponsiveGrid(QWidget):
    def __init__(self, min_item_width=220, parent=None):
        super().__init__(parent)
        self.min_item_width = min_item_width
        self.items = []

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(10)

    def addItemWidget(self, widget):
        self.items.append(widget)
        self._rebuild()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild()

    def _rebuild(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        if not self.items:
            return

        width = max(1, self.width())
        cols = max(1, width // self.min_item_width)
        cols = min(cols, len(self.items))

        for i, w in enumerate(self.items):
            row = i // cols
            col = i % cols
            self._layout.addWidget(w, row, col)


class HoverCard(QFrame):
    def __init__(self):
        super().__init__()

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(16)
        self._shadow.setOffset(0, 3)
        self._shadow.setColor(QColor(103, 46, 180, 24))
        self.setGraphicsEffect(self._shadow)

        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim_blur.setDuration(180)
        self._anim_blur.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"offset", self)
        self._anim_offset.setDuration(180)
        self._anim_offset.setEasingCurve(QEasingCurve.OutCubic)

        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._anim_blur.stop()
        self._anim_blur.setStartValue(self._shadow.blurRadius())
        self._anim_blur.setEndValue(24)
        self._anim_blur.start()

        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._shadow.offset())
        self._anim_offset.setEndValue(QPointF(0, 5))
        self._anim_offset.start()

        self._shadow.setColor(QColor(132, 56, 220, 55))

        self.setProperty("hover", True)
        self.style().unpolish(self)
        self.style().polish(self)

        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim_blur.stop()
        self._anim_blur.setStartValue(self._shadow.blurRadius())
        self._anim_blur.setEndValue(16)
        self._anim_blur.start()

        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._shadow.offset())
        self._anim_offset.setEndValue(QPointF(0, 3))
        self._anim_offset.start()

        self._shadow.setColor(QColor(103, 46, 180, 24))

        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)

        super().leaveEvent(event)


class ModuleIcon(QFrame):
    def __init__(self, text: str):
        super().__init__()
        self.setObjectName("ModuleIcon")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(42, 42)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        lb = QLabel(text)
        lb.setObjectName("ModuleIconText")
        lb.setAlignment(Qt.AlignCenter)
        layout.addWidget(lb)


class StatCard(HoverCard):
    def __init__(self, icon, label, value):
        super().__init__()

        self.setObjectName("StatCard")
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        accent = QFrame()
        accent.setObjectName("StatAccentLine")
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        top = QHBoxLayout()
        top.setSpacing(8)

        ic = QLabel(icon)
        ic.setObjectName("StatIcon")
        ic.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        lb = QLabel(label)
        lb.setObjectName("StatLabel")
        lb.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        top.addWidget(ic, 0)
        top.addWidget(lb, 0)
        top.addStretch(1)

        layout.addLayout(top)

        val = QLabel(value)
        val.setObjectName("StatValue")
        val.setWordWrap(True)

        layout.addWidget(val)
        layout.addStretch(1)        


class DetailCard(HoverCard):
    def __init__(self, eyebrow, icon_text, titulo, descricao, bullets):
        super().__init__()

        self.setObjectName("WorkspaceModuleCard")
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)

        icon = ModuleIcon(icon_text)
        top.addWidget(icon, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        lb1 = QLabel(eyebrow)
        lb1.setObjectName("SectionEyebrow")
        text_col.addWidget(lb1)

        lb2 = QLabel(titulo)
        lb2.setObjectName("FieldTitle")
        lb2.setWordWrap(True)
        text_col.addWidget(lb2)

        top.addLayout(text_col, 1)
        top.addStretch(1)

        layout.addLayout(top)

        lb3 = QLabel(descricao)
        lb3.setObjectName("FieldText")
        lb3.setWordWrap(True)
        layout.addWidget(lb3)

        bullets_wrap = QVBoxLayout()
        bullets_wrap.setSpacing(7)

        for item in bullets:
            row = QHBoxLayout()
            row.setSpacing(8)

            dot = QLabel("•")
            dot.setObjectName("FieldText")
            dot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            txt = QLabel(item)
            txt.setObjectName("FieldText")
            txt.setWordWrap(True)

            row.addWidget(dot, 0)
            row.addWidget(txt, 1)
            bullets_wrap.addLayout(row)

        layout.addLayout(bullets_wrap)
        layout.addStretch(1)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # HERO / DESTAQUE
        hero = QFrame()
        hero.setObjectName("WorkspaceHero")
        hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(hero)

        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 20, 20, 20)
        hero_layout.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(6)

        e1 = QLabel("WORKSPACE")
        e1.setObjectName("SectionEyebrow")
        header.addWidget(e1)

        t1 = QLabel("Operação fiscal centralizada")
        t1.setObjectName("HeroTitle")
        t1.setWordWrap(True)
        header.addWidget(t1)

        t2 = QLabel("Acesse os módulos pela lateral e acompanhe o status geral do ambiente.")
        t2.setObjectName("HeroText")
        t2.setWordWrap(True)
        header.addWidget(t2)

        hero_layout.addLayout(header)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("SectionDivider")
        hero_layout.addWidget(divider)

        self.stats_wrap = ResponsiveGrid(min_item_width=210)

        self.stat_modulos = StatCard("◫", "Módulos", "3")
        self.stat_ambiente = StatCard("◩", "Ambiente", "Corporativo")
        self.stat_status = StatCard("●", "Status", "Pronto")
        self.stat_fluxo = StatCard("◇", "Fluxo", "PDF + TXT + SAP")

        self.stats_wrap.addItemWidget(self.stat_modulos)
        self.stats_wrap.addItemWidget(self.stat_ambiente)
        self.stats_wrap.addItemWidget(self.stat_status)
        self.stats_wrap.addItemWidget(self.stat_fluxo)

        hero_layout.addWidget(self.stats_wrap)

        # MÓDULOS
        self.modules_wrap = ResponsiveGrid(min_item_width=300)

        self.card_p9 = DetailCard(
            "VALIDAÇÃO P9",
            "PDF",
            "Leitura de PDFs fiscais",
            "Importa PDFs de RAICMS, processa os dados e gera o consolidado final em Excel.",
            [
                "Seleciona a pasta de origem dos PDFs fiscais.",
                "Gera consolidado e estruturas auxiliares em Excel.",
                "Exibe progresso e saída do processamento na própria tela.",
            ]
        )

        self.card_con = DetailCard(
            "CONSOLIDADOR FISCAL",
            "TXT",
            "Base interna e exportação",
            "Lê TXT fiscais, monta a base interna em parquet e exporta no layout necessário.",
            [
                "Consolida a base TXT em estrutura interna reutilizável.",
                "Permite exportação em formatos ANDERSEN e VIVO.",
                "Mostra andamento, logs e resumo do resultado final.",
            ]
        )

        self.card_ztmm = DetailCard(
            "ZTMM X LIVRO",
            "SAP",
            "Conciliação ZTMM x Livro",
            "Consolida TXTs ZTMM do SAP, exporta por divisão e executa análise de conciliação.",
            [
                "Consolida arquivos TXT SAP em base interna parquet.",
                "Exporta CSVs filtrados por divisão selecionada.",
                "Concilia NC com ZTMM, enriquecendo com ICMS, ST e Razões.",
            ]
        )

        self.modules_wrap.addItemWidget(self.card_p9)
        self.modules_wrap.addItemWidget(self.card_con)
        self.modules_wrap.addItemWidget(self.card_ztmm)

        root.addWidget(self.modules_wrap)

        # FLUXO
        fluxo = QFrame()
        fluxo.setObjectName("WorkspaceBand")
        fluxo.setMinimumHeight(150)
        fluxo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(fluxo)

        fluxo_layout = QVBoxLayout(fluxo)
        fluxo_layout.setContentsMargins(18, 16, 18, 16)
        fluxo_layout.setSpacing(8)

        f1 = QLabel("FLUXO")
        f1.setObjectName("SectionEyebrow")
        fluxo_layout.addWidget(f1)

        f2 = QLabel("Como o workspace é usado")
        f2.setObjectName("FieldTitle")
        fluxo_layout.addWidget(f2)

        f3 = QLabel(
            "1. PDFs entram pela Validação P9.\n"
            "2. Arquivos TXT entram pelo Consolidador Fiscal.\n"
            "3. TXTs SAP entram pelo ZTMM x Livro para conciliação.\n"
            "4. O resultado final é salvo na pasta de destino escolhida.\n"
            "5. O acompanhamento de progresso acontece dentro de cada módulo."
        )
        f3.setObjectName("FieldText")
        f3.setWordWrap(True)
        fluxo_layout.addWidget(f3)