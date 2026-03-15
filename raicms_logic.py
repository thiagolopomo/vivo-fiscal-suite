#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import unicodedata

import pdfplumber
import pandas as pd

from openpyxl import load_workbook
from openpyxl.styles import NamedStyle


# =========================================================
# CONFIG GERAL
# =========================================================
ARQ_DIVISAO = "Tabela_Divisao.csv"

TITULO_ALVO = "LIVRO REGISTRO DE APURAÇÃO DO ICMS - RAICMS - MODELO P"
TITULO_RESUMO = "RESUMO DA APURAÇÃO DO IMPOSTO".upper()


# =========================================================
# RECURSOS
# =========================================================
def caminho_recurso(nome_arquivo):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, nome_arquivo)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nome_arquivo)


# =========================================================
# PROCESSAMENTO RAICMS
# =========================================================
def normalizar_espacos(txt: str) -> str:
    return re.sub(r"\s+", " ", txt or "").strip()


def normalizar_texto(txt: str) -> str:
    txt = txt or ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = normalizar_espacos(txt).upper()
    return txt


def converter_numero_br(valor):
    if valor is None:
        return None

    valor = str(valor).strip()
    if not valor:
        return None

    valor = valor.replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except Exception:
        return None


def formatar_periodo(periodo):
    if not periodo:
        return ""
    return str(periodo).replace("/", ".")


def extrair_cabecalho_pagina(texto):
    firma = ""
    ie = ""
    cnpj = ""
    periodo = ""
    folha = ""

    m_firma = re.search(r"FIRMA\s*:\s*(.+)", texto)
    if m_firma:
        firma = normalizar_espacos(m_firma.group(1))

    m_ie = re.search(r"INSCR\.\s*EST\.\s*:\s*([^\n]+?)\s+CNPJ\s*:\s*([0-9\.\-\/]+)", texto)
    if m_ie:
        ie = normalizar_espacos(m_ie.group(1))
        cnpj = normalizar_espacos(m_ie.group(2))
    else:
        m_ie2 = re.search(r"INSCR\.\s*EST\.\s*:\s*(.+)", texto)
        if m_ie2:
            ie = normalizar_espacos(m_ie2.group(1))

        m_cnpj = re.search(r"CNPJ\s*:\s*([0-9\.\-\/]+)", texto)
        if m_cnpj:
            cnpj = normalizar_espacos(m_cnpj.group(1))

    m_periodo = re.search(r"Per[ií]odo\s*:\s*(\d{2}/\d{4})", texto, flags=re.IGNORECASE)
    if m_periodo:
        periodo = m_periodo.group(1)

    m_folha = re.search(r"FOLHA\s*:\s*([^\n]+)", texto)
    if m_folha:
        folha = normalizar_espacos(m_folha.group(1))

    return {
        "Firma": firma,
        "IE": ie,
        "CNPJ": cnpj,
        "Período": periodo,
        "Folha": folha
    }


def extrair_filial_do_arquivo(nome_arquivo):
    nome = os.path.splitext(os.path.basename(nome_arquivo))[0]
    nome_up = nome.upper()

    if "PAY" in nome_up:
        return "PAY"

    m = re.search(r"FL\s*(\d{4})", nome_up)
    if m:
        return m.group(1)

    tokens = re.split(r"[_\-\s]+", nome_up)
    for tok in tokens:
        if re.fullmatch(r"\d{4}", tok):
            return tok

    return ""


def carregar_mapa_divisao():
    arq = caminho_recurso(ARQ_DIVISAO)

    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": None, "engine": "python", "encoding": "latin1"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
    ]

    ultimo_erro = None
    df = None

    for cfg in tentativas:
        try:
            df = pd.read_csv(arq, **cfg)
            break
        except Exception as e:
            ultimo_erro = e

    if df is None:
        raise RuntimeError(f"Erro ao ler Tabela_Divisao.csv: {ultimo_erro}")

    cols_norm = {normalizar_texto(c): c for c in df.columns}

    col_filial = cols_norm.get(normalizar_texto("Local de Negócios"))
    col_divisao = cols_norm.get(normalizar_texto("Divisão"))

    if not col_filial or not col_divisao:
        raise RuntimeError(
            "Não encontrei as colunas 'Local de Negócios' e/ou 'Divisão' no Tabela_Divisao.csv"
        )

    mapa = {}
    for _, row in df[[col_filial, col_divisao]].dropna(how="all").iterrows():
        filial = normalizar_espacos(str(row[col_filial])) if pd.notna(row[col_filial]) else ""
        divisao = normalizar_espacos(str(row[col_divisao])) if pd.notna(row[col_divisao]) else ""

        filial_limpa = re.sub(r"\.0$", "", filial.strip())
        if filial_limpa:
            mapa[filial_limpa.upper()] = divisao

    return mapa


def aplicar_sinal_entrada(valor, tipo):
    if valor is None or pd.isna(valor):
        return valor
    if (tipo or "").strip().upper() == "ENTRADA":
        return -abs(float(valor))
    return abs(float(valor))


def definir_status_por_descricao(descricao):
    desc_n = normalizar_texto(descricao)
    if desc_n == "SALDO CREDOR A TRANSPORTAR" or desc_n == "IMPOSTO A RECOLHER":
        return "ICMS a Recolher ou Recuperar"
    return "Entrada / Saída"


# =========================================================
# CFOP
# =========================================================
def eh_linha_numerica_tabela(linha):
    linha = linha.strip()

    if not re.match(r"^\d{4}\b", linha):
        return False

    nums = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", linha)
    return len(nums) >= 3


def parse_linha_tabela(linha):
    linha = normalizar_espacos(linha)

    m_cfop = re.match(r"^(\d{4})\b", linha)
    if not m_cfop:
        return None

    cfop = m_cfop.group(1)
    nums = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", linha)

    if len(nums) < 5:
        return None

    ultimos_5 = nums[-5:]

    return {
        "CFOP": cfop,
        "Valores Contábeis": converter_numero_br(ultimos_5[0]),
        "Base de Cálculo": converter_numero_br(ultimos_5[1]),
        "Imposto Creditado": converter_numero_br(ultimos_5[2]),
        "Isentas ou não Trib.": converter_numero_br(ultimos_5[3]),
        "Outras": converter_numero_br(ultimos_5[4]),
    }


def linha_indica_secao_cfop(linha):
    l = normalizar_texto(linha)

    if l == "ENTRADAS":
        return "Entrada"

    if "SAIDAS" in l:
        return "Saída"

    return None


def deve_ignorar_linha_cfop(linha):
    l = normalizar_espacos(linha).upper()

    ignorar_se_conter = [
        "LIVRO REGISTRO DE APURAÇÃO DO ICMS",
        "REGISTRO DE APURAÇÃO DO ICMS",
        "RESUMO DA APURAÇÃO DO IMPOSTO",
        "ICMS - VALORES FISCAIS",
        "OPERAÇÕES COM CRÉDITO DO IMPOSTO",
        "OPERACOES COM CREDITO DO IMPOSTO",
        "OPERAÇÕES SEM CRÉDITO DO IMPOSTO",
        "OPERACOES SEM CREDITO DO IMPOSTO",
        "CODIFICAÇÃO",
        "CONTÁBIL",
        "CONTABIL",
        "FISCAL",
        "VALORES CONTÁBEIS",
        "VALORES CONTABEIS",
        "BASE DE CÁLCULO",
        "BASE DE CALCULO",
        "IMPOSTO CREDITADO",
        "ISENTAS OU NÃO TRIB.",
        "ISENTAS OU NAO TRIB.",
        "OUTRAS",
        "SUBTOTAIS",
        "TOTAIS",
        "1.00 DO ESTADO",
        "2.00 DE OUTROS ESTADOS",
        "3.00 DO EXTERIOR",
        "FIRMA :",
        "INSCR. EST. :",
        "CNPJ :",
        "FOLHA :",
        "PERÍODO :",
        "PERIODO :"
    ]

    return any(x in l for x in ignorar_se_conter)


def processar_pdf_cfop(caminho_pdf, mapa_divisao):
    registros = []
    arquivo_pdf = os.path.basename(caminho_pdf)
    filial = extrair_filial_do_arquivo(arquivo_pdf)
    divisao = mapa_divisao.get((filial or "").upper(), "")

    with pdfplumber.open(caminho_pdf) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""

            if TITULO_ALVO not in texto:
                continue

            if TITULO_RESUMO in texto.upper():
                continue

            meta = extrair_cabecalho_pagina(texto)

            linhas = texto.splitlines()
            tipo_atual = None

            for linha in linhas:
                linha_limpa = linha.strip()

                if not linha_limpa:
                    continue

                novo_tipo = linha_indica_secao_cfop(linha_limpa)
                if novo_tipo:
                    tipo_atual = novo_tipo
                    continue

                if deve_ignorar_linha_cfop(linha_limpa):
                    continue

                if eh_linha_numerica_tabela(linha_limpa):
                    dados_linha = parse_linha_tabela(linha_limpa)
                    if dados_linha:
                        dados_linha["Imposto Creditado"] = aplicar_sinal_entrada(
                            dados_linha["Imposto Creditado"], tipo_atual
                        )

                        registros.append({
                            "Arquivo PDF": arquivo_pdf,
                            "Filial": filial,
                            "Divisão": divisao,
                            "Página": num_pagina,
                            "Firma": meta["Firma"],
                            "IE": meta["IE"],
                            "CNPJ": meta["CNPJ"],
                            "Período": meta["Período"],
                            "Tipo": tipo_atual,
                            "Status": "Entrada / Saída",
                            **dados_linha
                        })

    return registros


# =========================================================
# RESUMO APURAÇÃO
# =========================================================
def linha_indica_secao_resumo(linha):
    l = normalizar_texto(linha)

    if "DEBITO DO IMPOSTO" in l:
        return "Débito do Imposto"
    if "CREDITO DO IMPOSTO" in l:
        return "Crédito do Imposto"
    if "APURACAO DO SALDO" in l:
        return "Apuração do Saldo"

    return None


def deve_ignorar_linha_resumo(linha):
    l = normalizar_texto(linha)

    ignorar = [
        "LIVRO REGISTRO DE APURACAO DO ICMS",
        "RAICMS - MODELO P",
        "RESUMO DA APURACAO DO IMPOSTO",
        "VALORES",
        "COLUNA AUXILIAR",
        "SOMAS",
        "FIRMA :",
        "INSCR. EST. :",
        "CNPJ :",
        "FOLHA :",
        "PERIODO :",
        "INFORMACOES COMPLEMENTARES",
        "GUIAS DE RECOLHIMENTO",
        "GUIA DE INFORMACAO",
        "OBSERVACOES",
        "DATA DA ENTREGA",
        "LOCAL DA ENTREGA",
        "ORGAO ARRECADADOR",
        "BANCO :",
        "AGENCIA :"
    ]

    return any(x in l for x in ignorar)


def parse_linha_resumo(linha):
    linha_original = linha.rstrip()
    linha = linha_original.strip()

    if not linha:
        return None

    numero = ""
    descricao = ""

    m_fim_2 = re.search(
        r"\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
        linha
    )
    m_fim_1 = re.search(
        r"\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
        linha
    )

    col_aux = None
    somas = None
    linha_sem_valores = linha

    if m_fim_2:
        col_aux = converter_numero_br(m_fim_2.group(1))
        somas = converter_numero_br(m_fim_2.group(2))
        linha_sem_valores = linha[:m_fim_2.start()].rstrip()
    elif m_fim_1:
        valor_final = converter_numero_br(m_fim_1.group(1))
        linha_sem_valores = linha[:m_fim_1.start()].rstrip()
    else:
        valor_final = None

    m_num = re.match(r"^(\d{3})\s*-\s*(.+?)\s*$", linha_sem_valores)
    if m_num:
        numero = m_num.group(1).strip()
        descricao = m_num.group(2).strip()
        if m_fim_1 and not m_fim_2:
            somas = valor_final
    else:
        m_sem_num = re.match(r"^-\s*(.+?)\s*$", linha_sem_valores)
        if m_sem_num:
            numero = ""
            descricao = m_sem_num.group(1).strip()
            if m_fim_1 and not m_fim_2:
                col_aux = valor_final
        else:
            return None

    return {
        "Número": numero,
        "Descrição": descricao,
        "Coluna Auxiliar": col_aux,
        "Somas": somas
    }


def definir_tipo_resumo(secao, descricao):
    secao_n = normalizar_texto(secao)
    desc_n = normalizar_texto(descricao)

    if "CREDITO" in secao_n:
        return "Entrada"

    if "DEBITO" in secao_n:
        return "Saída"

    if "APURACAO" in secao_n:
        if "DEDUCAO" in desc_n or "DEDUCOES" in desc_n:
            return "Entrada"
        if "IMPOSTO A RECOLHER" in desc_n:
            return "Entrada"
        if "SALDO CREDOR A TRANSPORTAR" in desc_n:
            return "Saída"
        if "SALDO DEVEDOR" in desc_n:
            return "Saída"

    return ""


def processar_pdf_resumo(caminho_pdf, mapa_divisao):
    registros = []
    arquivo_pdf = os.path.basename(caminho_pdf)
    filial = extrair_filial_do_arquivo(arquivo_pdf)
    divisao = mapa_divisao.get((filial or "").upper(), "")

    with pdfplumber.open(caminho_pdf) as pdf:
        seq = 0

        for num_pagina, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""

            if TITULO_ALVO not in texto:
                continue

            if TITULO_RESUMO not in texto.upper():
                continue

            meta = extrair_cabecalho_pagina(texto)

            linhas = texto.splitlines()
            secao_atual = None

            for linha in linhas:
                linha_limpa = linha.strip()

                if not linha_limpa:
                    continue

                nova_secao = linha_indica_secao_resumo(linha_limpa)
                if nova_secao:
                    secao_atual = nova_secao
                    continue

                if deve_ignorar_linha_resumo(linha_limpa):
                    continue

                dados = parse_linha_resumo(linha_limpa)
                if dados:
                    seq += 1
                    tipo = definir_tipo_resumo(secao_atual, dados["Descrição"])
                    dados["Somas"] = aplicar_sinal_entrada(dados["Somas"], tipo)
                    status = definir_status_por_descricao(dados["Descrição"])

                    registros.append({
                        "_seq": seq,
                        "Arquivo PDF": arquivo_pdf,
                        "Filial": filial,
                        "Divisão": divisao,
                        "Página": num_pagina,
                        "Firma": meta["Firma"],
                        "IE": meta["IE"],
                        "CNPJ": meta["CNPJ"],
                        "Período": meta["Período"],
                        "Seção": secao_atual,
                        "Tipo": tipo,
                        "Status": status,
                        **dados
                    })

    return registros


# =========================================================
# CONFERÊNCIA
# =========================================================
def montar_conferencia(df_cfop, df_resumo):
    partes = []

    if not df_cfop.empty:
        tmp_cfop = df_cfop[["Divisão", "Filial", "Status", "Imposto Creditado"]].copy()
        tmp_cfop = tmp_cfop.rename(columns={"Imposto Creditado": "Montante"})
        partes.append(tmp_cfop)

    if not df_resumo.empty:
        descricoes_desconsiderar = {
            "ENTRADAS",
            "SAIDAS",
            "SUB TOTAL",
            "SALDO DEVEDOR",
            "TOTAL"
        }

        tmp_resumo = df_resumo.copy()
        tmp_resumo["_DESC_NORM"] = tmp_resumo["Descrição"].apply(normalizar_texto)
        tmp_resumo = tmp_resumo[~tmp_resumo["_DESC_NORM"].isin(descricoes_desconsiderar)]

        tmp_resumo = tmp_resumo[["Divisão", "Filial", "Status", "Somas"]].copy()
        tmp_resumo = tmp_resumo.rename(columns={"Somas": "Montante"})
        partes.append(tmp_resumo)

    if not partes:
        return pd.DataFrame(columns=[
            "Divisão", "Filial", "Entrada / Saída",
            "ICMS a Recolher ou Recuperar", "Soma Total"
        ])

    base = pd.concat(partes, ignore_index=True)
    base["Montante"] = pd.to_numeric(base["Montante"], errors="coerce").fillna(0)

    conf = (
        base.groupby(["Divisão", "Filial", "Status"], dropna=False, as_index=False)["Montante"]
        .sum()
        .pivot(index=["Divisão", "Filial"], columns="Status", values="Montante")
        .fillna(0)
        .reset_index()
    )

    conf.columns.name = None

    for col in ["Entrada / Saída", "ICMS a Recolher ou Recuperar"]:
        if col not in conf.columns:
            conf[col] = 0.0

    conf["Soma Total"] = (
        pd.to_numeric(conf["Entrada / Saída"], errors="coerce").fillna(0)
        + pd.to_numeric(conf["ICMS a Recolher ou Recuperar"], errors="coerce").fillna(0)
    )

    conf = conf[[
        "Divisão",
        "Filial",
        "Entrada / Saída",
        "ICMS a Recolher ou Recuperar",
        "Soma Total"
    ]]
    return conf


# =========================================================
# EXCEL
# =========================================================
def aplicar_formatacao_excel(caminho_arquivo):
    wb = load_workbook(caminho_arquivo)

    try:
        moeda_style = NamedStyle(name="moeda_style_raicms", number_format='R$ #,##0.00')
        wb.add_named_style(moeda_style)
    except Exception:
        pass

    abas_colunas_monetarias = {
        "Consolidado": [
            "Valores Contábeis",
            "Base de Cálculo",
            "Imposto Creditado",
            "Isentas ou não Trib.",
            "Outras"
        ],
        "Resumo_Apuracao": [
            "Coluna Auxiliar",
            "Somas"
        ],
        "Conferência": [
            "Entrada / Saída",
            "ICMS a Recolher ou Recuperar",
            "Soma Total"
        ]
    }

    for nome_aba, colunas_monetarias in abas_colunas_monetarias.items():
        if nome_aba not in wb.sheetnames:
            continue

        ws = wb[nome_aba]
        headers = {ws.cell(row=1, column=col).value: col for col in range(1, ws.max_column + 1)}

        for nome_col in colunas_monetarias:
            col_idx = headers.get(nome_col)
            if not col_idx:
                continue

            for row in range(2, ws.max_row + 1):
                cell = ws.cell(row=row, column=col_idx)
                if isinstance(cell.value, (int, float)):
                    cell.number_format = 'R$ #,##0.00'

    wb.save(caminho_arquivo)


# =========================================================
# MOTOR DE PROCESSAMENTO
# =========================================================
def processar_raicms(pasta_pdfs, pasta_destino, progress_callback=None):
    t0 = time.time()

    mapa_divisao = carregar_mapa_divisao()

    dados_cfop = []
    dados_resumo = []

    arquivos_pdf = []
    for raiz, _, files in os.walk(pasta_pdfs):
        for f in files:
            if f.lower().endswith(".pdf"):
                arquivos_pdf.append(os.path.join(raiz, f))

    arquivos_pdf = sorted(arquivos_pdf)

    if not arquivos_pdf:
        raise FileNotFoundError("Nenhum PDF encontrado na pasta selecionada.")

    total = len(arquivos_pdf)

    for i, caminho_pdf in enumerate(arquivos_pdf, start=1):
        if progress_callback:
            progress_callback("processando_pdf", i, total, os.path.basename(caminho_pdf))

        dados_cfop.extend(processar_pdf_cfop(caminho_pdf, mapa_divisao))
        dados_resumo.extend(processar_pdf_resumo(caminho_pdf, mapa_divisao))

    df_cfop = pd.DataFrame(dados_cfop) if dados_cfop else pd.DataFrame(columns=[
        "Arquivo PDF", "Filial", "Divisão", "Página", "Firma", "IE", "CNPJ", "Período", "Tipo", "Status",
        "CFOP", "Valores Contábeis", "Base de Cálculo", "Imposto Creditado",
        "Isentas ou não Trib.", "Outras"
    ])

    df_resumo = pd.DataFrame(dados_resumo) if dados_resumo else pd.DataFrame(columns=[
        "Arquivo PDF", "Filial", "Divisão", "Página", "Firma", "IE", "CNPJ", "Período",
        "Seção", "Tipo", "Status", "Número", "Descrição", "Coluna Auxiliar", "Somas"
    ])

    if not df_cfop.empty:
        cols_ordem_cfop = [
            "Arquivo PDF", "Filial", "Divisão", "Página", "Firma", "IE", "CNPJ", "Período", "Tipo", "Status",
            "CFOP", "Valores Contábeis", "Base de Cálculo", "Imposto Creditado",
            "Isentas ou não Trib.", "Outras"
        ]
        df_cfop = df_cfop[cols_ordem_cfop]

    if not df_resumo.empty:
        df_resumo = df_resumo.sort_values(by=["Arquivo PDF", "_seq"], kind="stable")
        cols_ordem_resumo = [
            "Arquivo PDF", "Filial", "Divisão", "Página", "Firma", "IE", "CNPJ",
            "Período", "Seção", "Tipo", "Status", "Número", "Descrição", "Coluna Auxiliar", "Somas"
        ]
        df_resumo = df_resumo[cols_ordem_resumo]

    df_conferencia = montar_conferencia(df_cfop, df_resumo)

    if df_cfop.empty and df_resumo.empty:
        raise ValueError("Nenhum dado útil foi encontrado nos PDFs.")

    pares = set()

    if not df_cfop.empty:
        pares.update(tuple(x) for x in df_cfop[["Período"]].drop_duplicates().values.tolist())

    if not df_resumo.empty:
        pares.update(tuple(x) for x in df_resumo[["Período"]].drop_duplicates().values.tolist())

    arquivos_gerados = []

    total_periodos = max(1, len(pares))
    for idx, (periodo,) in enumerate(sorted(pares, key=lambda x: str(x[0])), start=1):
        if progress_callback:
            progress_callback("gerando_excel", idx, total_periodos, f"Período {periodo}")

        periodo_txt = formatar_periodo(periodo if pd.notna(periodo) else "SEM_PERIODO")
        nome_arquivo = f"RAICMS - {periodo_txt}.xlsx"
        caminho_saida = os.path.join(pasta_destino, nome_arquivo)

        df_cfop_grupo = df_cfop[(df_cfop["Período"] == periodo)] if not df_cfop.empty else pd.DataFrame()
        df_resumo_grupo = df_resumo[(df_resumo["Período"] == periodo)] if not df_resumo.empty else pd.DataFrame()
        df_conferencia_grupo = montar_conferencia(df_cfop_grupo, df_resumo_grupo)

        with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
            if not df_cfop_grupo.empty:
                df_cfop_grupo.to_excel(writer, index=False, sheet_name="Consolidado")
            else:
                pd.DataFrame(columns=[
                    "Arquivo PDF", "Filial", "Divisão", "Página", "Firma", "IE", "CNPJ", "Período", "Tipo", "Status",
                    "CFOP", "Valores Contábeis", "Base de Cálculo", "Imposto Creditado",
                    "Isentas ou não Trib.", "Outras"
                ]).to_excel(writer, index=False, sheet_name="Consolidado")

            if not df_resumo_grupo.empty:
                df_resumo_grupo.to_excel(writer, index=False, sheet_name="Resumo_Apuracao")
            else:
                pd.DataFrame(columns=[
                    "Arquivo PDF", "Filial", "Divisão", "Página", "Firma", "IE", "CNPJ",
                    "Período", "Seção", "Tipo", "Status", "Número", "Descrição", "Coluna Auxiliar", "Somas"
                ]).to_excel(writer, index=False, sheet_name="Resumo_Apuracao")

            df_conferencia_grupo.to_excel(writer, index=False, sheet_name="Conferência")

        aplicar_formatacao_excel(caminho_saida)
        arquivos_gerados.append(caminho_saida)

    if progress_callback:
        progress_callback("gerando_excel", total_periodos, total_periodos, "Consolidado geral")

    caminho_consolidado = os.path.join(pasta_destino, "RAICMS - Consolidado Geral.xlsx")
    with pd.ExcelWriter(caminho_consolidado, engine="openpyxl") as writer:
        df_cfop.to_excel(writer, index=False, sheet_name="Consolidado")
        df_resumo.to_excel(writer, index=False, sheet_name="Resumo_Apuracao")
        df_conferencia.to_excel(writer, index=False, sheet_name="Conferência")

    aplicar_formatacao_excel(caminho_consolidado)
    arquivos_gerados.append(caminho_consolidado)

    return {
        "arquivos_pdf": len(arquivos_pdf),
        "linhas_cfop": len(df_cfop),
        "linhas_resumo": len(df_resumo),
        "tempo_total": round(time.time() - t0, 2),
        "arquivo_final": caminho_consolidado,
        "arquivos_gerados": arquivos_gerados
    }