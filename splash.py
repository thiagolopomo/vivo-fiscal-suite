#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame, QGraphicsDropShadowEffect

from resources import carregar_logo_vivo


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(900, 520)
        self.setMinimumSize(760, 450)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.valor = 0
        self._callback_final = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)

        self.card = QFrame()
        root.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(64)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(78, 8, 132, 110))
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(38, 32, 38, 30)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.addStretch()

        logo = QLabel()
        logo.setAttribute(Qt.WA_TranslucentBackground)
        pix = carregar_logo_vivo(110)
        if pix:
            logo.setPixmap(pix)
        top.addWidget(logo, alignment=Qt.AlignRight)
        layout.addLayout(top)

        layout.addSpacing(16)

        self.title = QLabel("VIVO Fiscal Suite")
        self.title.setStyleSheet("color:white;font-size:34px;font-weight:700;background:transparent;")
        layout.addWidget(self.title)

        self.subtitle = QLabel("Validação P9 e Consolidador Fiscal em uma experiência única, premium e corporativa.")
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet("color:rgba(255,255,255,0.84);font-size:13px;font-weight:500;background:transparent;")
        layout.addWidget(self.subtitle)

        layout.addSpacing(18)

        badges = QHBoxLayout()
        for txt in ["PDF Intelligence", "Fiscal Workspace", "Enterprise Flow"]:
            tag = QLabel(txt)
            tag.setStyleSheet("""
                QLabel{
                    background:rgba(255,255,255,0.12);
                    color:white;
                    border:1px solid rgba(255,255,255,0.18);
                    border-radius:15px;
                    padding:6px 12px;
                    font-size:10px;
                    font-weight:700;
                }
            """)
            badges.addWidget(tag, 0, Qt.AlignLeft)
        badges.addStretch()
        layout.addLayout(badges)

        layout.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        left_box = QFrame()
        left_box.setStyleSheet("""
            QFrame{
                background:rgba(255,255,255,0.10);
                border:1px solid rgba(255,255,255,0.14);
                border-radius:24px;
            }
        """)
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(22, 18, 22, 18)
        left_layout.setSpacing(4)

        left_layout.addWidget(self._lbl("AMBIENTE", "rgba(255,255,255,0.72)", 10, 700, 1.5))
        left_layout.addWidget(self._lbl("VIVO", "white", 28, 700))
        left_layout.addWidget(self._lbl("Software corporativo premium", "rgba(255,255,255,0.82)", 12, 500))
        bottom.addWidget(left_box, 1)

        right_box = QFrame()
        right_box.setStyleSheet("""
            QFrame{
                background:rgba(255,255,255,0.14);
                border:1px solid rgba(255,255,255,0.18);
                border-radius:24px;
            }
        """)
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(22, 18, 22, 18)
        right_layout.setSpacing(10)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        right_layout.addWidget(self.progress)

        info = QHBoxLayout()
        self.status = self._lbl("Inicializando workspace...", "rgba(255,255,255,0.88)", 12, 600)
        info.addWidget(self.status)
        info.addStretch()
        self.percent = self._lbl("0%", "white", 12, 700)
        info.addWidget(self.percent)
        right_layout.addLayout(info)

        bottom.addWidget(right_box, 3)
        layout.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._avancar)

        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(420)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def _lbl(self, txt, color, size, weight, spacing=0):
        lb = QLabel(txt)
        lb.setStyleSheet(
            f"color:{color};font-size:{size}px;font-weight:{weight};"
            f"letter-spacing:{spacing}px;background:transparent;"
        )
        return lb

    def iniciar(self, callback_final):
        self._callback_final = callback_final
        self.setWindowOpacity(0.0)
        self.show()
        self.anim.start()
        self.timer.start(24)

    def _avancar(self):
        self.valor += 2
        if self.valor > 100:
            self.valor = 100

        self.progress.setValue(self.valor)
        self.percent.setText(f"{self.valor}%")

        if self.valor <= 18:
            self.status.setText("Carregando interface premium...")
        elif self.valor <= 42:
            self.status.setText("Preparando módulos fiscais...")
        elif self.valor <= 72:
            self.status.setText("Validando recursos do sistema...")
        elif self.valor <= 92:
            self.status.setText("Organizando workspace...")
        else:
            self.status.setText("Abrindo suíte fiscal...")

        if self.valor >= 100:
            self.timer.stop()
            QTimer.singleShot(220, self._finalizar)

    def _finalizar(self):
        self.close()
        if self._callback_final:
            self._callback_final()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(20, 20, -20, -20)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 30, 30)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor("#18081F"))
        grad.setColorAt(0.24, QColor("#341149"))
        grad.setColorAt(0.55, QColor("#5C1490"))
        grad.setColorAt(0.80, QColor("#6F02B5"))
        grad.setColorAt(1.0, QColor("#8A35D8"))
        painter.fillPath(path, grad)

        glow1 = QRadialGradient(rect.left() + 190, rect.top() + 120, 280)
        glow1.setColorAt(0.0, QColor(255, 255, 255, 38))
        glow1.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, glow1)

        glow2 = QRadialGradient(rect.right() - 160, rect.bottom() - 100, 320)
        glow2.setColorAt(0.0, QColor(255, 255, 255, 24))
        glow2.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, glow2)

        pen = QPen(QColor(255, 255, 255, 32))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)