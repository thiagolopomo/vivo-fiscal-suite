#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import json
import time
from pathlib import Path
from collections import Counter
import polars as pl

CACHE_DIR = Path.home() / "AppData" / "Local" / "ValidadorVIVO"
CACHE_ZTMM_META = CACHE_DIR / "ztmm_meta.json"
COMPRESSION = "zstd"


def extrair_tabela_de_txt(caminho_txt):
    with open(caminho_txt, "r", encoding="latin-1", errors="ignore") as f:
        linhas = [ln.rstrip("\r\n") for ln in f]

    header_idx = None
    for i, linha in enumerate(linhas):
        if (
            linha.startswith("|")
            and "Empresa" in linha
            and "Centro" in linha
            and "Quantidade" in linha
        ):
            header_idx = i
            break

    if header_idx is None:
        return None

    header_raw = [c.strip() for c in linhas[header_idx].strip().strip("|").split("|")]
    dados = []

    for linha in linhas[header_idx + 1:]:
        s = linha.strip()
        if not s:
            continue
        if set(s) <= set("-|"):
            continue
        if not linha.startswith("|"):
            continue
        cols = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(cols) < len(header_raw):
            cols += [""] * (len(header_raw) - len(cols))
        elif len(cols) > len(header_raw):
            cols = cols[:len(header_raw)]
        dados.append(cols)

    if not dados:
        return None

    return header_raw, dados


def ajustar_header_duplicados(header):
    contagem_total = Counter(header)
    contagem_visto = {}
    novo_header = []

    for nome in header:
        contagem_visto[nome] = contagem_visto.get(nome, 0) + 1
        idx = contagem_visto[nome]

        if nome == "Valor ICMS":
            novo_header.append(f"Valor ICMS_{idx}")
            continue

        if contagem_total[nome] == 1:
            novo_header.append(nome)
        else:
            novo_header.append(f"{nome}_{idx}")

    return novo_header


def extrair_divisao(caminho_txt):
    nome_arquivo = Path(caminho_txt).name.upper()
    if nome_arquivo.startswith("PTV"):
        return "29SP"

    stem = Path(caminho_txt).stem.upper()
    m = re.match(r"^(\d{2}[A-Z]{2})(?:_|$)", stem)
    if m:
        return m.group(1)

    return ""


def consolidar_ztmm(pasta_txts, progress_callback=None):
    t0 = time.time()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pasta_txts = Path(pasta_txts)

    arquivos_txt = []
    for root, _, files in os.walk(pasta_txts):
        root_path = Path(root)
        for nome in files:
            if nome.lower().endswith(".txt"):
                arquivos_txt.append(root_path / nome)

    arquivos_txt = sorted(arquivos_txt)

    if not arquivos_txt:
        raise FileNotFoundError("Nenhum TXT encontrado na pasta selecionada.")

    total = len(arquivos_txt)
    dfs = []

    for i, caminho_txt in enumerate(arquivos_txt, start=1):
        if progress_callback:
            progress_callback("processando_txt", i, total, caminho_txt.name)

        resultado = extrair_tabela_de_txt(caminho_txt)
        if resultado is None:
            continue

        header_raw, linhas = resultado
        header = ajustar_header_duplicados(header_raw)
        divisao = extrair_divisao(caminho_txt)

        header_com_div = header + ["Divisão"]
        linhas_com_div = [linha + [divisao] for linha in linhas]

        if not linhas_com_div:
            continue

        df = pl.DataFrame(linhas_com_div, schema=header_com_div, orient="row")
        dfs.append(df)

    if not dfs:
        raise ValueError("Nenhum TXT com dados válidos encontrado.")

    if progress_callback:
        progress_callback("consolidando", 1, 1, "Concatenando DataFrames...")

    df_final = pl.concat(dfs, how="vertical_relaxed")
    df_final = df_final.with_columns([pl.all().cast(pl.Utf8)])

    divisoes = sorted(set(
        str(x).strip() for x in df_final["Divisão"].to_list()
        if str(x).strip()
    ))

    parquet_path = CACHE_DIR / "ZTMM_Consolidado.parquet"
    df_final.write_parquet(str(parquet_path), compression=COMPRESSION)

    meta = {
        "parquet_path": str(parquet_path),
        "total_linhas": df_final.height,
        "divisoes": divisoes,
        "pasta_origem": str(pasta_txts),
        "data_processamento": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tempo_total": round(time.time() - t0, 2),
    }
    with open(CACHE_ZTMM_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if progress_callback:
        progress_callback("finalizado", 1, 1, parquet_path.name)

    return str(parquet_path), df_final.height, divisoes


def carregar_meta_ztmm():
    if not CACHE_ZTMM_META.exists():
        return None
    try:
        with open(CACHE_ZTMM_META, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def listar_divisoes_ztmm(parquet_path):
    try:
        df = (
            pl.scan_parquet(str(parquet_path))
            .select(pl.col("Divisão").cast(pl.Utf8).fill_null("").str.strip_chars())
            .unique()
            .collect()
        )
        vals = [x for x in df["Divisão"].to_list() if str(x).strip()]
        return sorted(set(vals))
    except Exception:
        return []


def exportar_ztmm_por_divisao(parquet_path, divisoes, pasta_destino, progress_callback=None):
    parquet_path = str(parquet_path)
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("exportando", 0, 1, "Lendo parquet ZTMM...")

    df = pl.read_parquet(parquet_path)

    if divisoes:
        divisoes_upper = [d.strip().upper() for d in divisoes]
        df = df.filter(
            pl.col("Divisão").cast(pl.Utf8).fill_null("").str.strip_chars().str.to_uppercase().is_in(divisoes_upper)
        )

    if df.height == 0:
        raise ValueError("Nenhuma linha encontrada para as divisões selecionadas.")

    divs_txt = "_".join(sorted(divisoes)) if divisoes else "TODAS"
    nome_csv = f"ZTMM_{divs_txt}.csv"
    out_csv = pasta_destino / nome_csv

    if progress_callback:
        progress_callback("exportando", 1, 2, f"Gerando {nome_csv}...")

    df = df.with_columns([
        pl.col(c).str.strip_chars().alias(c)
        for c in df.columns
        if df.schema[c] == pl.Utf8
    ])

    df.write_csv(
        str(out_csv),
        separator=";",
        null_value="",
        include_bom=True,
    )

    if progress_callback:
        progress_callback("finalizado", 2, 2, f"Exportado: {nome_csv} ({df.height:,} linhas)")

    return str(out_csv)
