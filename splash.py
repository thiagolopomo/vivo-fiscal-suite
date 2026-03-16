#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient,
    QPen, QFont
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QGraphicsDropShadowEffect
)

from resources import carregar_logo_vivo


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(980, 560)
        self.setMinimumSize(860, 500)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.valor = 0
        self._callback_final = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)

        self.card = QFrame()
        self.card.setObjectName("SplashCard")
        root.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(70)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(48, 0, 76, 120))
        self.card.setGraphicsEffect(shadow)

        main = QHBoxLayout(self.card)
        main.setContentsMargins(44, 38, 44, 34)
        main.setSpacing(28)

        # =========================
        # LEFT
        # =========================
        left = QVBoxLayout()
        left.setSpacing(0)
        main.addLayout(left, 7)

        top_row = QHBoxLayout()
        top_row.addStretch()

        self.logo = QLabel()
        self.logo.setAttribute(Qt.WA_TranslucentBackground)
        pix = carregar_logo_vivo(120)
        if pix:
            self.logo.setPixmap(pix)
        top_row.addWidget(self.logo, alignment=Qt.AlignRight)

        left.addLayout(top_row)
        left.addSpacing(18)

        self.badge = QLabel("FISCAL WORKSPACE")
        self.badge.setStyleSheet("""
            QLabel {
                background: rgba(255,255,255,0.10);
                color: rgba(255,255,255,0.92);
                border: none;
                border-radius: 14px;
                padding: 7px 14px;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1.8px;
            }
        """)
        self.badge.setMaximumWidth(170)
        left.addWidget(self.badge, 0, Qt.AlignLeft)

        left.addSpacing(22)

        self.title = QLabel("VIVO Fiscal Suite")
        self.title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 40px;
                font-weight: 700;
                letter-spacing: -0.4px;
                background: transparent;
            }
        """)
        left.addWidget(self.title)

        left.addSpacing(10)

        self.subtitle = QLabel(
            "Validação P9 e Consolidador Fiscal em uma experiência mais limpa, "
            "corporativa e sofisticada."
        )
        self.subtitle.setWordWrap(True)
        self.subtitle.setMaximumWidth(620)
        self.subtitle.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.78);
                font-size: 15px;
                font-weight: 400;
                line-height: 1.45;
                background: transparent;
            }
        """)
        left.addWidget(self.subtitle)

        left.addSpacing(24)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        for txt in ["PDF Validation", "TXT Consolidation", "Corporate Flow"]:
            lb = QLabel(txt)
            lb.setStyleSheet("""
                QLabel {
                    background: rgba(255,255,255,0.08);
                    color: rgba(255,255,255,0.88);
                    border: none;
                    border-radius: 12px;
                    padding: 8px 12px;
                    font-size: 11px;
                    font-weight: 500;
                }
            """)
            chips.addWidget(lb, 0, Qt.AlignLeft)
        chips.addStretch()
        left.addLayout(chips)

        left.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(16)

        self.env_label = QLabel("Ambiente corporativo Vivo")
        self.env_label.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.72);
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
        """)

        self.sep = QLabel("•")
        self.sep.setStyleSheet("color: rgba(255,255,255,0.45); font-size: 12px;")

        self.mode_label = QLabel("Inicialização segura do workspace")
        self.mode_label.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.72);
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
        """)

        footer.addWidget(self.env_label, 0, Qt.AlignLeft)
        footer.addWidget(self.sep, 0, Qt.AlignLeft)
        footer.addWidget(self.mode_label, 0, Qt.AlignLeft)
        footer.addStretch()

        left.addLayout(footer)

        # =========================
        # RIGHT
        # =========================
        right_wrap = QVBoxLayout()
        right_wrap.addStretch()
        main.addLayout(right_wrap, 4)

        self.load_panel = QFrame()
        self.load_panel.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 28px;
            }
        """)
        right_wrap.addWidget(self.load_panel)

        panel_layout = QVBoxLayout(self.load_panel)
        panel_layout.setContentsMargins(24, 22, 24, 22)
        panel_layout.setSpacing(14)

        self.panel_kicker = QLabel("STARTUP FLOW")
        self.panel_kicker.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.64);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2.2px;
                background: transparent;
            }
        """)
        panel_layout.addWidget(self.panel_kicker)

        self.panel_title = QLabel("Preparando sua suíte fiscal")
        self.panel_title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 19px;
                font-weight: 600;
                background: transparent;
            }
        """)
        panel_layout.addWidget(self.panel_title)

        self.panel_desc = QLabel(
            "Carregando interface, módulos e recursos essenciais para iniciar o workspace."
        )
        self.panel_desc.setWordWrap(True)
        self.panel_desc.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.74);
                font-size: 12px;
                font-weight: 400;
                line-height: 1.45;
                background: transparent;
            }
        """)
        panel_layout.addWidget(self.panel_desc)

        panel_layout.addSpacing(8)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(14)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: rgba(255,255,255,0.18);
                border: none;
                border-radius: 7px;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E6CCFF,
                    stop:0.55 #B76CFF,
                    stop:1 #6F02B5
                );
            }
        """)
        panel_layout.addWidget(self.progress)

        info = QHBoxLayout()
        info.setSpacing(10)

        self.status = QLabel("Inicializando ambiente...")
        self.status.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.86);
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
        """)
        info.addWidget(self.status, 1)

        self.percent = QLabel("0%")
        self.percent.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: 700;
                background: transparent;
            }
        """)
        info.addWidget(self.percent, 0, Qt.AlignRight)

        panel_layout.addLayout(info)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._avancar)

        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(420)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

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
            self.status.setText("Carregando identidade visual...")
        elif self.valor <= 40:
            self.status.setText("Preparando módulos fiscais...")
        elif self.valor <= 70:
            self.status.setText("Validando recursos do sistema...")
        elif self.valor <= 90:
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

        rect = self.rect().adjusted(18, 18, -18, -18)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 34, 34)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.00, QColor("#120417"))
        grad.setColorAt(0.18, QColor("#241034"))
        grad.setColorAt(0.45, QColor("#4A126E"))
        grad.setColorAt(0.72, QColor("#6F02B5"))
        grad.setColorAt(1.00, QColor("#9B3AF0"))
        painter.fillPath(path, grad)

        glow_left = QRadialGradient(rect.left() + 160, rect.top() + 120, 340)
        glow_left.setColorAt(0.0, QColor(255, 255, 255, 24))
        glow_left.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, glow_left)

        glow_right = QRadialGradient(rect.right() - 90, rect.bottom() - 40, 300)
        glow_right.setColorAt(0.0, QColor(255, 255, 255, 34))
        glow_right.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, glow_right)

        # Linhas decorativas discretas
        painter.save()
        painter.setClipPath(path)

        pen = QPen(QColor(255, 255, 255, 18))
        pen.setWidth(1)
        painter.setPen(pen)
        for y in (rect.top() + 86, rect.top() + 116, rect.bottom() - 84):
            painter.drawLine(rect.left() + 36, y, rect.right() - 36, y)

        painter.restore()

        border_pen = QPen(QColor(255, 255, 255, 26))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawPath(path)