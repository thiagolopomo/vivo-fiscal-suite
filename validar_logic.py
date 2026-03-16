#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import json

from pathlib import Path

import pyarrow.parquet as pq
import pythoncom
import polars as pl

from openpyxl import Workbook

os.environ.setdefault("POLARS_MAX_THREADS", "1")


PARQUET_NOME = "VIVO_TXTS_CONSOLIDADO.parquet"
TMP_NOME = "_tmp_shards_vivo"
CACHE_DIR = Path.home() / "AppData" / "Local" / "ValidadorVIVO"
CACHE_PARQUET = CACHE_DIR / "base_processada.parquet"
CACHE_META = CACHE_DIR / "base_processada_meta.json"

LOGO_VIVO_ARQ = "logo_vivo.png"

COMPRESSION = "zstd"
ROW_GROUP = 100_000
PIPE_PLACEHOLDER = "<<<PIPE_DESC>>>"

ARQ_TABELA_DIV = "Tabela_Divisao.csv"
ARQ_CFOP_MAP = "Mapeamento_CFOP.csv"


# =========================
# RECURSOS
# =========================
def caminho_recurso(nome_arquivo):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, nome_arquivo)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nome_arquivo)


# =========================
# FUNÇÕES DO SCRIPT
# =========================
def csv_para_xlsb_via_excel(csv_path, xlsb_path, sheet_name="Plan1", progress_callback=None, progresso_base=0, progresso_total=100):
    import win32com.client as win32

    pythoncom.CoInitialize()

    excel = None
    wb = None

    def report(passo, msg):
        if progress_callback:
            progress_callback("exportando_xlsx", passo, progresso_total, msg)

    try:
        csv_path = str(Path(csv_path).resolve())
        xlsb_path = str(Path(xlsb_path).resolve())

        report(progresso_base + 1, "Abrindo Excel...")
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.EnableEvents = False
        excel.AskToUpdateLinks = False
        excel.DisplayStatusBar = False
        excel.Interactive = False
        excel.UserControl = False

        try:
            excel.AutoRecover.Enabled = False
        except Exception:
            pass

        report(progresso_base + 2, "Abrindo CSV no Excel...")
        excel.Workbooks.OpenText(
            Filename=csv_path,
            Origin=65001,
            StartRow=1,
            DataType=1,
            TextQualifier=1,
            ConsecutiveDelimiter=False,
            Tab=False,
            Semicolon=True,
            Comma=False,
            Space=False,
            Other=False,
            Local=True
        )

        wb = excel.ActiveWorkbook

        report(progresso_base + 3, "Carregando dados na planilha...")
        try:
            wb.Worksheets(1).Name = sheet_name[:31]
        except Exception:
            pass

        report(progresso_base + 4, "Salvando arquivo XLSB...")
        wb.SaveAs(xlsb_path, FileFormat=50)

        report(progresso_base + 5, "Fechando arquivo...")
        wb.Close(False)
        wb = None

        excel.Quit()
        excel = None

        report(progresso_base + 6, "Conversão concluída.")

    finally:
        try:
            if wb is not None:
                wb.Close(False)
        except Exception:
            pass

        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass

        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def excel_col_name(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def escrever_bloco_excel(ws, row_ini, col_ini, dados):
    if not dados:
        return

    nrows = len(dados)
    ncols = len(dados[0]) if nrows else 0
    if ncols == 0:
        return

    col_fim = col_ini + ncols - 1
    row_fim = row_ini + nrows - 1

    a1 = f"{excel_col_name(col_ini)}{row_ini}"
    b2 = f"{excel_col_name(col_fim)}{row_fim}"

    ws.Range(a1, b2).Value = dados


def escrever_xlsx_via_excel_com(parquet_path, caminho_saida, sheet_name, processar_batch, progress_callback=None):
    import win32com.client as win32

    pythoncom.CoInitialize()

    excel = None
    wb = None

    try:
        parquet_path = str(parquet_path)
        caminho_saida = str(Path(caminho_saida).resolve())

        batch_size = 25_000
        max_excel_rows = 1_048_576

        pf = pq.ParquetFile(parquet_path)

        total_batches = 0
        if pf.metadata:
            for i in range(pf.metadata.num_row_groups):
                rg = pf.metadata.row_group(i)
                n = rg.num_rows
                total_batches += max(1, (n + batch_size - 1) // batch_size)

        if total_batches <= 0:
            total_batches = 1

        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.EnableEvents = False
        excel.AskToUpdateLinks = False

        wb = excel.Workbooks.Add()
        ws = wb.Worksheets(1)
        ws.Name = sheet_name[:31]

        header_escrito = False
        row_excel = 1
        linhas_lidas = 0
        linhas_gravadas = 0
        lote = 0

        for batch in pf.iter_batches(batch_size=batch_size, use_threads=True):
            linhas_lidas += batch.num_rows

            df = pl.from_arrow(batch)
            df = processar_batch(df)

            lote += 1

            if df.height == 0:
                if progress_callback:
                    progress_callback(
                        "exportando_xlsx",
                        lote,
                        total_batches,
                        f"Lote {lote}/{total_batches} | lidas: {linhas_lidas:,} | gravadas: {linhas_gravadas:,}"
                    )
                continue

            if not header_escrito:
                header = [str(c) for c in df.columns]
                escrever_bloco_excel(ws, 1, 1, [header])
                header_escrito = True
                row_excel = 2

            if row_excel + df.height - 1 > max_excel_rows:
                raise ValueError(
                    f"O Excel suporta no máximo {max_excel_rows:,} linhas por aba "
                    f"(incluindo cabeçalho). A exportação excedeu esse limite."
                )

            dados = df.rows()
            escrever_bloco_excel(ws, row_excel, 1, dados)

            row_excel += df.height
            linhas_gravadas += df.height

            if progress_callback:
                progress_callback(
                    "exportando_xlsx",
                    lote,
                    total_batches,
                    f"Lote {lote}/{total_batches} | lidas: {linhas_lidas:,} | gravadas: {linhas_gravadas:,}"
                )

        if not header_escrito:
            ws.Cells(1, 1).Value = ""

        wb.SaveAs(caminho_saida, FileFormat=51)
        wb.Close(False)
        wb = None

        excel.Quit()
        excel = None

        if progress_callback:
            progress_callback(
                "finalizado_xlsx",
                total_batches + 8,
                total_batches + 8,
                f"Exportação concluída | gravadas: {linhas_gravadas:,}"
            )

    finally:
        try:
            if wb is not None:
                wb.Close(False)
        except Exception:
            pass

        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass

        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def lista_unica(seq):
    vistos = set()
    out = []
    for x in seq:
        if x not in vistos:
            vistos.add(x)
            out.append(x)
    return out


def escrever_xlsx_bruto_texto(df, caminho_saida, nome_aba="BASE_VIVO"):
    caminho_saida = str(caminho_saida)

    max_excel_rows = 1_048_576
    total_rows_planilha = df.height + 1

    if total_rows_planilha > max_excel_rows:
        raise ValueError(
            f"O Excel suporta no máximo {max_excel_rows:,} linhas por aba. "
            f"A exportação teria {total_rows_planilha:,} linhas incluindo o cabeçalho."
        )

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=nome_aba[:31])

    ws.append([str(c) for c in df.columns])

    for fatia in df.iter_slices(n_rows=50_000):
        for row in fatia.iter_rows(named=False, buffer_size=50_000):
            ws.append(list(row))

    wb.save(caminho_saida)
    wb.close()


def limpar_colunas_csv(df):
    novas = []
    for c in df.columns:
        novo = (
            c.replace("ï»¿", "")
             .replace("Ã³", "ó")
             .replace("Ã£", "ã")
             .replace("Ã§", "ç")
             .replace("Ã©", "é")
             .replace("Ãª", "ê")
             .replace("Ã¡", "á")
             .replace("Ã­", "í")
             .replace("Ãº", "ú")
             .strip()
        )
        novas.append(novo)
    df.columns = novas
    return df


def carregar_divisoes_df():
    df = pl.read_csv(
        caminho_recurso(ARQ_TABELA_DIV),
        separator=";",
        encoding="utf8",
        ignore_errors=True
    )
    df = limpar_colunas_csv(df)

    return (
        df.select([
            pl.col("Local de Negócios").cast(pl.Utf8),
            pl.col("Divisão").cast(pl.Utf8).alias("Divisão_DePara"),
        ])
        .unique(subset=["Local de Negócios"], keep="first")
    )


def carregar_cfop_df():
    df = pl.read_csv(
        caminho_recurso(ARQ_CFOP_MAP),
        separator=";",
        encoding="utf8",
        ignore_errors=True
    )
    df = limpar_colunas_csv(df)

    return (
        df.select([
            pl.col("CFOP").cast(pl.Utf8).str.strip_chars().alias("CFOP"),
            pl.col("Mapeamento").cast(pl.Utf8).str.strip_chars().alias("Mapeamento"),
        ])
        .unique(subset=["CFOP"], keep="first")
    )


def detectar_header(path):
    with open(path, "r", encoding="latin-1", errors="ignore") as f:
        for i, linha in enumerate(f):
            up = linha.upper()
            if "|" in linha and ("CHAVE DA NOTA" in up or "MNFSM_CHV_NFE" in up):
                header = [c.strip() for c in linha.rstrip("\r\n").split("|")]
                return i, header
    return None, None


def limpar_nomes_colunas(cols):
    vistos = {}
    saida = []

    for c in cols:
        nome = c.strip() or "COLUNA_VAZIA"
        if nome in vistos:
            vistos[nome] += 1
            nome = f"{nome}_{vistos[nome]}"
        else:
            vistos[nome] = 1
        saida.append(nome)

    return saida


def linha_eh_lixo(linha):
    s = linha.strip()
    up = s.upper()

    if not s:
        return True

    if set(s) <= {"-", "|"}:
        return True

    if "MNFSM_CHV_NFE" in up or "CHAVE DA NOTA" in up:
        return True

    if re.fullmatch(r"\d+\s+linhas\s+selecionadas\.?", s, flags=re.IGNORECASE):
        return True

    return False


def descobrir_idx_dsc(header_cols):
    prioridades = [
        "DSC",
        "INFSM_DSC",
        "DSC_1",
        "DESCRICAO",
        "DESCRIÇÃO",
    ]

    upper_cols = [c.upper() for c in header_cols]

    for alvo in prioridades:
        if alvo in upper_cols:
            return upper_cols.index(alvo)

    for i, c in enumerate(upper_cols):
        if "DSC" in c:
            return i

    return None


def corrigir_pipe_na_descricao(linha, ncols, idx_dsc):
    cols = linha.rstrip("\r\n").split("|")

    if idx_dsc is None:
        if len(cols) < ncols:
            cols.extend([""] * (ncols - len(cols)))
        elif len(cols) > ncols:
            cols = cols[:ncols]
        return "|".join(cols)

    if len(cols) == ncols:
        return "|".join(cols)

    if len(cols) < ncols:
        cols.extend([""] * (ncols - len(cols)))
        return "|".join(cols)

    right_count = ncols - idx_dsc - 1

    left = cols[:idx_dsc]

    if right_count > 0:
        right = cols[-right_count:]
        middle = cols[idx_dsc:-right_count]
    else:
        right = []
        middle = cols[idx_dsc:]

    dsc = PIPE_PLACEHOLDER.join(middle)

    cols_corrigidas = left + [dsc] + right

    if len(cols_corrigidas) < ncols:
        cols_corrigidas.extend([""] * (ncols - len(cols_corrigidas)))
    elif len(cols_corrigidas) > ncols:
        cols_corrigidas = cols_corrigidas[:ncols]

    return "|".join(cols_corrigidas)


def extrair_divisao_arquivo(nome):
    nome_up = (nome or "").upper()

    if "0001SP" in nome_up:
        return "29SP"

    m = re.search(r"NFE_([0-9]{2}[A-Z]{2})", nome_up)
    if m:
        return m.group(1)

    return ""


def montar_ordem_final(cols):
    remover = {"DivArquivo", "Divisão_DePara", "CFOP", "__ordem__"}

    base = [c for c in cols if c not in remover]

    for c in ["Fonte", "Período", "Nome do Arquivo", "Divisão", "Mapeamento"]:
        if c in base:
            base.remove(c)

    ordem = ["Fonte", "Período", "Nome do Arquivo"]

    for c in base:
        ordem.append(c)

        if c == "EMPRESA" and "Divisão" in cols and "Divisão" not in ordem:
            ordem.append("Divisão")

        if c == "CFOP_COD" and "Mapeamento" in cols and "Mapeamento" not in ordem:
            ordem.append("Mapeamento")

    for c in ["Divisão", "Mapeamento"]:
        if c in cols and c not in ordem:
            ordem.append(c)

    return ordem


def detectar_tipo_movimento(arquivos):
    tem_ent = False
    tem_sai = False

    for arq in arquivos:
        nome = Path(arq).name.upper()

        if "ENT" in nome:
            tem_ent = True

        if "SAI" in nome or "SAIDA" in nome:
            tem_sai = True

    if tem_ent and tem_sai:
        raise ValueError(
            "A pasta contém arquivos de ENTRADA e SAÍDA juntos. "
            "Processe apenas um tipo por vez."
        )

    if tem_ent:
        return "ENTRADA"

    if tem_sai:
        return "SAIDA"

    raise ValueError(
        "Não foi possível identificar se os arquivos são de ENTRADA ou SAÍDA "
        "pelos nomes dos TXT."
    )


def salvar_meta_cache(tipo_movimento, base_dir, pasta_destino):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    meta = {
        "tipo_movimento": tipo_movimento,
        "base_dir": str(base_dir),
        "pasta_destino": str(pasta_destino),
        "cache_parquet": str(CACHE_PARQUET),
    }

    with open(CACHE_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def carregar_meta_cache():
    if not CACHE_META.exists():
        return None

    with open(CACHE_META, "r", encoding="utf-8") as f:
        return json.load(f)


def selecionar_colunas_existentes(df, colunas_desejadas):
    cols_existentes = df.columns
    ordem_final = [c for c in colunas_desejadas if c in cols_existentes]
    return df.select(ordem_final)


def renomear_colunas_parcial(df, mapa_renomeio):
    ren = {k: v for k, v in mapa_renomeio.items() if k in df.columns}
    if ren:
        df = df.rename(ren)
    return df


def exportar_versao_andersen(parquet_path, pasta_destino, progress_callback=None):
    pasta_destino = Path(pasta_destino)
    out_csv = pasta_destino / "BASE_ANDERSEN.csv"

    pf = pq.ParquetFile(parquet_path)
    writer_iniciado = False

    total_batches = 0
    if pf.metadata:
        for i in range(pf.metadata.num_row_groups):
            rg = pf.metadata.row_group(i)
            n = rg.num_rows
            total_batches += max(1, (n + 249_999) // 250_000)

    if total_batches <= 0:
        total_batches = 1

    batches_processados = 0
    linhas_lidas = 0
    linhas_gravadas = 0

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        f.write("\ufeff")

        for batch in pf.iter_batches(batch_size=250_000, use_threads=True):
            linhas_lidas += batch.num_rows
            df = pl.from_arrow(batch)

            df = df.with_columns([
                pl.col(c).str.strip_chars().alias(c)
                for c in df.columns
                if df.schema[c] == pl.Utf8
            ])

            df.write_csv(
                f,
                separator=";",
                include_header=not writer_iniciado,
                null_value="",
                line_terminator="\n",
                quote_style="necessary"
            )

            writer_iniciado = True
            batches_processados += 1
            linhas_gravadas += df.height

            if progress_callback and (
                batches_processados == 1
                or batches_processados == total_batches
                or batches_processados % 5 == 0
            ):
                progress_callback(
                    "exportando_csv",
                    batches_processados,
                    total_batches,
                    f"Gerando CSV ANDERSEN | lote {batches_processados}/{total_batches} | lidas: {linhas_lidas:,} | gravadas: {linhas_gravadas:,}"
                )

    if progress_callback:
        progress_callback(
            "finalizado_csv",
            total_batches,
            total_batches,
            f"Exportação concluída | gravadas: {linhas_gravadas:,}"
        )

    return out_csv


def exportar_versao_vivo(parquet_path, pasta_destino, tipo_movimento, progress_callback=None):
    tipo = (tipo_movimento or "").upper()
    parquet_path = str(parquet_path)
    pasta_destino = Path(pasta_destino)

    def normalizar_colunas_filtro(df, cols):
        exprs = []
        for c in cols:
            if c in df.columns:
                exprs.append(
                    pl.col(c)
                    .cast(pl.Utf8)
                    .fill_null("")
                    .str.strip_chars()
                    .str.to_uppercase()
                    .alias(c)
                )
        if exprs:
            df = df.with_columns(exprs)
        return df

    def escrever_csv_final(parquet_path, csv_out, processar_batch):
        pf = pq.ParquetFile(parquet_path)

        total_batches = 0
        if pf.metadata:
            for i in range(pf.metadata.num_row_groups):
                rg = pf.metadata.row_group(i)
                n = rg.num_rows
                total_batches += max(1, (n + 99_999) // 100_000)

        if total_batches <= 0:
            total_batches = 1

        batches_processados = 0
        linhas_lidas = 0
        linhas_gravadas = 0
        writer_iniciado = False

        with open(csv_out, "w", encoding="utf-8", newline="") as f:
            f.write("\ufeff")

            for batch in pf.iter_batches(batch_size=100_000, use_threads=True):
                linhas_lidas += batch.num_rows
                df = pl.from_arrow(batch)
                df = processar_batch(df)
                batches_processados += 1

                if df.height == 0:
                    if progress_callback and (
                        batches_processados == 1
                        or batches_processados == total_batches
                        or batches_processados % 5 == 0
                    ):
                        progress_callback(
                            "exportando_csv",
                            batches_processados,
                            total_batches,
                            f"Gerando CSV VIVO | lote {batches_processados}/{total_batches} | lidas: {linhas_lidas:,} | gravadas: {linhas_gravadas:,}"
                        )
                    continue

                df = df.with_columns([
                    pl.col(c).str.strip_chars().alias(c)
                    for c in df.columns
                    if df.schema[c] == pl.Utf8
                ])

                df.write_csv(
                    f,
                    separator=";",
                    include_header=not writer_iniciado,
                    null_value="",
                    line_terminator="\n",
                    quote_style="necessary"
                )

                writer_iniciado = True
                linhas_gravadas += df.height

                if progress_callback and (
                    batches_processados == 1
                    or batches_processados == total_batches
                    or batches_processados % 5 == 0
                ):
                    progress_callback(
                        "exportando_csv",
                        batches_processados,
                        total_batches,
                        f"Gerando CSV VIVO | lote {batches_processados}/{total_batches} | lidas: {linhas_lidas:,} | gravadas: {linhas_gravadas:,}"
                    )

        return linhas_gravadas, total_batches

    if tipo == "ENTRADA":
        excluir_cfop = ["1923", "2923", "1915", "2915", "1154", "2154", "1403", "2403", "1555", "2555"]

        ordem_entrada = [
            "ID_ORIGEM", "EMPRESA", "FILIAL", "Divisão", "UF", "DTEMIS", "DTENTR",
            "INFEM_NUM", "CFOP_COD", "VAL_ICMS", "Mapeamento", "TRIBICM", "IND_CANC",
            "VALSUBST_ICMS", "IND_TRIB_SUBSTRIB", "VAL_IPI", "TRIBIPI", "VAL_CONT",
            "ALIQ_DIFICMS", "BAS_ICMS", "ALIQ_ICMS", "ISENTA_ICMS", "VAL_REDICMS",
            "OUTRA_ICMS", "BASSUBST_ICMS", "ALIQ_ST", "VAL_ISEN_SUBSTRIB",
            "VAL_OUTR_SUBSTRIB", "BAS_IPI", "ALIQ_IPI", "ISENTA_IPI", "VAL_REDIPI",
            "OUTRA_IPI", "NOPE_COD", "VAR02", "CNPJ/CPF", "IE", "MOD_DOC", "TDOC_COD",
            "SERIE", "CATG_COD", "CADG_COD", "NUM_ITEM", "MATE_COD", "DSC", "CCUS_COD",
            "CNBM_COD", "UNID_COD_PADRAO", "QTD", "PES_LIQ", "VAL_PRECOUNIT",
            "VAL_PRECOTOT", "VAL_DESC", "VAL_FRETE", "VAL_SEGUR", "IND_MOV",
            "COD_CONT", "NUM_FCI", "FCP_DEST", "ICMS_DEST", "ICMS_ORIG", "FCP_ST",
            "SIST_ORIGEM", "USUA_ORIGEM", "DATA_CRIACAO", "CHAVE DA NOTA", "Nome do Arquivo",
        ]

        mapa_entrada = {
            "ID_ORIGEM": "ID Origem",
            "EMPRESA": "Empresa",
            "FILIAL": "Filial",
            "Divisão": "Divisão",
            "UF": "Unidade Federativa",
            "DTEMIS": "Emissão",
            "DTENTR": "Entrada",
            "INFEM_NUM": "Nota Fiscal",
            "CFOP_COD": "CFOP",
            "VAL_ICMS": "Valor do ICMS",
            "Mapeamento": "Mapeamento",
            "TRIBICM": "Indicador de Tributação de ICMS",
            "IND_CANC": "Indicador de Cancelamento",
            "VALSUBST_ICMS": "Valor Subst. ICMS",
            "IND_TRIB_SUBSTRIB": "Tributação.Subs.Trib.",
            "VAL_IPI": "Valor do IPI",
            "TRIBIPI": "Indicador Trib. IPI",
            "VAL_CONT": "Valor Contábil",
            "ALIQ_DIFICMS": "Alíq. Dif. ICMS",
            "BAS_ICMS": "Base de ICMS",
            "ALIQ_ICMS": "Alíquota de ICMS",
            "ISENTA_ICMS": "Valor Isenta ICMS",
            "VAL_REDICMS": "Valor de Redução da Base",
            "OUTRA_ICMS": "Valor Outras ICMS",
            "BASSUBST_ICMS": "Base Subst. ICMS",
            "ALIQ_ST": "Alíquota do ICMS - ST",
            "VAL_ISEN_SUBSTRIB": "Isent. Subst.Trib.",
            "VAL_OUTR_SUBSTRIB": "Outr. Subst.Trib.",
            "BAS_IPI": "Valor de Base de IPI",
            "ALIQ_IPI": "Aliq. de IPI",
            "ISENTA_IPI": "Valor Isenta IPI",
            "VAL_REDIPI": "Valor de Redução do IPI",
            "OUTRA_IPI": "Valor Outras IPI",
            "NOPE_COD": "Natureza da Operação",
            "VAR02": "OpenFlex 02",
            "CNPJ/CPF": "CNPJ/CPF",
            "IE": "Inscricao Estadual",
            "MOD_DOC": "Modelo de Documento",
            "TDOC_COD": "Tipo de Documento",
            "SERIE": "Serie",
            "CATG_COD": "Categoria",
            "CADG_COD": "Código PF/PJ",
            "NUM_ITEM": "Numero do Item",
            "MATE_COD": "Material",
            "DSC": "Descrição Complementar",
            "CCUS_COD": "Centro de Custo",
            "CNBM_COD": "Classificação Fiscal",
            "UNID_COD_PADRAO": "Unid. Padrão de Venda",
            "QTD": "Quantidade",
            "PES_LIQ": "Peso Liquido",
            "VAL_PRECOUNIT": "Preco Unitario",
            "VAL_PRECOTOT": "Preco Total",
            "VAL_DESC": "Desconto",
            "VAL_FRETE": "Frete",
            "VAL_SEGUR": "Seguro",
            "IND_MOV": "Indicador de Movimento",
            "COD_CONT": "Código Contábil",
            "NUM_FCI": "Número da FCI",
            "FCP_DEST": "Valor FCP UF Destino",
            "ICMS_DEST": "Valor ICMS UF Destino",
            "ICMS_ORIG": "Valor ICMS UF Origem",
            "FCP_ST": "Valor Unitário do FCP ST convertido",
            "SIST_ORIGEM": "Sistema de Origem",
            "USUA_ORIGEM": "Usuário de Origem",
            "DATA_CRIACAO": "Data Integração",
            "CHAVE DA NOTA": "Chave Nota Fiscal",
            "Nome do Arquivo": "Nome Arquivo",
        }

        def processar_batch_entrada(df):
            df = normalizar_colunas_filtro(df, ["CFOP_COD", "IND_CANC", "TRIBICMS", "TRIBICM"])
            col_trib = "TRIBICMS" if "TRIBICMS" in df.columns else ("TRIBICM" if "TRIBICM" in df.columns else None)

            filtros = []
            if col_trib is not None:
                filtros.append(pl.col(col_trib) == "S")
            if "IND_CANC" in df.columns:
                filtros.append(pl.col("IND_CANC") == "N")
            if "CFOP_COD" in df.columns:
                filtros.append(~pl.col("CFOP_COD").is_in(excluir_cfop))

            if filtros:
                expr = filtros[0]
                for f in filtros[1:]:
                    expr = expr & f
                df = df.filter(expr)

            df = selecionar_colunas_existentes(df, ordem_entrada)
            df = renomear_colunas_parcial(df, mapa_entrada)
            return df

        nome_csv = "BASE_VIVO_ENTRADA.csv"
        processar_batch = processar_batch_entrada

    elif tipo == "SAIDA":
        ordem_saida = lista_unica([
            "Índice", "Fonte", "Período", "ID_ORIGEM", "EMPRESA", "FILIAL", "Divisão", "UF",
            "INFSM_DTEM", "INFSM_NUM", "CFOP_COD", "INFSM_VAL_ICMS", "Mapeamento", "I_2",
            "IND_CANC", "INFSM_VALSUBST_ICMS", "IND_TRIB_SUBSTRIB", "INFSM_VAL_IPI", "I",
            "INFSM_VAL_CONT", "INFSM_ALIQ_DIFICMS", "INFSM_BAS_ICMS", "INFSM_ALIQ_ICMS",
            "INFSM_ISENTA_ICMS", "INFSM_VAL_REDICMS", "INFSM_OUTRA_ICMS",
            "INFSM_BASSUBST_ICMS", "INFSM_ALIQ_ST", "VAL_ISEN_SUBSTRIB", "VAL_OUTR_SUBSTRIB",
            "INFSM_BAS_IPI", "INFSM_ALIQ_IPI", "INFSM_ISENTA_IPI", "INFSM_VAL_REDIPI",
            "INFSM_OUTRA_IPI", "NOPE_COD", "VAR02", "CNPJ/CPF", "IE", "MOD_DOC", "TDOC_COD",
            "INFSM", "CATG_COD", "CADG_COD", "INFSM_2", "MATE_COD", "INFSM_DSC", "CCUS_COD",
            "CNBM_COD", "UNID_COD_VENDA", "INFSM_QTD", "INFSM_PES_LIQ", "INFSM_VAL_PRECOUNIT",
            "INFSM_VAL_PRECOTOT", "INFSM_VAL_DESC", "INFSM_VAL_FRETE", "INFSM_VAL_SEGUR",
            "INFSM_COD_CONT", "INFSM_NUM_FCI", "INFSM_FCP_DEST", "INFSM_ICMS_DEST",
            "INFSM_ICMS_ORIG", "INFSM_FCP_ST_REST", "SIST_ORIGEM", "USUA_ORIGEM",
            "DATA_CRIACAO", "MNFSM_CHV_NFE", "Nome do Arquivo", "INFSM_VAL_DESP", "FEDE_COD",
            "INFSM_ICMS_FRETE", "INFSM_CHASSI", "LIPI_COD", "INFSM_FCP_PRO", "INFSM_FCP_RET",
            "INFSM_FCP_ST", "INFSM_QTD_CONV", "INFSM_VLR_CONV", "INFSM_ICMS_CONV",
            "INFSM_VAL_ICMS_OP_CONV", "INFSM_BC_ICMS_ST_CONV", "INFSM_ICMS_ST_EST",
            "INFSM_FCP_ST_EST", "INFSM_ICMS_ST_REST", "INFSM_ICMS_ST_COMP",
            "INFSM_FCP_ST_COMP", "TMRC_COD",
        ])

        mapa_saida = {
            "Índice": "Índice",
            "Fonte": "Fonte",
            "Período": "Período",
            "ID_ORIGEM": "ID Origem",
            "EMPRESA": "Empresa",
            "FILIAL": "Filial",
            "Divisão": "Divisão",
            "UF": "UF",
            "INFSM_DTEM": "Data Emissão",
            "INFSM_NUM": "Nota Fiscal",
            "CFOP_COD": "CFOP",
            "INFSM_VAL_ICMS": "Vr. de ICMS",
            "Mapeamento": "Mapeamento",
            "I_2": "Indicador de Trib. ICMS",
            "IND_CANC": "Indicador de Cancelamento",
            "INFSM_VALSUBST_ICMS": "Vr. do ICMS por Substituto",
            "IND_TRIB_SUBSTRIB": "Indicador deTrib. Subs.Trib.",
            "INFSM_VAL_IPI": "Vr. do IPI",
            "I": "Indicador de Trib. IPI",
            "INFSM_VAL_CONT": "Vlr. Contábil",
            "INFSM_ALIQ_DIFICMS": "Alíquota ICMS DIFAL",
            "INFSM_BAS_ICMS": "Base de ICMS",
            "INFSM_ALIQ_ICMS": "Aliquota ICMS",
            "INFSM_ISENTA_ICMS": "Isenta ICMS",
            "INFSM_VAL_REDICMS": "Vr. de Redução de ICMS",
            "INFSM_OUTRA_ICMS": "Vlr. outra ICMS",
            "INFSM_BASSUBST_ICMS": "Vr. Base de Substituição ICMS",
            "INFSM_ALIQ_ST": "Aliquota do ICMS-ST",
            "VAL_ISEN_SUBSTRIB": "Valor Isent. Subst.Trib.",
            "VAL_OUTR_SUBSTRIB": "Valor Outr. Subst.Trib",
            "INFSM_BAS_IPI": "Base de IPI",
            "INFSM_ALIQ_IPI": "Aliquota de IPI",
            "INFSM_ISENTA_IPI": "Isenta de IPI",
            "INFSM_VAL_REDIPI": "Valor de Redução do IPI",
            "INFSM_OUTRA_IPI": "Vlr. de Outra de IPI",
            "NOPE_COD": "Natureza",
            "VAR02": "OpenFlex 02",
            "CNPJ/CPF": "CNPJ/CPF",
            "IE": "Inscrição Estadual",
            "MOD_DOC": "Modelo de Documento",
            "TDOC_COD": "Tipo de Documento",
            "INFSM": "Série",
            "CATG_COD": "Categoria",
            "CADG_COD": "Código PF\\PJ",
            "INFSM_2": "Item",
            "MATE_COD": "Material",
            "INFSM_DSC": "Descrição",
            "CCUS_COD": "Centro de Custo",
            "CNBM_COD": "NCM",
            "UNID_COD_VENDA": "Unidade Código Padrão",
            "INFSM_QTD": "Quantidade",
            "INFSM_PES_LIQ": "Peso Líquido",
            "INFSM_VAL_PRECOUNIT": "Preço Unitário",
            "INFSM_VAL_PRECOTOT": "Preço Total",
            "INFSM_VAL_DESC": "Valor de Desconto",
            "INFSM_VAL_FRETE": "Vr. do Frete",
            "INFSM_VAL_SEGUR": "Vr. Seguro",
            "INFSM_COD_CONT": "Código Contábil",
            "INFSM_NUM_FCI": "Número da FCI",
            "INFSM_FCP_DEST": "Valor FCP UF Destino",
            "INFSM_ICMS_DEST": "Valor ICMS UF Destino",
            "INFSM_ICMS_ORIG": "Valor ICMS UF Origem",
            "INFSM_FCP_ST_REST": "Valor Unitário FCP ST Convertido A Restituir",
            "SIST_ORIGEM": "Sistema de Origem",
            "USUA_ORIGEM": "Usuário de Origem",
            "DATA_CRIACAO": "Data de Criação",
            "MNFSM_CHV_NFE": "Chave de Acesso",
            "Nome do Arquivo": "FileName",
            "INFSM_VAL_DESP": "Vr. Despesa",
            "FEDE_COD": "Sit. Trib. Federal",
            "INFSM_ICMS_FRETE": "ICMS sobre Frete",
            "INFSM_CHASSI": "Número do Chassi",
            "LIPI_COD": "CST IPI",
            "INFSM_FCP_PRO": "Valor do Fundo de Combate à Pobreza (FCP) Próprio",
            "INFSM_FCP_RET": "Valor do Fundo de Combate à Pobreza (FCP) Retido",
            "INFSM_FCP_ST": "Valor do Fundo de Combate à Pobreza (FCP) ST",
            "INFSM_QTD_CONV": "Quantidade do Item convertida",
            "INFSM_VLR_CONV": "Valor unitário convertido",
            "INFSM_ICMS_CONV": "Valor unitário ICMS Operação convertido",
            "INFSM_VAL_ICMS_OP_CONV": "Valor unitário ICMS operação de Entrada Convertido",
            "INFSM_BC_ICMS_ST_CONV": "Valor unitário da Base de Cálculo do ICMS ST Convertido",
            "INFSM_ICMS_ST_EST": "Valor Unitário ICMS ST Estoque Convertido",
            "INFSM_FCP_ST_EST": "Valor Unitário FCP ICMS ST Estoque Convertidos",
            "INFSM_ICMS_ST_REST": "Valor Unitario ICMS ST Convertido a Restituir",
            "INFSM_ICMS_ST_COMP": "Valor unitário do ICMS ST Convertido",
            "INFSM_FCP_ST_COMP": "Valor Unitário do FCP ST convertido",
            "TMRC_COD": "Tab105",
        }

        def processar_batch_saida(df):
            df = normalizar_colunas_filtro(df, ["I_2", "IND_CANC"])

            filtros = []
            if "I_2" in df.columns:
                filtros.append(pl.col("I_2") == "S")
            if "IND_CANC" in df.columns:
                filtros.append(pl.col("IND_CANC") == "N")

            if filtros:
                expr = filtros[0]
                for f in filtros[1:]:
                    expr = expr & f
                df = df.filter(expr)

            df = selecionar_colunas_existentes(df, ordem_saida)
            df = renomear_colunas_parcial(df, mapa_saida)
            return df

        nome_csv = "BASE_VIVO_SAIDA.csv"
        processar_batch = processar_batch_saida

    else:
        raise ValueError("Tipo de movimento não identificado para exportação VIVO.")

    out_csv = Path(pasta_destino) / nome_csv

    linhas_gravadas, total_batches = escrever_csv_final(
        parquet_path=parquet_path,
        csv_out=str(out_csv),
        processar_batch=processar_batch
    )

    if progress_callback:
        progress_callback(
            "finalizado_csv",
            total_batches,
            total_batches,
            f"Exportação concluída | gravadas: {linhas_gravadas:,}"
        )

    return out_csv


def criar_txt_limpo(path_txt, tmp_txt):
    header_line, header_raw = detectar_header(path_txt)
    if header_line is None:
        return None, None, 0

    header = limpar_nomes_colunas(header_raw)
    ncols = len(header)
    idx_dsc = descobrir_idx_dsc(header)
    kept = 0

    with open(path_txt, "r", encoding="latin-1", errors="ignore") as fin, \
         open(tmp_txt, "w", encoding="latin-1", errors="ignore", newline="") as fout:

        for _ in range(header_line + 1):
            next(fin)

        fout.write("|".join(header) + "\n")

        for linha in fin:
            if linha_eh_lixo(linha):
                continue

            linha_corrigida = corrigir_pipe_na_descricao(linha, ncols, idx_dsc)
            fout.write(linha_corrigida + "\n")
            kept += 1

    return header, header_raw, kept


def processar_arquivo(args):
    path_txt_str, tmp_dir_str = args

    path_txt = Path(path_txt_str)
    tmp_dir = Path(tmp_dir_str)

    shard_out = tmp_dir / f"{path_txt.stem}.parquet"
    txt_limpo = tmp_dir / f"{path_txt.stem}__limpo.txt"

    header, header_raw, kept = criar_txt_limpo(path_txt, txt_limpo)
    if header is None:
        return {"arquivo": path_txt.name, "linhas": 0, "ok": False, "motivo": "header não encontrado"}

    df = pl.read_csv(
        txt_limpo,
        separator="|",
        has_header=True,
        encoding="latin1",
        infer_schema_length=0,
        schema_overrides={c: pl.Utf8 for c in header},
        ignore_errors=False,
        truncate_ragged_lines=True,
        quote_char=None,
    )

    idx_dsc = descobrir_idx_dsc(header)

    if idx_dsc is not None:
        col_dsc = header[idx_dsc]
        df = df.with_columns(
            pl.col(col_dsc)
            .str.replace_all(PIPE_PLACEHOLDER, "|")
            .alias(col_dsc)
        )

    nome_arquivo = path_txt.name
    divisao_arquivo = extrair_divisao_arquivo(nome_arquivo)

    div_df = carregar_divisoes_df()
    cfop_df = carregar_cfop_df()

    if "DTENTR" in df.columns:
        expr_periodo = (
            pl.when(pl.col("DTENTR").is_not_null() & (pl.col("DTENTR").str.len_chars() >= 10))
            .then(pl.col("DTENTR").str.slice(6, 4) + pl.lit("_") + pl.col("DTENTR").str.slice(3, 2))
            .otherwise(pl.lit(""))
            .alias("Período")
        )
    elif "INFSM_DTEM" in df.columns:
        expr_periodo = (
            pl.when(pl.col("INFSM_DTEM").is_not_null() & (pl.col("INFSM_DTEM").str.len_chars() >= 10))
            .then(pl.col("INFSM_DTEM").str.slice(6, 4) + pl.lit("_") + pl.col("INFSM_DTEM").str.slice(3, 2))
            .otherwise(pl.lit(""))
            .alias("Período")
        )
    else:
        expr_periodo = pl.lit("").alias("Período")

    df = df.with_columns([
        pl.lit("Fiscal").alias("Fonte"),
        pl.lit(nome_arquivo).alias("Nome do Arquivo"),
        pl.lit(divisao_arquivo).alias("DivArquivo"),
        expr_periodo,
    ])

    df = df.join(
        div_df,
        left_on="FILIAL",
        right_on="Local de Negócios",
        how="left"
    )

    df = df.with_columns([
        pl.when(pl.col("FILIAL").cast(pl.Utf8).str.strip_chars() == "3007")
        .then(pl.lit("31SC"))
        .when(pl.col("DivArquivo").str.to_uppercase() == "85MN")
        .then(pl.lit("85MG"))
        .when(pl.col("DivArquivo") == "")
        .then(pl.col("Divisão_DePara").fill_null(""))
        .when(pl.col("Divisão_DePara").fill_null("").str.to_uppercase() == pl.col("DivArquivo").str.to_uppercase())
        .then(pl.col("DivArquivo"))
        .otherwise(pl.col("DivArquivo"))
        .alias("Divisão")
    ])


    df = df.with_columns(
        pl.col("CFOP_COD").cast(pl.Utf8).str.strip_chars().alias("CFOP_COD")
    )

    df = df.join(
        cfop_df,
        left_on="CFOP_COD",
        right_on="CFOP",
        how="left"
    )

    df = df.with_columns([
        pl.col(c).str.strip_chars().alias(c)
        for c in df.columns
        if df.schema[c] == pl.Utf8
    ])

    ordem = montar_ordem_final(df.columns)
    df = df.select(ordem)

    df = df.with_columns(pl.lit(path_txt.name).alias("__ordem__"))

    df.write_parquet(
        shard_out,
        compression=COMPRESSION,
        row_group_size=ROW_GROUP
    )

    try:
        txt_limpo.unlink(missing_ok=True)
    except Exception:
        pass

    return {"arquivo": path_txt.name, "linhas": df.height, "ok": True, "shard": str(shard_out)}


def consolidar_final(base_dir_str, progress_callback=None):
    t0 = time.time()

    base_dir = Path(base_dir_str)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    parquet_final = CACHE_PARQUET
    tmp_dir = CACHE_DIR / TMP_NOME

    arquivos = sorted(base_dir.rglob("*.txt"))
    if not arquivos:
        raise FileNotFoundError("Nenhum TXT encontrado na pasta selecionada.")

    tipo_movimento = detectar_tipo_movimento(arquivos)

    tmp_dir.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("preparando", 0, len(arquivos), "Preparando processamento...")

    shard_paths = []
    total_linhas = 0
    total_arquivos = len(arquivos)

    args = [(str(a), str(tmp_dir)) for a in arquivos]

    for i, arg in enumerate(args, start=1):
        res = processar_arquivo(arg)

        if progress_callback:
            progress_callback(
                "processando_txt",
                i,
                total_arquivos,
                res.get("arquivo", "")
            )

        if not res["ok"]:
            continue

        shard_paths.append(res["shard"])
        total_linhas += res["linhas"]

    if not shard_paths:
        raise ValueError("Nenhum shard gerado.")

    if progress_callback:
        progress_callback("consolidando", 1, 1, "Consolidando shards...")

    df = (
        pl.scan_parquet(shard_paths)
        .with_row_index("Índice", offset=1)
        .collect()
    )

    cols = [c for c in df.columns if c not in {"Índice", "__ordem__"}]
    ordem_final = ["Índice"] + cols
    df = df.select(ordem_final)

    df.write_parquet(
        parquet_final,
        compression=COMPRESSION,
        row_group_size=ROW_GROUP
    )

    if progress_callback:
        progress_callback("finalizado", 1, 1, parquet_final.name)

    return parquet_final, df.height, round(time.time() - t0, 2), tipo_movimento