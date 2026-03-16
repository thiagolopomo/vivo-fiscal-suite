#!/usr/bin/env python
# -*- coding: utf-8 -*-

def build_app_qss(font_family: str = "Segoe UI") -> str:
    return f"""
    * {{
        font-family: "{font_family}", "Inter", "Segoe UI", sans-serif;
        outline: none;
    }}

    QWidget {{
        background: #F4F7FB;
        color: #243043;
        font-size: 11px;
    }}

    QMainWindow, QDialog {{
        background: #EEF2F7;
    }}

    QLabel {{
        background: transparent;
        border: none;
        padding: 0px;
        margin: 0px;
    }}

    QFrame {{
        border: none;
        background: transparent;
    }}

    #ShellRoot {{
        background: #EEF2F7;
    }}

    #ContentWrap {{
        background: #EEF2F7;
    }}

    #MainStack {{
        background: transparent;
    }}

    /* =========================
       SIDEBAR PREMIUM ESCURA
       ========================= */

    #Sidebar {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #1E1830,
            stop:1 #171324
        );
        border-right: 1px solid rgba(255,255,255,0.04);
    }}

    #BrandCard {{
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 18px;
    }}

    #BrandLogoWrap {{
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
}}

    #BrandAccentLine {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #8E35E9,
            stop:0.55 #B463FF,
            stop:1 #D7A5FF
        );
        border-radius: 1px;
        min-height: 2px;
        max-height: 2px;
    }}

    #BrandLogo {{
        background: transparent;
        border: none;
        padding-top: 2px;
        padding-bottom: 0px;
        margin: 0px;
    }}

    #BrandTitle {{
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
        letter-spacing: 0.2px;
    }}

    #BrandSubtitle {{
    color: #BEB7D2;
    font-size: 10px;
    font-weight: 500;
    }}

    #BrandChip {{
        background: rgba(255,255,255,0.08);
        color: #EDE5FF;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px;
        padding: 5px 10px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.6px;
    }}

    #SidebarSection {{
        color: #968FB0;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 2px;
    }}

    #SidebarPanel {{
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
    }}

    QPushButton#NavButton {{
        background: transparent;
        color: #ECE8F7;
        border: 1px solid transparent;
        border-radius: 12px;
        text-align: left;
        padding: 8px 12px;
        font-size: 12px;
        font-weight: 650;
        min-height: 16px;
    }}

    QPushButton#NavButton:hover {{
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.08);
        color: #FFFFFF;
    }}

    QPushButton#NavButton:checked {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #7C18CB,
            stop:1 #A651EA
        );
        color: white;
        border: 1px solid rgba(255,255,255,0.10);
    }}

    QPushButton#NavButton:disabled {{
        background: rgba(255,255,255,0.025);
        color: #7E7892;
        border: 1px solid rgba(255,255,255,0.04);
    }}

    #QuickTitle {{
        color: #FFFFFF;
        font-size: 12px;
        font-weight: 650;
    }}

    #QuickText {{
        color: #BBB5CE;
        font-size: 10px;
        font-weight: 500;
    }}

    #ProfileCard {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #4A1271,
            stop:1 #6A16A3
        );
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.08);
    }}

    #ProfileName {{
        color: white;
        font-size: 13px;
        font-weight: 700;
    }}

    #ProfileMeta {{
        color: rgba(255,255,255,0.84);
        font-size: 9px;
        font-weight: 500;
    }}

    #MachineChip {{
        background: rgba(255,255,255,0.10);
        color: rgba(255,255,255,0.92);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px;
        padding: 6px 8px;
        font-size: 9px;
        font-weight: 600;
    }}

    /* =========================
       TOPBAR / HEADER PREMIUM
       ========================= */

    #Topbar {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #FFFFFF,
            stop:1 #F7F3FF
        );
        border: 1px solid #E4DAF7;
        border-radius: 18px;
    }}

    #TopbarTitle {{
        color: #1D2230;
        font-size: 17px;
        font-weight: 750;
    }}

    #TopbarSubtitle {{
        color: #75839A;
        font-size: 11px;
        font-weight: 500;
    }}

    #TopbarBadge {{
        background: #F4EDFF;
        color: #7A4FD2;
        border: 1px solid #E2D4FA;
        border-radius: 10px;
        padding: 4px 9px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1.2px;
    }}

    /* =========================
       CARDS / CONTEÚDO BASE
       ========================= */

    #PageCard {{
        background: #FCFDFE;
        border: 1px solid #E4EAF3;
        border-radius: 20px;
    }}

    #SoftCard {{
        background: #FFFFFF;
        border: 1px solid #E7ECF4;
        border-radius: 16px;
    }}

    #GlassCard {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FBFCFE,
            stop:1 #F6F8FC
        );
        border: 1px solid #E5EAF2;
        border-radius: 16px;
    }}

    #AccentPanel {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #F7F3FF,
            stop:1 #F2EEFC
        );
        border: 1px solid #E4D8FA;
        border-radius: 14px;
    }}

    #TopBadge {{
        background: #F5EEFF;
        color: #7D58CC;
        border: 1px solid #E5D8FA;
        border-radius: 10px;
        padding: 4px 8px;
        font-size: 9px;
        font-weight: 700;
    }}

    #SectionEyebrow {{
        color: #7A5AF8;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        padding: 0px;
        background: transparent;
    }}

    #SectionTitle {{
        color: #182235;
        font-size: 20px;
        font-weight: 800;
        padding-bottom: 4px;
    }}

    #SectionText {{
        color: #76859C;
        font-size: 11px;
        font-weight: 500;
    }}

    #FieldTitle {{
        color: #1F293B;
        font-size: 13px;
        font-weight: 700;
    }}

    #FieldText {{
        color: #708097;
        font-size: 11px;
        font-weight: 500;
    }}

    #InfoValue {{
        color: #2E3A4D;
        font-size: 12px;
        font-weight: 650;
    }}

    #MetricTitle {{
    color: #7F8BA0;
    font-size: 10px;
    font-weight: 700;
}}

#MetricValue {{
    color: #182235;
    font-size: 11px;
    font-weight: 800;
    padding-top: 1px;
}}

    #AccessMainName {{
        color: #334155;
        font-size: 14px;
        font-weight: 650;
    }}

    #HashValue {{
        color: #7B8798;
        font-size: 11px;
        font-weight: 500;
    }}

    #AccessStatusValue {{
        color: #425166;
        font-size: 11px;
        font-weight: 600;
    }}

    #SectionDivider {{
        background: transparent;
        border: none;
        border-top: 1px solid #DCE4EF;
        min-height: 1px;
        max-height: 1px;
        margin-top: 2px;
        margin-bottom: 2px;
    }}

    /* =========================
       INPUTS / TEXTAREA
       ========================= */

    QLineEdit {{
        background: #FFFFFF;
        border: 1px solid #DCE4EF;
        border-radius: 12px;
        padding: 7px 10px;
        color: #243043;
        selection-background-color: #DCC6FB;
        font-size: 11px;
    }}

    QLineEdit:hover {{
        border: 1px solid #CDD8E6;
    }}

    QLineEdit:focus {{
        border: 1px solid #A35AF0;
        background: #FFFFFF;
    }}

    QLineEdit#PathInput {{
        background: #FFFFFF;
        border: 1px solid #DED7EE;
        border-radius: 12px;
        padding: 8px 10px;
        color: #233044;
    }}

    QLineEdit#PathInput:hover {{
        border: 1px solid #CBBEE8;
    }}

    QLineEdit#PathInput:focus {{
        border: 1px solid #9D5AF2;
        background: #FFFFFF;
    }}

    QTextEdit {{
        background: #FFFFFF;
        border: 1px solid #DCE4EF;
        border-radius: 13px;
        padding: 8px;
        color: #243043;
        font-size: 11px;
    }}

    QTextEdit:hover {{
        border: 1px solid #CFC3EA;
    }}

    QTextEdit:focus {{
        border: 1px solid #A35AF0;
    }}

    /* =========================
       BOTÕES
       ========================= */

    QPushButton {{
        border-radius: 14px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 700;
        min-height: 32px;
        max-height: 16777215px;
    }}

    QPushButton#PrimaryButton {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #6D09B8,
            stop:0.52 #8E33DA,
            stop:1 #B564F2
        );
        color: white;
        border: 1px solid #7A20C8;
        border-radius: 14px;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: 700;
    }}

    QPushButton#PrimaryButton:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #5E00A8,
            stop:0.52 #8429D6,
            stop:1 #B35FF0
        );
        border: 1px solid #6E13C2;
    }}

    QPushButton#SecondaryButton {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #F8F4FF,
            stop:1 #F2EBFD
        );
        color: #552A9B;
        border: 1px solid #DCCCF8;
        border-radius: 14px;
        padding: 10px 18px;
        font-size: 12px;
        font-weight: 700;
    }}

    QPushButton#SecondaryButton:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #F1E5FF,
            stop:1 #E9D6FF
        );
        border: 1px solid #C9A7F5;
        color: #411C82;
    }}

    QPushButton#GhostButton {{
        background: #FFFFFF;
        color: #6B2FB8;
        border: 1px solid #DFCFFA;
        border-radius: 14px;
        padding: 10px 18px;
        font-size: 12px;
        font-weight: 700;
    }}

    QPushButton#GhostButton:hover {{
        background: #F9F3FF;
        border: 1px solid #CFAEF7;
        color: #4B1F95;
    }}

    QPushButton:disabled {{
        background: #EEF2F6;
        color: #9AA5B5;
        border: 1px solid #E7EBF1;
    }}

    /* =========================
       PROGRESS
       ========================= */

    QProgressBar {{
        background: #EEF2F7;
        border: 1px solid #E0E7F0;
        border-radius: 8px;
        min-height: 10px;
        text-align: center;
        color: #64748B;
        font-size: 9px;
    }}

    QProgressBar::chunk {{
        border-radius: 6px;
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

    /* =========================
       SCROLL
       ========================= */

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 2px 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background: #D3DCE8;
        border-radius: 5px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #C3CEDC;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
        border: none;
    }}

    QMessageBox {{
        background: #EEF2F7;
    }}

    QMessageBox QLabel {{
        color: #243043;
        font-size: 11px;
    }}

    /* =========================
       DASHBOARD
       ========================= */

    #WorkspaceHero {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FBF7FF,
            stop:0.25 #F5EEFF,
            stop:0.58 #F3F7FC,
            stop:1 #EDF4FB
        );
        border: 1px solid #E2E8F2;
        border-radius: 22px;
    }}

    #WorkspaceBand {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #F8FAFD,
            stop:1 #F2F6FC
        );
        border: 1px solid #E4EAF3;
        border-radius: 18px;
    }}

    #WorkspaceModuleCard {{
        background: #FFFFFF;
        border: 1px solid #E5EAF3;
        border-radius: 20px;
    }}

    #WorkspaceModuleCard[hover="true"] {{
        border: 1px solid #E3DDF3;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #FAF8FF
        );
    }}

    #WorkspaceModuleCard[hover="true"] #ModuleIcon {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #6E0FC1,
            stop:1 #B05DF2
        );
    }}

    #ModuleIcon {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #7C18CB,
            stop:1 #A651EA
        );
        border: none;
        border-radius: 14px;
    }}

    #ModuleIconText {{
        color: #FFFFFF;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.6px;
    }}

    #HeroTitle {{
        color: #17263A;
        font-size: 28px;
        font-weight: 800;
    }}

    #HeroText {{
        color: #667892;
        font-size: 13px;
        font-weight: 500;
    }}

    #StatCard {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #F8F4FF
        );
        border: 1px solid #E4DDF4;
        border-radius: 16px;
    }}

    #StatCard[hover="true"] {{
        border: 1px solid #E3DDF3;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #FAF8FF
        );
    }}

    #StatIcon {{
        color: #7A3FE0;
        font-size: 15px;
        font-weight: 700;
    }}

    #StatLabel {{
        color: #7A889D;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    #StatValue {{
    color: #17263A;
    font-size: 18px;
    font-weight: 800;
    padding-top: 1px;
}}

    #StatCard[hover="true"] #StatIcon {{
        color: #5F35AE;
        font-size: 16px;
        font-weight: 800;
    }}

    #StatCard[hover="true"] #StatLabel {{
        color: #6F6592;
    }}

    #StatCard[hover="true"] #StatValue {{
        color: #1D2330;
    }}

    #StatAccentLine {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #8A35EA,
            stop:0.55 #A855F7,
            stop:1 #C27EFF
        );
        border-radius: 1px;
        min-height: 2px;
        max-height: 2px;
    }}

    /* =========================
       PÁGINAS INTERNAS PREMIUM
       ========================= */

    #PremiumPathCard {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #FBF7FF
        );
        border: 1px solid #E5EAF3;
        border-radius: 20px;
    }}

    #PremiumPathCard[hover="true"] {{
        border: 1px solid #E5EAF3;
        background: #FFFFFF;
    }}

    #PremiumMetricBox {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #FBF7FF
        );
        border: 1px solid #E6DDF6;
        border-radius: 14px;
    }}

    #PremiumMetricBox[hover="true"] {{
        border: 1px solid #E3DDF3;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #FAF8FF
        );
    }}

    #PremiumExecCard,
    #PremiumLogCard,
    #PremiumSummaryCard {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #F9F6FF
        );
        border: 1px solid #E5EAF3;
        border-radius: 20px;
    }}

    #PremiumExecCard[hover="true"],
    #PremiumLogCard[hover="true"],
    #PremiumSummaryCard[hover="true"] {{
        border: 1px solid #E3DDF3;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #FFFFFF,
            stop:1 #FAF8FF
        );
    }}

    #CardAccentLine {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #8E35E9,
            stop:0.55 #AC5BFA,
            stop:1 #C987FF
        );
        border-radius: 1px;
        min-height: 2px;
        max-height: 2px;
    }}

    #MetricAccentLine {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #8A35EA,
            stop:1 #C27EFF
        );
        border-radius: 1px;
        min-height: 1px;
        max-height: 1px;
    }}

    #PremiumExecCard[hover="true"] #InfoValue,
    #PremiumSummaryCard[hover="true"] #MetricValue,
    #PremiumMetricBox[hover="true"] #MetricValue {{
        color: #1F2530;
    }}

    #PremiumExecCard[hover="true"] #FieldText,
    #PremiumSummaryCard[hover="true"] #MetricTitle,
    #PremiumMetricBox[hover="true"] #MetricTitle {{
        color: #717B8E;
    }}
    """