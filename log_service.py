#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Servico de log e notificacoes - VIVO Fiscal Suite
Registra uso no Supabase e envia emails via Resend.
"""

import json
import time
import getpass
import socket
import threading
import requests

SUPABASE_URL = "https://jhkqfacpobwnirioskii.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Impoa3FmYWNwb2J3bmlyaW9za2lpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyNzU2MDEsImV4cCI6MjA4ODg1MTYwMX0.lnRnP4ESzQc54LxX-6Y-qRZsfPEv1SGg3ozd2R0N4hY"

RESEND_KEY = "re_cw1BHBPG_BhTrRb5n8mTkvQ4qkppPPdE1"
EMAIL_DESTINO = "thiagolopomo67@gmail.com"
APP_TITLE = "VIVO Fiscal Suite"
APP_VERSION = "1.0.0"

# Machine ID global - setado pelo main.py apos login
_MACHINE_ID = ""


def set_machine_id(mid: str):
    global _MACHINE_ID
    _MACHINE_ID = mid


def get_machine_id() -> str:
    return _MACHINE_ID


def log_auto(acao, detalhes=None):
    """Log async usando machine_id global (uso nas pages/workers sem precisar passar machine_id)."""
    mid = _MACHINE_ID
    if mid:
        log_async(mid, acao, detalhes)


def _supabase_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }


def registrar_log(machine_id, acao="app_aberto", detalhes=None):
    """Registra log no Supabase e envia email."""
    usuario = getpass.getuser()
    maquina = socket.gethostname()

    # Supabase
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/registrar_log_uso"
        payload = {
            "p_app": APP_TITLE,
            "p_usuario": usuario,
            "p_maquina": maquina,
            "p_machine_id": machine_id,
            "p_acao": acao,
            "p_detalhes": json.dumps(detalhes or {}),
        }
        requests.post(url, headers=_supabase_headers(),
                       data=json.dumps(payload), timeout=10)
    except Exception:
        pass

    # Email
    try:
        _enviar_email_log(usuario, maquina, machine_id, acao, detalhes)
    except Exception:
        pass


def log_async(machine_id, acao, detalhes=None):
    """Registra log em background (nao bloqueia a UI)."""
    t = threading.Thread(
        target=registrar_log,
        args=(machine_id, acao, detalhes),
        daemon=True
    )
    t.start()


# ══════════════════════════════════════
# ACOES CONHECIDAS
# ══════════════════════════════════════

ACAO_MAP = {
    # Acesso
    "app_aberto": "abriu o aplicativo",
    "acesso_negado": "teve acesso NEGADO",
    "acesso_negado_polling": "teve acesso NEGADO (polling)",
    "solicitacao_enviada": "solicitou acesso",

    # Navegacao
    "nav_dashboard": "acessou Dashboard",
    "nav_p9": "acessou modulo Validacao P9",
    "nav_consolidador": "acessou modulo Consolidador Fiscal",
    "nav_ztmm": "acessou modulo ZTMM x Livro",

    # P9
    "p9_processamento_iniciado": "iniciou processamento P9",
    "p9_processamento_concluido": "concluiu processamento P9",
    "p9_processamento_erro": "erro no processamento P9",

    # Conferencia
    "conferencia_iniciada": "iniciou conferencia",
    "conferencia_concluida": "concluiu conferencia",
    "conferencia_erro": "erro na conferencia",

    # Consolidador
    "consolidador_processamento_iniciado": "iniciou consolidacao fiscal",
    "consolidador_processamento_concluido": "concluiu consolidacao fiscal",
    "consolidador_processamento_erro": "erro na consolidacao fiscal",
    "consolidador_exportacao_iniciada": "iniciou exportacao fiscal",
    "consolidador_exportacao_concluida": "concluiu exportacao fiscal",
    "consolidador_exportacao_erro": "erro na exportacao fiscal",

    # ZTMM
    "ztmm_consolidacao_iniciada": "iniciou consolidacao ZTMM",
    "ztmm_consolidacao_concluida": "concluiu consolidacao ZTMM",
    "ztmm_consolidacao_erro": "erro na consolidacao ZTMM",
    "ztmm_exportacao_iniciada": "iniciou exportacao ZTMM",
    "ztmm_exportacao_concluida": "concluiu exportacao ZTMM",
    "ztmm_exportacao_erro": "erro na exportacao ZTMM",
    "ztmm_analise_iniciada": "iniciou analise ZTMM",
    "ztmm_analise_concluida": "concluiu analise ZTMM",
    "ztmm_analise_erro": "erro na analise ZTMM",
}


def _enviar_email_log(usuario, maquina, machine_id, acao, detalhes):
    agora = time.strftime("%d/%m/%Y %H:%M:%S")
    acao_desc = ACAO_MAP.get(acao, acao)

    # Detalhe formatado
    modo = ""
    if detalhes and isinstance(detalhes, dict):
        parts = []
        m = detalhes.get("modo", "")
        if m == "cache_local":
            parts.append("Acesso previamente aprovado")
        elif m == "aprovacao_inicial":
            parts.append("Primeira aprovacao")
        elif m == "aprovacao_polling":
            parts.append("Aprovado em tempo real")
        for k, v in detalhes.items():
            if k == "modo":
                continue
            parts.append(f"{k}: {v}")
        modo = " | ".join(parts)

    is_error = "negado" in acao or "erro" in acao
    cor = "#DC2626" if is_error else "#660099"
    badge_bg = "#FEE2E2" if is_error else "#F3E8FF"
    badge_color = "#DC2626" if is_error else "#7C3AED"

    # Categoria
    if "p9" in acao:
        modulo = "Validacao P9"
    elif "conferencia" in acao:
        modulo = "Conferencia"
    elif "consolidador" in acao or "consolidacao" in acao.replace("ztmm_", ""):
        modulo = "Consolidador Fiscal"
    elif "ztmm" in acao:
        modulo = "ZTMM x Livro"
    elif "nav_" in acao:
        modulo = "Navegacao"
    else:
        modulo = "Sistema"

    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px 0;">
      <div style="border-left:4px solid {cor};padding-left:16px;margin-bottom:20px;">
        <h2 style="color:#1B1464;margin:0 0 2px 0;font-size:17px;">VIVO Fiscal Suite</h2>
        <p style="color:#6B7E8D;margin:0;font-size:12px;">Log de uso em tempo real</p>
      </div>

      <div style="margin-bottom:16px;">
        <span style="background:{badge_bg};color:{badge_color};font-size:11px;font-weight:700;
               padding:4px 12px;border-radius:12px;letter-spacing:0.5px;">{modulo.upper()}</span>
      </div>

      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr>
          <td style="padding:10px 12px;color:#6B7E8D;background:#F8FAFB;width:120px;border-bottom:1px solid #EEF2F6;">Usuario</td>
          <td style="padding:10px 12px;color:#1E293B;font-weight:600;background:#F8FAFB;border-bottom:1px solid #EEF2F6;">{usuario}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;color:#6B7E8D;border-bottom:1px solid #EEF2F6;">Maquina</td>
          <td style="padding:10px 12px;color:#1E293B;border-bottom:1px solid #EEF2F6;">{maquina}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;color:#6B7E8D;background:#F8FAFB;border-bottom:1px solid #EEF2F6;">Acao</td>
          <td style="padding:10px 12px;color:{cor};font-weight:700;background:#F8FAFB;border-bottom:1px solid #EEF2F6;">{acao_desc}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;color:#6B7E8D;border-bottom:1px solid #EEF2F6;">Data/Hora</td>
          <td style="padding:10px 12px;color:#1E293B;border-bottom:1px solid #EEF2F6;">{agora}</td>
        </tr>
        {"<tr><td style='padding:10px 12px;color:#6B7E8D;background:#F8FAFB;border-bottom:1px solid #EEF2F6;'>Detalhe</td><td style='padding:10px 12px;color:#1E293B;background:#F8FAFB;border-bottom:1px solid #EEF2F6;'>" + modo + "</td></tr>" if modo else ""}
      </table>

      <p style="color:#B0BEC5;font-size:10px;margin-top:20px;">
        Machine ID: {machine_id[:24]}... | {APP_TITLE} v{APP_VERSION}
      </p>
    </div>
    """

    requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": "onboarding@resend.dev",
            "to": [EMAIL_DESTINO],
            "subject": f"[VIVO Suite] {usuario} {acao_desc}",
            "html": html,
        },
        timeout=10,
    )
