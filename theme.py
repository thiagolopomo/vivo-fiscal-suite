#!/usr/bin/env python
# -*- coding: utf-8 -*-

def build_app_qss(font_family: str = "Segoe UI") -> str:
    return f"""
    * {{
        font-family: "{font_family}", "Inter", "Segoe UI", sans-serif;
        outline: none;
    }}

    QWidget {{
        background: #F5F7FB;
        color: #1E2430;
        font-size: 13px;
    }}

    QMainWindow, QDialog {{
        background: #F5F7FB;
    }}

    QLabel {{
        background: transparent;
    }}

    QFrame {{
        border: none;
        background: transparent;
    }}

    #ShellRoot {{
        background: #F5F7FB;
    }}

    #Sidebar {{
        background: #FFFFFF;
        border-right: 1px solid #E7EBF3;
    }}

    #BrandCard {{
        background: #FFFFFF;
        border: 1px solid #ECEFF5;
        border-radius: 20px;
    }}

    #BrandTitle {{
        color: #1F2430;
        font-size: 20px;
        font-weight: 700;
    }}

    #BrandSubtitle {{
        color: #7C8798;
        font-size: 12px;
        font-weight: 500;
    }}

    #SidebarSection {{
        color: #8D97A8;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.6px;
    }}

    #SidebarPanel {{
        background: #FFFFFF;
        border: 1px solid #ECEFF5;
        border-radius: 20px;
    }}

    QPushButton#NavButton {{
        background: #FFFFFF;
        color: #324055;
        border: 1px solid transparent;
        border-radius: 14px;
        text-align: left;
        padding: 0 14px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton#NavButton:hover {{
        background: #F7F3FF;
        color: #5B2CA0;
        border: 1px solid #E7D8FF;
    }}

    QPushButton#NavButton:checked {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #6F02B5,
            stop:1 #8A35D8
        );
        color: white;
        border: 1px solid #6A16B8;
    }}

    #QuickTitle {{
        color: #202634;
        font-size: 15px;
        font-weight: 700;
    }}

    #QuickText {{
        color: #7C8798;
        font-size: 12px;
        font-weight: 500;
        line-height: 1.4;
    }}

    #ProfileCard {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #2B1039,
            stop:1 #5C1490
        );
        border-radius: 22px;
        border: 1px solid rgba(255,255,255,0.08);
    }}

    #ProfileName {{
        color: white;
        font-size: 16px;
        font-weight: 700;
    }}

    #ProfileMeta {{
        color: rgba(255,255,255,0.82);
        font-size: 12px;
        font-weight: 500;
    }}

    #MachineChip {{
        background: rgba(255,255,255,0.12);
        color: white;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        padding: 8px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    #ContentWrap {{
        background: #F5F7FB;
    }}

    #Topbar {{
        background: #FFFFFF;
        border: 1px solid #E9EDF5;
        border-radius: 22px;
    }}

    #TopbarTitle {{
        color: #1E2430;
        font-size: 24px;
        font-weight: 700;
    }}

    #TopbarSubtitle {{
        color: #7A8698;
        font-size: 12px;
        font-weight: 500;
    }}

    #MainStack {{
        background: transparent;
    }}

    #PageCard {{
        background: #FFFFFF;
        border: 1px solid #E9EDF5;
        border-radius: 24px;
    }}

    #SoftCard {{
        background: #FFFFFF;
        border: 1px solid #ECEFF5;
        border-radius: 20px;
    }}

    #GlassCard {{
        background: #FCFDFE;
        border: 1px solid #EAEFF6;
        border-radius: 20px;
    }}

    #AccentPanel {{
        background: #F8F5FF;
        border: 1px solid #E8DEFA;
        border-radius: 18px;
    }}

    #SectionEyebrow {{
        color: #8667C7;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2px;
    }}

    #SectionTitle {{
        color: #1E2430;
        font-size: 18px;
        font-weight: 700;
    }}

    #SectionText {{
        color: #778295;
        font-size: 12px;
        font-weight: 500;
    }}

    #FieldTitle {{
        color: #243043;
        font-size: 14px;
        font-weight: 700;
    }}

    #FieldText {{
        color: #7A8698;
        font-size: 12px;
        font-weight: 500;
    }}

    #InfoValue {{
        color: #202735;
        font-size: 14px;
        font-weight: 600;
    }}

    #MetricTitle {{
        color: #8A96A8;
        font-size: 11px;
        font-weight: 600;
    }}

    #MetricValue {{
        color: #1D2431;
        font-size: 17px;
        font-weight: 700;
    }}

    QLineEdit {{
        background: #FFFFFF;
        border: 1px solid #E5EAF2;
        border-radius: 16px;
        padding: 12px 14px;
        color: #243043;
        selection-background-color: #DCC6FB;
        font-size: 13px;
    }}

    QLineEdit:hover {{
        border: 1px solid #D8DFEA;
    }}

    QLineEdit:focus {{
        border: 1px solid #A35AF0;
        background: #FFFFFF;
    }}

    QTextEdit {{
        background: #FFFFFF;
        border: 1px solid #E5EAF2;
        border-radius: 16px;
        padding: 12px;
        color: #243043;
        font-size: 13px;
    }}

    QTextEdit:focus {{
        border: 1px solid #A35AF0;
    }}

    QPushButton {{
        min-height: 20px;
        border-radius: 14px;
        padding: 11px 18px;
        font-size: 13px;
        font-weight: 700;
    }}

    QPushButton#PrimaryButton {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #6F02B5,
            stop:0.55 #8B34D7,
            stop:1 #A55AF0
        );
        color: white;
        border: 1px solid #7318C2;
    }}

    QPushButton#PrimaryButton:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #6500A6,
            stop:0.55 #8028CE,
            stop:1 #9A50EA
        );
        border: 1px solid #6911B8;
    }}

    QPushButton#PrimaryButton:pressed {{
        background: #6811B1;
        border: 1px solid #6811B1;
    }}

    QPushButton#SecondaryButton {{
        background: #F7F8FC;
        color: #46546A;
        border: 1px solid #E3E8F1;
    }}

    QPushButton#SecondaryButton:hover {{
        background: #EEF2F8;
        border: 1px solid #D9E0EB;
    }}

    QPushButton#GhostButton {{
        background: #FFFFFF;
        color: #5B2CA0;
        border: 1px solid #E4D7FA;
    }}

    QPushButton#GhostButton:hover {{
        background: #FAF7FF;
        border: 1px solid #DCCAF8;
    }}

    QPushButton:disabled {{
        background: #EEF2F6;
        color: #9AA5B5;
        border: 1px solid #E7EBF1;
    }}

    QProgressBar {{
        background: #EEF2F7;
        border: 1px solid #E4EAF2;
        border-radius: 10px;
        min-height: 16px;
        text-align: center;
        color: #64748B;
        font-size: 11px;
    }}

    QProgressBar::chunk {{
        border-radius: 8px;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #C89CFF,
            stop:0.5 #9A49E5,
            stop:1 #6F02B5
        );
    }}

    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 4px 2px 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background: #D8DFEA;
        border-radius: 6px;
        min-height: 28px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #C9D2E1;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
        border: none;
    }}

    QMessageBox {{
        background: #F5F7FB;
    }}

    QMessageBox QLabel {{
        color: #243043;
        font-size: 13px;
    }}
    """