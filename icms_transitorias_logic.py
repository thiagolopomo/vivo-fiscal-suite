#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Consolidação dos razões de ICMS Transitórias e validação contra Balancete.

Pipeline:
1. `consolidar_razoes(pasta)`: lê todos os TXTs (formato pipe-separated do SAP),
   extrai a Conta do nome do arquivo, parseia o conteúdo e gera um parquet
   consolidado em cache.
2. `validar_contra_balancete(balancete)`: compara o "Montante Razão" agregado
   por Conta no parquet consolidado com o "Desvio Absoluto" da coluna "Textos"
   do balancete. Indica diferenças e onde elas estão.
"""
import io
import os
import re
import gc
import json
import time
import shutil
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import polars as pl


CACHE_DIR = Path.home() / "AppData" / "Local" / "ValidadorVIVO"
CACHE_TRANSIT_PARQUET = CACHE_DIR / "icms_transitorias_consolidado.parquet"
CACHE_TRANSIT_META = CACHE_DIR / "icms_transitorias_meta.json"
CACHE_TRANSIT_VALID = CACHE_DIR / "icms_transitorias_validacao.parquet"
COMPRESSION = "zstd"


# =====================================================================
# Helpers de parsing
# =====================================================================

def _conta_do_nome(caminho_txt):
    """A Conta do razão é o próprio stem do arquivo (ex.: '11221211.TXT' -> '11221211')."""
    return Path(caminho_txt).stem.strip()


def _parse_razao_txt(caminho_txt, parte_path):
    """Lê um TXT de razão SAP e grava como parquet em parte_path.

    O formato é igual ao ZTMM: uma tabela ascii com `|` como separador,
    incluindo "colunas vazias" (`| |`) entre alguns campos. Filtramos as
    linhas separadoras e o lixo do cabeçalho do relatório, e usamos o
    parser nativo do polars (rápido, libera GIL, suporta múltiplas threads
    quando rodando em paralelo).

    Retorna (parte_path, height) ou None se vazio/inválido.
    """
    with open(caminho_txt, "rb") as f:
        raw = f.read()

    text = raw.decode("latin-1", errors="ignore")
    del raw
    lines = text.splitlines()
    del text

    # Encontra a linha do header da tabela. Procuramos por uma linha que
    # comece com `|` e contenha as palavras-chave que sempre aparecem.
    header_idx = None
    for i, linha in enumerate(lines):
        if (
            linha.startswith("|")
            and "Conta" in linha
            and "Montante" in linha
        ):
            header_idx = i
            break

    if header_idx is None:
        return None

    header_raw = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    # Tira colunas vazias do header e renomeia duplicadas mantendo a ordem
    # original. As colunas "vazias" (resultado de `| |`) viram placeholders
    # tipo COL_EMPTY_N pra preservar o alinhamento na hora do split.
    header = []
    seen = {}
    for i, name in enumerate(header_raw):
        nome = name if name else f"_VAZIO_{i}"
        if nome in seen:
            seen[nome] += 1
            nome = f"{nome}_{seen[nome]}"
        else:
            seen[nome] = 1
        header.append(nome)

    # Coleta as linhas de dados, filtrando separadores (---|---|---) e lixo.
    data_buf = []
    for linha in lines[header_idx + 1:]:
        if not linha.startswith("|"):
            continue
        s = linha.strip()
        if not s or not s.strip("-|"):
            continue
        data_buf.append(linha.strip().strip("|"))

    del lines

    if not data_buf:
        return None

    csv_bytes = "\n".join(data_buf).encode("utf-8", errors="replace")
    del data_buf

    schema = {name: pl.Utf8 for name in header}

    try:
        df = pl.read_csv(
            io.BytesIO(csv_bytes),
            separator="|",
            has_header=False,
            schema=schema,
            truncate_ragged_lines=True,
            quote_char=None,
        )
    except Exception:
        df = pl.read_csv(
            io.BytesIO(csv_bytes),
            separator="|",
            has_header=False,
            new_columns=header,
            infer_schema_length=0,
            truncate_ragged_lines=True,
            quote_char=None,
        )

    del csv_bytes

    # Remove whitespace de todas as Utf8 (vetorizado, nativo)
    df = df.with_columns([pl.col(c).str.strip_chars() for c in df.columns])

    # Move o sinal negativo do FINAL para o INÍCIO no(s) campo(s) "Montante".
    # O SAP exporta "299,22-" mas o Excel só reconhece como número se vier
    # como "-299,22". A coluna fica como string (sem conversão de tipo) — só
    # reposiciona o sinal, mantendo a vírgula decimal BR.
    for c in df.columns:
        if "Montante" in c:
            df = df.with_columns(
                pl.when(pl.col(c).str.ends_with("-"))
                .then(pl.lit("-") + pl.col(c).str.slice(0, pl.col(c).str.len_chars() - 1))
                .otherwise(pl.col(c))
                .alias(c)
            )

    # Filtra linhas de SUBTOTAL/ACUMULADO do SAP. Elas aparecem no rodapé
    # de cada conta com `Tipo` E `CL` vazios e o "Montante Razão" sendo o
    # TOTAL da conta — se forem deixadas, a soma duplica/triplica o valor
    # real (no caso típico, total da conta aparece 2x → soma vira 3× o real).
    if "Tipo" in df.columns and "CL" in df.columns:
        df = df.filter(
            (pl.col("Tipo").fill_null("").str.strip_chars() != "")
            | (pl.col("CL").fill_null("").str.strip_chars() != "")
        )

    # Reforça a Conta usando o nome do arquivo (mais confiável e fica bem
    # quando alguma linha tem a coluna em branco).
    conta_arquivo = _conta_do_nome(caminho_txt)
    if "Conta" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("Conta").fill_null("") == "")
            .then(pl.lit(conta_arquivo))
            .otherwise(pl.col("Conta"))
            .alias("Conta")
        )
    else:
        df = df.with_columns(pl.lit(conta_arquivo).alias("Conta"))

    # Filtra HEADERS REPETIDOS no meio do TXT. O SAP imprime o header de
    # coluna a cada "página" do relatório (ex.: "Conta" / "Tipo" / "CL"
    # como texto literal nas posições dos respectivos valores). Como Tipo
    # e CL são preenchidos com o texto literal ("Tipo", "CL"), o filtro de
    # subtotal acima não pega. O critério definitivo é manter só linhas
    # onde a Conta é numérica (lançamentos reais sempre são).
    df = df.filter(
        pl.col("Conta").fill_null("").str.strip_chars().str.contains(r"^\d+$", literal=False)
    )

    df = df.with_columns(pl.lit(Path(caminho_txt).name).alias("Arquivo"))

    df.write_parquet(str(parte_path), compression=COMPRESSION)
    height = df.height
    del df
    return parte_path, height


# =====================================================================
# Consolidação
# =====================================================================

def consolidar_razoes(pasta_txts, progress_callback=None):
    """Consolida todos os TXTs de razão da pasta em um único parquet.

    Mesma estratégia já validada no ZTMM:
    - 1 parquet temporário por TXT (libera RAM entre arquivos)
    - parsing paralelizado com ThreadPoolExecutor (cap 4 workers)
    - concat final em streaming via scan_parquet + sink_parquet

    Retorna (parquet_path, total_linhas, total_contas).
    """
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
        raise FileNotFoundError("Nenhum TXT de razão encontrado na pasta selecionada.")

    total = len(arquivos_txt)
    tmp_dir = Path(tempfile.mkdtemp(prefix="transit_parts_", dir=str(CACHE_DIR)))
    temp_parts = []

    max_workers = max(1, min(4, os.cpu_count() or 2))

    def _worker(args):
        idx, caminho = args
        parte_path = tmp_dir / f"parte_{idx:06d}.parquet"
        try:
            resultado = _parse_razao_txt(caminho, parte_path)
        except Exception as exc:
            return ("erro", idx, caminho.name, repr(exc))
        if resultado is None:
            return ("vazio", idx, caminho.name, None)
        return ("ok", idx, caminho.name, resultado[0])

    try:
        args_list = list(enumerate(arquivos_txt, start=1))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_worker, a) for a in args_list]
            processados = 0
            for fut in as_completed(futures):
                status, idx, nome, payload = fut.result()
                processados += 1
                if progress_callback:
                    progress_callback("processando_txt", processados, total, nome)
                if status == "ok":
                    temp_parts.append(payload)

        if not temp_parts:
            raise ValueError("Nenhum TXT de razão com dados válidos foi encontrado.")

        temp_parts = sorted(temp_parts)

        if progress_callback:
            progress_callback("consolidando", 1, 1, "Concatenando razões...")

        parquet_path = CACHE_TRANSIT_PARQUET

        lazy_frames = [pl.scan_parquet(str(p)) for p in temp_parts]
        lf = pl.concat(lazy_frames, how="diagonal_relaxed")

        try:
            lf.sink_parquet(str(parquet_path), compression=COMPRESSION)
        except Exception:
            df_final = lf.collect(streaming=True)
            df_final.write_parquet(str(parquet_path), compression=COMPRESSION)
            del df_final
            gc.collect()

        # Conta linhas e contas únicas via lazy
        lf_final = pl.scan_parquet(str(parquet_path))
        total_linhas = int(lf_final.select(pl.len()).collect().item())

        contas_df = (
            lf_final
            .select(pl.col("Conta").cast(pl.Utf8).fill_null("").str.strip_chars())
            .unique()
            .collect()
        )
        contas = sorted(set(
            str(x).strip() for x in contas_df["Conta"].to_list()
            if str(x).strip()
        ))
        total_contas = len(contas)
        del contas_df, lf_final
        gc.collect()

        meta = {
            "parquet_path": str(parquet_path),
            "total_linhas": total_linhas,
            "total_contas": total_contas,
            "contas": contas,
            "pasta_origem": str(pasta_txts),
            "data_processamento": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tempo_total": round(time.time() - t0, 2),
        }
        with open(CACHE_TRANSIT_META, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback("finalizado", 1, 1, parquet_path.name)

        return str(parquet_path), total_linhas, total_contas
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def carregar_meta_transitorias():
    if not CACHE_TRANSIT_META.exists():
        return None
    try:
        with open(CACHE_TRANSIT_META, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# =====================================================================
# Extração de Razões Conciliados (Chave_02 = Div_NºDoc_Tipo)
# =====================================================================

def _achar_coluna(cols, nome_alvo):
    """Encontra uma coluna ignorando case e diferenças de acentuação/espaço."""
    norm_alvo = (
        nome_alvo.lower()
        .replace("ã", "a").replace("á", "a").replace("ç", "c")
        .replace("é", "e").replace("ê", "e").replace("í", "i")
        .replace("ó", "o").replace("ô", "o").replace("ú", "u")
        .replace("º", "").replace(".", "").replace(" ", "").replace("_", "")
    )
    for c in cols:
        c_norm = (
            c.lower()
            .replace("ã", "a").replace("á", "a").replace("ç", "c")
            .replace("é", "e").replace("ê", "e").replace("í", "i")
            .replace("ó", "o").replace("ô", "o").replace("ú", "u")
            .replace("º", "").replace(".", "").replace(" ", "").replace("_", "")
        )
        if c_norm == norm_alvo:
            return c
    return None


def extrair_razoes_aa(
    parquet_path,
    destino,
    tipo_filtro="BOTH",
    progress_callback=None,
):
    """Extrai os razões CONCILIADOS por Chave_02 (Div + Nº Doc + Tipo).

    Pipeline:
      1. Filtra Tipo ∈ {WE, WL} (ou apenas um deles, conforme tipo_filtro)
      2. Cria Chave_02 = Div_NºDoc_Tipo
      3. Agrupa por Chave_02 e soma Montante Razão
      4. Mantém só linhas cujos grupos somam ZERO → marca Status AA = "Conciliado"
      5. Cria Referência AA = Referência sem o sufixo "-N" (ex.: 142246-1 → 142246)
      6. Cria Chave_01 = Div_ReferênciaAA
      7. Grava em destino (xlsx ou csv)

    tipo_filtro:
      - "WE"   : só lançamentos WE
      - "WL"   : só lançamentos WL
      - "BOTH" : ambos (default)
    """
    parquet_path = str(parquet_path)
    destino = Path(destino)

    if progress_callback:
        progress_callback("extraindo_aa", 1, 5, "Lendo razões consolidados...")

    lf = pl.scan_parquet(parquet_path)
    cols = lf.collect_schema().names()

    # Localiza as colunas necessárias (tolerante a variações de nome).
    col_div = _achar_coluna(cols, "Div")
    col_tipo = _achar_coluna(cols, "Tipo")
    col_ndoc = _achar_coluna(cols, "Nº doc.")
    col_montante = _achar_coluna(cols, "Montante Razão")
    col_ref = _achar_coluna(cols, "Referência")

    faltando = [
        nome for nome, ref in [
            ("Div", col_div), ("Tipo", col_tipo),
            ("Nº doc.", col_ndoc), ("Montante Razão", col_montante),
            ("Referência", col_ref),
        ] if ref is None
    ]
    if faltando:
        raise ValueError(
            f"Colunas obrigatórias não encontradas no parquet: {faltando}"
        )

    # Filtra os tipos pedidos
    tipo_filtro = (tipo_filtro or "BOTH").upper()
    if tipo_filtro == "WE":
        tipos = ["WE"]
        rotulo_tipo = "WE"
    elif tipo_filtro == "WL":
        tipos = ["WL"]
        rotulo_tipo = "WL"
    else:
        tipos = ["WE", "WL"]
        rotulo_tipo = "WE_WL"

    lf = lf.filter(
        pl.col(col_tipo).cast(pl.Utf8).str.strip_chars().is_in(tipos)
    )

    if progress_callback:
        progress_callback("extraindo_aa", 2, 5, "Construindo Chave_02...")

    lf = lf.with_columns([
        (
            pl.col(col_div).cast(pl.Utf8).str.strip_chars()
            + pl.lit("_")
            + pl.col(col_ndoc).cast(pl.Utf8).str.strip_chars()
            + pl.lit("_")
            + pl.col(col_tipo).cast(pl.Utf8).str.strip_chars()
        ).alias("Chave_02"),
        _expr_montante_br(col_montante).alias("__montante_num"),
    ])

    if progress_callback:
        progress_callback("extraindo_aa", 3, 5, "Conciliando por Chave_02...")

    # Soma do grupo por Chave_02 → quando = 0, é conciliação
    soma_grupo = lf.group_by("Chave_02").agg(
        pl.col("__montante_num").sum().alias("__soma_grupo")
    )
    lf = lf.join(soma_grupo, on="Chave_02", how="left")

    # Tolerância de 1 centavo para arredondamentos de float
    lf = lf.filter(pl.col("__soma_grupo").abs() < 0.005)
    lf = lf.with_columns(pl.lit("Conciliado").alias("Status AA"))

    if progress_callback:
        progress_callback(
            "extraindo_aa", 4, 5, "Gerando Referência AA e Chave_01..."
        )

    # Referência AA = Referência sem sufixo "-N" (Série) e SEM zeros à esquerda.
    # Ex.: "000860702-1" -> "860702" (sem o "-1" e sem os "000" iniciais).
    lf = lf.with_columns(
        pl.col(col_ref)
        .cast(pl.Utf8)
        .fill_null("")
        .str.strip_chars()
        .str.replace(r"-\d+$", "", literal=False)
        .str.replace(r"^0+", "", literal=False)
        .alias("Referência AA")
    )
    # Chave_01 = Div_ReferênciaAA (também sem zeros à esquerda na NF)
    lf = lf.with_columns(
        (
            pl.col(col_div).cast(pl.Utf8).str.strip_chars()
            + pl.lit("_")
            + pl.col("Referência AA")
        ).alias("Chave_01")
    )

    # Limpa colunas auxiliares e os placeholders de pipes vazios do parser
    cols_drop = ["__montante_num", "__soma_grupo"]
    cols_drop.extend([c for c in lf.collect_schema().names() if c.startswith("_VAZIO_")])
    lf = lf.drop(cols_drop)

    df = lf.collect()

    # Reordena colunas (no parquet/polars, antes de gravar — XLSB só serializa):
    #   - colunas originais na ordem natural
    #   - "Referência AA" colocada IMEDIATAMENTE depois de "Referência"
    #   - depois de TODAS as originais: Chave_01 → Chave_02 → Status AA
    derivadas = {"Referência AA", "Chave_01", "Chave_02", "Status AA"}
    originais = [c for c in df.columns if c not in derivadas]
    nova_ordem = []
    for c in originais:
        nova_ordem.append(c)
        if c == col_ref:
            nova_ordem.append("Referência AA")
    # Se "Referência" não existir, joga "Referência AA" entre as originais e
    # as chaves derivadas pra não perder a coluna.
    if "Referência AA" not in nova_ordem:
        nova_ordem.append("Referência AA")
    nova_ordem.extend(["Chave_01", "Chave_02", "Status AA"])
    df = df.select(nova_ordem)

    if df.height == 0:
        raise ValueError(
            f"Nenhum lançamento conciliado encontrado para tipo(s): {', '.join(tipos)}."
        )

    if progress_callback:
        progress_callback(
            "extraindo_aa", 5, 5, f"Gravando {df.height:,} linhas em {destino.name}..."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)
    suf = destino.suffix.lower()
    if suf == ".csv":
        df.write_csv(str(destino), separator=";", include_bom=True)
    elif suf == ".xlsb":
        # Pipeline rápido: CSV (Polars/Rust em segundos) + XLSB via Excel COM
        # (binário, ~5-10x mais rápido que XLSX via xlsxwriter para 300k+ linhas).
        # Reaproveita a função já validada no Consolidador Fiscal.
        from validar_logic import _csv_para_xlsb_rapido
        tmp_csv = destino.with_suffix(".__tmp__.csv")
        try:
            with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
                f.write("﻿")
                df.write_csv(
                    f, separator=";", include_header=True,
                    null_value="", line_terminator="\n",
                    quote_style="necessary",
                )
            _csv_para_xlsb_rapido(
                str(tmp_csv), str(destino),
                progress_callback=progress_callback,
            )
        finally:
            try:
                tmp_csv.unlink()
            except Exception:
                pass
    else:
        # Default: xlsx via xlsxwriter (mais lento — ofereça XLSB para volumes grandes).
        if suf != ".xlsx":
            destino = destino.with_suffix(".xlsx")
        try:
            df.write_excel(str(destino), autofit=False)
        except TypeError:
            df.write_excel(str(destino))

    return {
        "destino": str(destino),
        "linhas": df.height,
        "tipos": tipos,
        "rotulo_tipo": rotulo_tipo,
    }


# =====================================================================
# Validação contra Balancete
# =====================================================================

# Aceita variações comuns: vírgula como decimal, separador de milhar com `.`
# e o sinal de negativo escondido entre parênteses ou no final ("123,45-").
_NUM_BR_RE = re.compile(r"^-?\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?-?$|^-?\d+(?:,\d+)?-?$|^-?\d+(?:\.\d+)?$|^\(\s*\d+(?:[.,]\d+)?\s*\)$")


def _expr_montante_br(col):
    """Converte para Float64 detectando o formato POR LINHA:

    - Strings BR ("1.234,56", "12,91", "123,45-")  -> ponto é milhar, vírgula é decimal
    - Strings US/numéricas ("1234.56", "0", "8850829.57") -> ponto é decimal

    Isso é importante porque o balancete em xlsb chega via pyxlsb como
    floats nativos (1234.56) enquanto o razão TXT do SAP chega como string
    BR (1.234,56). Sem esse switch, eu removia o ponto do float nativo e
    multiplicava o valor por ~100.
    """
    raw = pl.col(col).cast(pl.Utf8).fill_null("").str.strip_chars()

    # negativo no final: "123,45-" / "123-" -> "-123,45" / "-123"
    raw = (
        pl.when(raw.str.ends_with("-"))
        .then(pl.lit("-") + raw.str.slice(0, raw.str.len_chars() - 1))
        .otherwise(raw)
    )

    # Caminho BR: remove pontos (milhar) e troca vírgula por ponto (decimal).
    sem_milhar_br = (
        raw.str.replace_all(r"\.", "")
           .str.replace(",", ".", literal=True)
    )

    # Caminho US/numérico: já tá no formato esperado pelo cast.
    s = pl.when(raw.str.contains(",", literal=True)).then(sem_milhar_br).otherwise(raw)
    return s.cast(pl.Float64, strict=False).fill_null(0.0)


def _ler_balancete(caminho):
    """Carrega o balancete em DataFrame, tentando xlsb/xlsx/csv.

    Retorna o DataFrame BRUTO sem header definido (todas as células como Utf8),
    para que possamos detectar a linha de header procurando por "Textos" e
    "Desvio absoluto".
    """
    caminho = Path(caminho)
    suf = caminho.suffix.lower()

    if suf == ".xlsb":
        # Lazy import: pyxlsb só é necessário para esse formato específico.
        import pandas as pd
        df_pd = pd.read_excel(caminho, engine="pyxlsb", sheet_name=0, header=None)
        df_pd = df_pd.astype(object).where(df_pd.notna(), "")
        # Converte tudo para string evitando o ".0" inúteis em ints/floats.
        def _to_str(v):
            if v == "" or v is None:
                return ""
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            return str(v)
        for c in df_pd.columns:
            df_pd[c] = df_pd[c].map(_to_str)
        return pl.from_pandas(df_pd)

    if suf in (".xlsx", ".xlsm"):
        import pandas as pd
        df_pd = pd.read_excel(caminho, sheet_name=0, header=None, dtype=str)
        df_pd = df_pd.fillna("")
        return pl.from_pandas(df_pd)

    if suf == ".csv":
        return pl.read_csv(
            caminho,
            has_header=False,
            infer_schema_length=0,
            separator=";" if _detectar_separador_csv(caminho) == ";" else ",",
            encoding="utf8-lossy",
            ignore_errors=True,
        )

    raise ValueError(f"Formato não suportado para balancete: {suf}")


def _detectar_separador_csv(caminho):
    with open(caminho, "rb") as f:
        sample = f.read(4096).decode("latin-1", errors="ignore")
    return ";" if sample.count(";") > sample.count(",") else ","


def _achar_header_balancete(df_bruto):
    """Encontra a linha do header procurando por "Textos" e "Desvio absoluto"
    na mesma linha, e retorna (linha_idx, {nome_col: idx_col}) com as colunas
    relevantes mapeadas."""
    cols = df_bruto.columns
    n_rows = df_bruto.height

    for i in range(min(n_rows, 50)):
        row = df_bruto.row(i)
        valores = [(j, str(v).strip()) for j, v in enumerate(row) if v is not None]

        idx_textos = None
        idx_desvio = None
        for j, val in valores:
            v_norm = val.lower().replace("ã", "a").replace("é", "e").replace("í", "i")
            if v_norm == "textos":
                idx_textos = j
            elif "desvio absoluto" in v_norm:
                idx_desvio = j

        if idx_textos is not None and idx_desvio is not None:
            return i, {"textos": idx_textos, "desvio_absoluto": idx_desvio}

    return None, None


def validar_contra_balancete(parquet_razoes, caminho_balancete, progress_callback=None):
    """Compara totais por Conta entre o parquet consolidado de razões e o
    balancete fornecido.

    Para o razão: agrupa por Conta e soma "Montante Razão".
    Para o balancete: localiza as colunas "Textos" (Conta) e "Desvio absoluto"
    (valor) pelo nome do header — independente da posição exata.

    Retorna um dict com:
      - df_validacao: DataFrame com Conta, Soma_Razao, Soma_Balancete, Diferenca, Status
      - total_contas, batendo, divergentes, ausentes_balancete, ausentes_razao
      - parquet_validacao: caminho do parquet salvo com a comparação
    """
    t0 = time.time()

    if progress_callback:
        progress_callback("validando", 1, 4, "Lendo razões consolidados...")

    lf_raz = pl.scan_parquet(str(parquet_razoes))

    # Encontra a coluna de Montante. Pode aparecer como "Montante Razão",
    # "Montante Razao", "Montante", etc. Pega a primeira que casar.
    cols_raz = lf_raz.collect_schema().names()
    col_montante = None
    for c in cols_raz:
        c_norm = c.lower().replace("ã", "a").replace("é", "e")
        if "montante" in c_norm:
            col_montante = c
            break
    if col_montante is None:
        raise ValueError("Coluna 'Montante Razão' não encontrada no parquet consolidado.")

    if "Conta" not in cols_raz:
        raise ValueError("Coluna 'Conta' não encontrada no parquet consolidado.")

    soma_razao = (
        lf_raz
        .select([
            pl.col("Conta").cast(pl.Utf8).fill_null("").str.strip_chars(),
            _expr_montante_br(col_montante).alias("__montante__"),
        ])
        .filter(pl.col("Conta") != "")
        # Mantém só Contas numéricas — filtra o header repetido ("Conta") e
        # subtotais/textos que possam ter escapado do parsing.
        .filter(pl.col("Conta").str.contains(r"^\d+$", literal=False))
        .group_by("Conta")
        .agg(pl.col("__montante__").sum().alias("Soma_Razao"))
        .collect()
    )

    if progress_callback:
        progress_callback("validando", 2, 4, "Lendo balancete...")

    df_bal = _ler_balancete(caminho_balancete)

    if progress_callback:
        progress_callback("validando", 3, 4, "Localizando colunas no balancete...")

    header_idx, mapa = _achar_header_balancete(df_bal)
    if header_idx is None:
        raise ValueError(
            "Não consegui localizar as colunas 'Textos' e 'Desvio absoluto' "
            "no balancete. Verifique se o arquivo está no padrão esperado."
        )

    cols_brutas = df_bal.columns
    col_textos = cols_brutas[mapa["textos"]]
    col_desvio = cols_brutas[mapa["desvio_absoluto"]]

    df_bal_dados = (
        df_bal.slice(header_idx + 1)
        .select([
            pl.col(col_textos).cast(pl.Utf8).fill_null("").str.strip_chars().alias("Conta"),
            _expr_montante_br(col_desvio).alias("Soma_Balancete"),
        ])
        .filter(pl.col("Conta") != "")
        # Conta pode vir do balancete como "11113104.0" (excel) — limpa o sufixo.
        .with_columns(
            pl.col("Conta").str.replace(r"\.0+$", "", literal=False).alias("Conta")
        )
        # Mantém apenas linhas em que a Conta é numérica (descarta totais e textos).
        .filter(pl.col("Conta").str.contains(r"^\d+$", literal=False))
        .group_by("Conta")
        .agg(pl.col("Soma_Balancete").sum())
    )

    if progress_callback:
        progress_callback("validando", 4, 4, "Cruzando razão x balancete...")

    df_join = (
        soma_razao.join(df_bal_dados, on="Conta", how="full", coalesce=True)
        .with_columns([
            pl.col("Soma_Razao").fill_null(0.0),
            pl.col("Soma_Balancete").fill_null(0.0),
        ])
        .with_columns(
            (pl.col("Soma_Razao") - pl.col("Soma_Balancete")).alias("Diferenca")
        )
        .with_columns(
            pl.when(pl.col("Diferenca").abs() < 0.005)
            .then(pl.lit("OK"))
            .when((pl.col("Soma_Razao") == 0) & (pl.col("Soma_Balancete") != 0))
            .then(pl.lit("Só no balancete"))
            .when((pl.col("Soma_Razao") != 0) & (pl.col("Soma_Balancete") == 0))
            .then(pl.lit("Só no razão"))
            .otherwise(pl.lit("Divergente"))
            .alias("Status")
        )
        .sort([pl.col("Status") == "OK", "Conta"])  # divergentes primeiro
    )

    df_join.write_parquet(str(CACHE_TRANSIT_VALID), compression=COMPRESSION)

    total_contas = df_join.height
    batendo = int((df_join["Status"] == "OK").sum())
    divergentes = int((df_join["Status"] == "Divergente").sum())
    ausentes_balancete = int((df_join["Status"] == "Só no razão").sum())
    ausentes_razao = int((df_join["Status"] == "Só no balancete").sum())

    return {
        "df_validacao": df_join,
        "parquet_validacao": str(CACHE_TRANSIT_VALID),
        "total_contas": total_contas,
        "batendo": batendo,
        "divergentes": divergentes,
        "ausentes_balancete": ausentes_balancete,
        "ausentes_razao": ausentes_razao,
        "tempo_total": round(time.time() - t0, 2),
    }


# =====================================================================
# Extração Transitórias do Livro Fiscal (Entradas / Saídas)
# =====================================================================

# CFOPs transitórios (definidos pelo time fiscal)
CFOP_TRANSIT_ENTRADA = [
    "2552", "1152", "2152", "1409", "2409",
    "1602", "1605", "1601", "2154", "2557",
]
CFOP_TRANSIT_SAIDA = [
    "6552", "5552", "6557", "5557", "5152",
    "6152", "5409", "6409", "5602", "5605",
]

# Aliases de coluna: cobre os nomes técnicos do parquet/Andersen e os nomes
# renomeados pelo "Versão Vivo" (Entrada e Saída). Tudo é resolvido por nome
# real — a ordem dentro de cada lista é "tente nessa ordem"; o primeiro que
# existir vence.
LIVRO_COL_ALIASES = {
    "indice":         ["Índice", "ÍNDICE", "INDICE", "Indice"],
    "fonte":          ["Fonte", "FONTE"],
    "periodo":        ["Período", "PERÍODO", "Periodo", "PERIODO"],
    "chave_nota":     ["CHAVE DA NOTA", "Chave Nota Fiscal", "Chave de Acesso", "MNFSM_CHV_NFE"],
    "empresa":        ["EMPRESA", "Empresa"],
    "divisao":        ["Divisão", "DIVISÃO", "Divisao", "DIVISAO"],
    "cnpj_cpf":       ["CNPJ/CPF", "CNPJ\\CPF"],
    "uf":             ["UF", "Unidade Federativa"],
    "ind_canc":       ["IND_CANC", "Indicador de Cancelamento"],
    "infem_num":      ["INFEM_NUM", "INFSM_NUM", "Nota Fiscal"],
    "dtemis":         ["DTEMIS", "INFSM_DTEM", "Emissão", "Data Emissão"],
    "dtentr":         ["DTENTR", "Entrada"],
    "cfop_cod":       ["CFOP_COD", "CFOP"],
    "val_ipi":        ["VAL_IPI", "INFSM_VAL_IPI", "Valor do IPI", "Vr. do IPI"],
    "val_icms":       ["VAL_ICMS", "INFSM_VAL_ICMS", "Valor do ICMS", "Vr. de ICMS"],
    "val_subst_icms": ["VALSUBST_ICMS", "INFSM_VALSUBST_ICMS",
                       "Valor Subst. ICMS", "Vr. do ICMS por Substituto"],
    "material":       ["MATE_COD", "Material"],
    "dsc":            ["DSC", "INFSM_DSC", "Descrição Complementar", "Descrição"],
    "ind_mov":        ["IND_MOV", "Indicador de Movimento"],
    "id_origem":      ["ID_ORIGEM", "ID Origem"],
}

# Ordem final de saída (nomes EXATOS pedidos pelo usuário) — schema da
# extração de ENTRADAS Transitórias. Cada par é (nome_no_output,
# chave_canonica_no_alias_dict). chave_canon=None ⇒ derivada.
LIVRO_OUTPUT_COLS_ENTRADA = [
    ("ÍNDICE",           "indice"),
    ("FONTE",            "fonte"),
    ("PERÍODO",          "periodo"),
    ("CHAVE DA NOTA AA", None),       # derivada
    ("EMPRESA",          "empresa"),
    ("DIVISÃO",          "divisao"),
    ("CNPJ/CPF",         "cnpj_cpf"),
    ("UF",               "uf"),
    ("IND CANC",         "ind_canc"),
    ("INFEM_NUM",        "infem_num"),
    ("DTEMISS",          "dtemis"),
    ("DTENTR",           "dtentr"),
    ("CFOP_COD",         "cfop_cod"),
    ("VAL_IPI",          "val_ipi"),
    ("VAL_ICMS",         "val_icms"),
    ("VAL_SUBST_ICMS",   "val_subst_icms"),
    ("MATE_COD",         "material"),
    ("DSC",              "dsc"),
    ("IND_MOV",          "ind_mov"),
    ("ID ORIGEM",        "id_origem"),
    ("Chave_01",         None),       # derivada (Divisão_INFEM_NUM)
]

# Schema da extração de SAÍDAS Transitórias — preserva os nomes ORIGINAIS
# do livro de saída (INFSM_*, MNFSM_*) sem renomear. Pega a mesma fonte de
# dados via aliases, mas o output mantém o vocabulário do livro.
# Sem DTENTR (não existe em saída — operação não tem entrada de mercadoria)
# e sem IND_MOV (só Entrada tem).
LIVRO_OUTPUT_COLS_SAIDA = [
    ("ÍNDICE",                "indice"),
    ("FONTE",                 "fonte"),
    ("PERÍODO",               "periodo"),
    ("CHAVE DA NOTA AA",      None),       # derivada
    ("EMPRESA",               "empresa"),
    ("DIVISÃO",               "divisao"),
    ("CNPJ/CPF",              "cnpj_cpf"),
    ("UF",                    "uf"),
    ("IND_CANC",              "ind_canc"),
    ("INFSM_NUM",             "infem_num"),    # nome original do livro de Saída
    ("INFSM_DTEM",            "dtemis"),       # nome original do livro de Saída
    ("CFOP_COD",              "cfop_cod"),
    ("INFSM_VAL_IPI",         "val_ipi"),
    ("INFSM_VAL_ICMS",        "val_icms"),
    ("INFSM_VALSUBST_ICMS",   "val_subst_icms"),
    ("MATE_COD",              "material"),
    ("INFSM_DSC",             "dsc"),
    ("ID_ORIGEM",             "id_origem"),
    ("Chave_01",              None),       # derivada (Divisão_INFSM_NUM)
]

# Compat: nome antigo (qualquer código externo que ainda use)
LIVRO_OUTPUT_COLS = LIVRO_OUTPUT_COLS_ENTRADA


_LIVRO_MARKERS = {
    "CFOP", "INFEM_NUM", "INFSM_NUM", "NOTA FISCAL", "CFOP_COD",
    "DIVISÃO", "DIVISAO", "EMPRESA", "DTEMIS", "DTENTR",
    "VAL_ICMS", "INFSM_VAL_ICMS", "VALOR DO ICMS", "CHAVE DA NOTA",
    "CHAVE NOTA FISCAL", "ID ORIGEM", "ID_ORIGEM",
}


def _score_linha_header(valores):
    """Pontua uma linha pela quantidade de marker columns que aparecem.
    Aceita lista de strings (ou converte do que vier)."""
    cols_upper = []
    for v in valores:
        s = str(v).strip().upper() if v is not None else ""
        if s and not s.startswith("UNNAMED"):
            cols_upper.append(s)
    score = sum(1 for m in _LIVRO_MARKERS if any(m in c for c in cols_upper))
    return score, len(cols_upper)


def detectar_tipo_livro(caminho):
    """Detecta se o livro fiscal é de Entrada ou Saída.

    Estratégia em duas camadas:
      1. Nome do arquivo (instantâneo — a maioria dos exports do app
         ("Versão Vivo_Entradas_*", "Versão Completa Andersen_Saídas_*")
         já carrega o tipo no nome).
      2. Peek nas colunas (fallback) — Saída tem prefixo INFSM_ /
         MNFSM_CHV_NFE; Entrada tem DTENTR / INFEM_NUM.

    Retorna 'ENTRADA', 'SAIDA' ou None se inconclusivo.
    """
    caminho = Path(caminho)

    # --- Camada 1: nome do arquivo ---
    nome = caminho.stem.lower()
    nome_norm = (
        nome.replace("í", "i").replace("ã", "a")
            .replace("á", "a").replace("é", "e").replace("ó", "o")
    )
    if "saida" in nome_norm:
        return "SAIDA"
    if "entrada" in nome_norm:
        return "ENTRADA"

    # --- Camada 2: peek nas colunas ---
    suf = caminho.suffix.lower()
    cols = []
    try:
        if suf == ".parquet":
            cols = list(pl.scan_parquet(str(caminho)).collect_schema().names())
        elif suf in (".xlsb", ".xlsx", ".xlsm"):
            import pandas as pd
            engine = "calamine" if suf == ".xlsb" else None
            try:
                sheet, header_row = _achar_sheet_e_header(caminho, engine=engine)
                head = pd.read_excel(
                    caminho, engine=engine, sheet_name=sheet,
                    header=header_row, nrows=2, dtype=object,
                )
            except Exception:
                fallback = "pyxlsb" if suf == ".xlsb" else None
                sheet, header_row = _achar_sheet_e_header(caminho, engine=fallback)
                head = pd.read_excel(
                    caminho, engine=fallback, sheet_name=sheet,
                    header=header_row, nrows=2, dtype=object,
                )
            cols = list(head.columns)
        elif suf == ".csv":
            sep = _detectar_separador_csv(caminho)
            df = pl.read_csv(
                str(caminho), n_rows=1, separator=sep,
                infer_schema_length=0, has_header=True,
                encoding="utf8-lossy", ignore_errors=True,
            )
            cols = df.columns
    except Exception:
        return None

    cols_upper = [str(c).upper() for c in cols]

    # Markers fortes de SAÍDA: prefixo INFSM_ (vivo de saída),
    # MNFSM_CHV_NFE (chave de NFe de saída), nomes Vivo renomeados.
    saida_markers = ("INFSM_", "MNFSM_CHV_NFE", "VR. DE ICMS", "VR. DO IPI", "DATA EMISSÃO")
    # Markers fortes de ENTRADA: DTENTR (data de entrada), INFEM_NUM (Nota
    # Fiscal de entrada), nomes Vivo renomeados.
    entrada_markers = ("DTENTR", "INFEM_NUM", "VALOR DO ICMS", " ENTRADA")

    n_saida = sum(1 for c in cols_upper if any(m in c for m in saida_markers))
    n_entrada = sum(1 for c in cols_upper if any(m in c for m in entrada_markers))

    if n_saida > n_entrada:
        return "SAIDA"
    if n_entrada > n_saida:
        return "ENTRADA"
    return None


def _achar_sheet_e_header(caminho, engine, max_rows_scan=15):
    """Identifica (sheet_name, header_row_index) da planilha de dados do
    livro fiscal. Resolve dois problemas comuns:

      1. Workbook tem múltiplas sheets (uma de pivot/resumo + a de dados).
      2. A sheet de dados pode ter linhas vazias antes do header (header
         começa na linha 1 ou 2 em vez da 0).

    Estratégia: varre cada sheet, lê as primeiras N linhas SEM cabeçalho,
    e pontua cada linha pelo número de colunas-marca presentes (CFOP,
    EMPRESA, INFEM_NUM, etc.). A linha com maior score vira o header da
    sheet vencedora.

    Devolve (sheet_name, header_row_idx). Em último caso, (sheet[0], 0).
    """
    import pandas as pd

    try:
        xls = pd.ExcelFile(caminho, engine=engine)
    except Exception:
        return 0, 0

    melhor = (xls.sheet_names[0], 0, -1, 0)  # (sheet, header_row, score, n_cols)
    for s in xls.sheet_names:
        try:
            head = pd.read_excel(
                xls, sheet_name=s, header=None,
                nrows=max_rows_scan, dtype=object,
            ).fillna("")
        except Exception:
            continue
        for r in range(min(max_rows_scan, len(head))):
            valores = head.iloc[r].tolist()
            score, n_cols = _score_linha_header(valores)
            if (score, n_cols) > (melhor[2], melhor[3]):
                melhor = (s, r, score, n_cols)

    return melhor[0], melhor[1]


def _ler_xlsx_calamine_resiliente(caminho, sheet, header_row, cols_pedidas, max_tentativas=10):
    """Tenta `pl.read_excel(columns=cols_pedidas)`. Se polars/calamine
    reclamar de coluna ausente (ex.: "column with name 'X' not found"),
    remove ela da lista e tenta de novo. Retorna o DataFrame ou None se
    não conseguiu após N tentativas.

    Isso protege a projeção contra pequenas variações entre arquivos
    (ex.: IND_MOV existe no Entrada mas não no Saída) — em vez de cair
    pra leitura completa, faz o ajuste fino e mantém o ganho de memória.
    """
    import re

    cols = list(cols_pedidas)
    for _ in range(max_tentativas):
        try:
            return pl.read_excel(
                caminho,
                sheet_name=sheet,
                engine="calamine",
                read_options={"header_row": header_row},
                columns=cols,
                infer_schema_length=0,
            )
        except Exception as e:
            msg = str(e)
            # polars/calamine: 'column with name "X" not found'
            m = re.search(r'column with name "([^"]+)" not found', msg)
            if m and m.group(1) in cols:
                cols.remove(m.group(1))
                if cols:
                    continue
            return None
    return None


def _ler_livro_xlsb_calamine_direto(caminho):
    """Lê xlsb/xlsx via python_calamine e projeta APENAS as colunas que
    a aba ICMS Transitórias usa (LIVRO_COL_ALIASES).

    Por que: `pl.read_excel` aloca em Arrow todas as 146 colunas mesmo
    quando só vamos usar 20 — isso custa ~19s extra. Indo via calamine
    direto, lemos as 146 colunas como list[list] em Python (~8-15s) e
    montamos o polars DataFrame só com as colunas necessárias.

    Se a detecção de aliases não conseguir mapear nada (formato muito
    diferente), retorna o livro completo — chamador pode fazer fallback.
    """
    from python_calamine import CalamineWorkbook

    caminho = Path(caminho)
    wb = CalamineWorkbook.from_path(str(caminho))

    # Escolhe a sheet pra ler — usa só METADADOS (instantâneo), sem peek de
    # dados (que custaria ~12s por sheet). Ordem de prioridade:
    #   1) "Dados" se existir (convenção dos exports)
    #   2) Sheet com maior total_height (sheets de pivot/resumo são pequenas)
    melhor_sheet = None
    for s in wb.sheet_names:
        if s.strip().lower() == "dados":
            melhor_sheet = s
            break
    if melhor_sheet is None:
        melhor_sheet = max(
            wb.sheet_names,
            key=lambda s: wb.get_sheet_by_name(s).total_height,
        )

    sheet = wb.get_sheet_by_name(melhor_sheet)
    all_rows = sheet.to_python()

    # Encontra a linha do header dentro da sheet
    header_idx = 0
    for i, row in enumerate(all_rows[:15]):
        cells = [str(c).strip() if c is not None else "" for c in row]
        score = sum(
            1 for m in _LIVRO_MARKERS
            if any(m in c.upper() for c in cells if c)
        )
        if score >= 3:
            header_idx = i
            break

    header = [
        str(c).strip() if c is not None and str(c).strip() else f"_C{i}_"
        for i, c in enumerate(all_rows[header_idx])
    ]
    data_rows = all_rows[header_idx + 1:]

    # Resolve aliases — quais colunas reais correspondem ao que precisamos
    resolvido = _resolver_aliases(header, LIVRO_COL_ALIASES)
    indices_uteis = {
        real: header.index(real)
        for _, real in resolvido.items()
        if real and real in header
    }

    # Helper pra converter cada célula em string preservando inteiros
    def _to_str(v):
        if v is None:
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    if indices_uteis:
        # Modo otimizado: monta polars só com as colunas necessárias
        out = {
            nome: [_to_str(r[idx]) for r in data_rows]
            for nome, idx in indices_uteis.items()
        }
    else:
        # Fallback: trouxe todas (quando o arquivo não casa com os aliases
        # conhecidos — formato exótico)
        out = {
            h: [_to_str(r[i]) for r in data_rows]
            for i, h in enumerate(header)
        }

    df = pl.from_dict(out)
    return df.with_columns([pl.col(c).cast(pl.Utf8) for c in df.columns])


def _ler_livro_fiscal(caminho):
    """Carrega o livro fiscal de qualquer formato (parquet/xlsb/xlsx/csv).

    Para xlsb/xlsx com múltiplas sheets, escolhe automaticamente a planilha
    que contém os dados reais (com base nas colunas-marca como CFOP_COD,
    INFEM_NUM, Divisão, etc.). Isso evita ler por engano uma planilha de
    pivot/resumo que tenha sido salva antes da planilha de dados.

    Tudo é convertido para Utf8 pra preservar zeros à esquerda, vírgulas
    decimais e formato BR. A primeira linha é o cabeçalho.
    """
    caminho = Path(caminho)
    suf = caminho.suffix.lower()

    if suf == ".parquet":
        df = pl.read_parquet(str(caminho))
        return df.with_columns([pl.col(c).cast(pl.Utf8) for c in df.columns])

    if suf in (".xlsb", ".xlsx", ".xlsm"):
        # pl.read_excel com calamine (Rust). A grande otimização aqui é a
        # PROJEÇÃO de colunas hardcoded por tipo de arquivo (Andersen/Vivo
        # × Entrada/Saída). Em vez de carregar 116-146 colunas em Arrow
        # (~7-8 GB pra Saídas com 1M linhas → OOM), só pedimos as ~20 que
        # a aba Transitórias usa (~1.5 GB). Não há peek caro: a lista vem
        # do filename. Se uma das colunas listadas não existir no arquivo,
        # o fallback resiliente abaixo remove e tenta de novo.
        sheet, header_row = _achar_sheet_e_header(
            caminho, engine="calamine" if suf == ".xlsb" else None
        )
        cols_projetar = _cols_projecao_pra_arquivo(caminho)

        # 1ª tentativa: projetada (low memory) — com auto-correção
        # de colunas ausentes
        if cols_projetar:
            df = _ler_xlsx_calamine_resiliente(
                caminho, sheet, header_row, list(cols_projetar)
            )
            if df is not None:
                return df.with_columns(
                    [pl.col(c).cast(pl.Utf8).fill_null("") for c in df.columns]
                )

        # 2ª tentativa: leitura completa (mais memória mas mais flexível)
        try:
            df = pl.read_excel(
                caminho,
                sheet_name=sheet,
                engine="calamine",
                read_options={"header_row": header_row},
                infer_schema_length=0,
            )
            return df.with_columns(
                [pl.col(c).cast(pl.Utf8).fill_null("") for c in df.columns]
            )
        except Exception:
            # 3ª tentativa: pandas + pyxlsb (xlsb) ou openpyxl (xlsx)
            import pandas as pd
            fallback = "pyxlsb" if suf == ".xlsb" else None
            sheet, header_row = _achar_sheet_e_header(caminho, engine=fallback)
            df_pd = pd.read_excel(
                caminho, engine=fallback, sheet_name=sheet,
                header=header_row, dtype=object,
            ).fillna("")

            def _to_str(v):
                if v is None or v == "":
                    return ""
                if isinstance(v, float) and v.is_integer():
                    return str(int(v))
                return str(v)

            for c in df_pd.columns:
                df_pd[c] = df_pd[c].map(_to_str)
            return pl.from_pandas(df_pd)

    if suf == ".csv":
        sep = _detectar_separador_csv(caminho)
        return pl.read_csv(
            str(caminho),
            has_header=True,
            infer_schema_length=0,
            separator=sep,
            encoding="utf8-lossy",
            ignore_errors=True,
        )

    raise ValueError(
        f"Formato de livro fiscal não suportado: '{suf}'. "
        f"Use .parquet, .xlsb, .xlsx ou .csv."
    )


def _ler_livro_fiscal_com_cache(caminho):
    """Mesmo que `_ler_livro_fiscal`, mas usa cache em parquet pra acelerar
    leituras repetidas do mesmo arquivo.

    Estratégia:
      - Parquet de origem: lê direto, sem cache (já é rápido).
      - Outros formatos: na primeira leitura, faz a conversão para parquet
        em CACHE_DIR usando um fingerprint do arquivo (nome + mtime + size).
        Leituras subsequentes do mesmo arquivo (mesmo fingerprint) são
        ~instantâneas — apenas um `pl.read_parquet`.
    """
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".parquet":
        return _ler_livro_fiscal(caminho)

    try:
        st = caminho.stat()
        fingerprint = f"{caminho.stem}_{int(st.st_mtime)}_{st.st_size}"
        cache_path = CACHE_DIR / f"_livro_fiscal_cache__{fingerprint}.parquet"
    except Exception:
        cache_path = None

    if cache_path and cache_path.exists():
        try:
            return pl.read_parquet(str(cache_path))
        except Exception:
            # Se o cache estiver corrompido, tenta re-gerar abaixo.
            try:
                cache_path.unlink()
            except Exception:
                pass

    df = _ler_livro_fiscal(caminho)

    if cache_path is not None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.write_parquet(str(cache_path), compression=COMPRESSION)
        except Exception:
            # Cache é puramente otimização: se falhar, segue o jogo.
            pass

    return df


# ---------- Coerções pro output do livro (datas e números BR) ------------

def _coerce_para_data_br(col_name):
    """Converte uma coluna de data para o formato BR 'dd/mm/yyyy'.

    Aceita os formatos comuns que aparecem na nossa pipeline:
      - Serial Excel (46095) — quando o reader devolveu o número bruto
      - ISO datetime ('2026-03-01 00:00:00') — formato do calamine
      - ISO date ('2026-03-01')
      - BR date ('06/03/2026') — preservado intacto
      - Qualquer outra coisa: preserva o valor original (sem quebrar)
    """
    from datetime import date

    raw = pl.col(col_name).cast(pl.Utf8).fill_null("").str.strip_chars()

    # 1) Já é BR ('06/03/2026') — primeira coisa que checamos pra preservar
    eh_br = raw.str.contains(r"^\d{2}/\d{2}/\d{4}", literal=False)

    # 2) ISO datetime ou date ('2026-03-01' ou '2026-03-01 00:00:00')
    eh_iso = raw.str.contains(r"^\d{4}-\d{2}-\d{2}", literal=False)
    iso_para_br = (
        raw.str.slice(8, 2)              # dia
        + pl.lit("/")
        + raw.str.slice(5, 2)            # mês
        + pl.lit("/")
        + raw.str.slice(0, 4)            # ano
    )

    # 3) Serial Excel (somente dígitos, opcionalmente com decimal)
    eh_serial = raw.str.contains(r"^\d+(\.\d+)?$", literal=False)
    serial_int = (
        raw.str.replace(r"\..*$", "", literal=False)
           .cast(pl.Int64, strict=False)
    )
    epoch = pl.lit(date(1899, 12, 30))  # Excel epoch (leap-year bug compatível)
    serial_para_br = (
        (epoch + pl.duration(days=serial_int)).dt.strftime("%d/%m/%Y")
    )

    return (
        pl.when(eh_br).then(raw)
          .when(eh_iso).then(iso_para_br)
          .when(eh_serial & (raw != "")).then(serial_para_br)
          .otherwise(raw)
    )


def _coerce_para_num_br(col_name):
    """Garante formato numérico BR (vírgula decimal) na coluna.

    Se o valor já tem vírgula, preserva (assume BR). Se tem só ponto, troca
    o ponto pela vírgula. Excel em locale BR vai reconhecer como número
    (alinha à direita, somatórios funcionam, etc.).
    """
    raw = pl.col(col_name).cast(pl.Utf8).fill_null("").str.strip_chars()
    is_us = raw.str.contains(r"\.", literal=False) & ~raw.str.contains(",", literal=True)
    convertido = raw.str.replace(".", ",", literal=True)
    return pl.when(is_us).then(convertido).otherwise(raw)


# Quais colunas do output devem ser tratadas como Data ou Número BR.
# Inclui os nomes tanto do schema de Entrada quanto do schema de Saída;
# o coercion check existe-coluna antes de aplicar, então é seguro listar tudo.
LIVRO_DATE_COLS = ["DTEMISS", "DTENTR", "INFSM_DTEM"]
LIVRO_NUM_COLS = [
    "VAL_IPI", "VAL_ICMS", "VAL_SUBST_ICMS",
    "INFSM_VAL_IPI", "INFSM_VAL_ICMS", "INFSM_VALSUBST_ICMS",
]


# Colunas que ICMS Transitórias precisa, por (origem, tipo). Servem pra
# PROJETAR a leitura — em vez de carregar 116-146 colunas, pl.read_excel
# aloca só as ~20 listadas. Isso reduz uso de memória de ~8GB pra ~1.5GB
# em arquivos grandes (Saídas com 1M linhas), evitando crash por OOM.
LIVRO_COLS_PROJECAO = {
    ("ANDERSEN", "ENTRADA"): [
        "Índice", "Fonte", "Período", "CHAVE DA NOTA", "EMPRESA", "Divisão",
        "CNPJ/CPF", "UF", "IND_CANC", "INFEM_NUM", "DTEMIS", "DTENTR",
        "CFOP_COD", "VAL_IPI", "VAL_ICMS", "VALSUBST_ICMS", "MATE_COD",
        "DSC", "IND_MOV", "ID_ORIGEM",
    ],
    ("ANDERSEN", "SAIDA"): [
        "Índice", "Fonte", "Período", "MNFSM_CHV_NFE", "EMPRESA", "Divisão",
        "CNPJ/CPF", "UF", "IND_CANC", "INFSM_NUM", "INFSM_DTEM",
        "CFOP_COD", "INFSM_VAL_IPI", "INFSM_VAL_ICMS", "INFSM_VALSUBST_ICMS",
        "MATE_COD", "INFSM_DSC", "ID_ORIGEM",
        # IND_MOV não existe no Saída — só no Entrada
    ],
    ("VIVO", "ENTRADA"): [
        "Índice", "Fonte", "Período", "Chave Nota Fiscal", "Empresa", "Divisão",
        "CNPJ/CPF", "Unidade Federativa", "Indicador de Cancelamento",
        "Nota Fiscal", "Emissão", "Entrada", "CFOP",
        "Valor do IPI", "Valor do ICMS", "Valor Subst. ICMS",
        "Material", "Descrição Complementar", "Indicador de Movimento", "ID Origem",
    ],
    ("VIVO", "SAIDA"): [
        "Índice", "Fonte", "Período", "Chave de Acesso", "Empresa", "Divisão",
        "CNPJ/CPF", "UF", "Indicador de Cancelamento",
        "Nota Fiscal", "Data Emissão", "CFOP",
        "Vr. do IPI", "Vr. de ICMS", "Vr. do ICMS por Substituto",
        "Material", "Descrição", "Indicador de Movimento", "ID Origem",
    ],
}


def _detectar_formato_livro(caminho):
    """Detecta (origem, tipo) baseado no filename. Retorna tupla com strings
    'ANDERSEN' / 'VIVO' / None pra origem e 'ENTRADA' / 'SAIDA' / None pra tipo."""
    nome = Path(caminho).stem.lower()
    nome_norm = (
        nome.replace("í", "i").replace("ã", "a").replace("á", "a")
            .replace("é", "e").replace("ê", "e").replace("ó", "o").replace("ô", "o")
    )
    origem = None
    if "andersen" in nome_norm:
        origem = "ANDERSEN"
    elif "vivo" in nome_norm:
        origem = "VIVO"
    tipo = None
    if "saida" in nome_norm:
        tipo = "SAIDA"
    elif "entrada" in nome_norm:
        tipo = "ENTRADA"
    return origem, tipo


def _cols_projecao_pra_arquivo(caminho):
    """Retorna a lista de colunas a projetar (~20) baseado no tipo do arquivo.
    None se o tipo não bater com nenhum padrão conhecido — chamador faz
    leitura completa nesse caso."""
    origem, tipo = _detectar_formato_livro(caminho)
    if not origem or not tipo:
        return None
    return LIVRO_COLS_PROJECAO.get((origem, tipo))


def _resolver_aliases(cols_arquivo, alias_dict):
    """Para cada chave canônica, devolve o nome real da coluna no arquivo
    (ou None se nenhuma alternativa existir)."""
    cols_set = set(cols_arquivo)
    resolvido = {}
    for canonico, candidatos in alias_dict.items():
        achou = None
        for c in candidatos:
            if c in cols_set:
                achou = c
                break
        resolvido[canonico] = achou
    return resolvido


def _periodo_para_mm_yyyy(valor):
    """Aceita 'YYYY_MM', 'MM_YYYY', 'YYYY/MM', 'YYYY-MM', etc. e devolve
    sempre 'MM_YYYY' (formato esperado no nome do arquivo final). Se não
    conseguir entender, devolve a string saneada (sem barras/pontos)."""
    s = (valor or "").strip().replace("/", "_").replace("-", "_").replace(".", "_")
    partes = [p for p in s.split("_") if p]
    if len(partes) == 2:
        a, b = partes
        if len(a) == 4 and len(b) == 2:   # YYYY_MM
            return f"{b}_{a}"
        if len(a) == 2 and len(b) == 4:   # MM_YYYY
            return s
    return s or "PERIODO"


def extrair_transitorias_livro(
    caminho_livro,
    destino,
    tipo_movimento,
    progress_callback=None,
):
    """Extrai as Transitórias de um Livro Fiscal (Entradas ou Saídas).

    Pipeline (todo no parquet/Polars — XLSB só serializa no final):
      1. Lê o livro (xlsx/xlsb/csv/parquet) em strings
      2. Resolve nomes de coluna por alias (Vivo / Andersen / parquet)
      3. Filtra CFOP_COD pela lista transitória do tipo escolhido
      4. Cria 'CHAVE DA NOTA AA' = CHAVE DA NOTA + "."
      5. Cria 'Chave_01' = Divisão_INFEM_NUM
      6. Seleciona/renomeia as colunas finais na ordem pedida
      7. Grava em xlsb (rápido) / xlsx / csv conforme extensão de `destino`

    tipo_movimento: 'ENTRADA' ou 'SAIDA'
    """
    tipo = (tipo_movimento or "").strip().upper()
    if tipo not in ("ENTRADA", "SAIDA"):
        raise ValueError(f"tipo_movimento inválido: {tipo_movimento!r}")

    if progress_callback:
        progress_callback("livro", 1, 5, "Lendo livro fiscal...")

    # Cache em parquet: na 1ª leitura de um xlsb/xlsx/csv, salva uma versão
    # parquet em CACHE_DIR. Próxima vez que o mesmo arquivo for usado, lê
    # do parquet (~instantâneo). Todo o resto do pipeline já roda em polars
    # sobre esse dataframe — XLSB só aparece no fim, na hora de exportar.
    df = _ler_livro_fiscal_com_cache(caminho_livro)
    resolvido = _resolver_aliases(df.columns, LIVRO_COL_ALIASES)

    if not resolvido.get("cfop_cod"):
        raise ValueError(
            "Coluna CFOP_COD/CFOP não encontrada no livro fiscal importado."
        )
    if not resolvido.get("divisao"):
        raise ValueError("Coluna Divisão não encontrada no livro fiscal.")
    if not resolvido.get("infem_num"):
        raise ValueError(
            "Coluna INFEM_NUM/Nota Fiscal não encontrada no livro fiscal."
        )

    cfops_alvo = CFOP_TRANSIT_ENTRADA if tipo == "ENTRADA" else CFOP_TRANSIT_SAIDA
    rotulo_tipo = "Entrada" if tipo == "ENTRADA" else "Saída"

    if progress_callback:
        progress_callback(
            "livro", 2, 5, f"Filtrando CFOPs transitórios ({rotulo_tipo})..."
        )

    col_cfop = resolvido["cfop_cod"]
    df = df.with_columns(
        pl.col(col_cfop).cast(pl.Utf8).fill_null("").str.strip_chars().alias(col_cfop)
    )
    df = df.filter(pl.col(col_cfop).is_in(cfops_alvo))

    # Exclui notas canceladas (IND_CANC = "S"). Mantém só "N" (normal) ou
    # ausente. Aplicado em qualquer tipo (Entrada e Saída) — convenção
    # fiscal padrão é não considerar notas canceladas.
    col_canc = resolvido.get("ind_canc")
    if col_canc:
        df = df.with_columns(
            pl.col(col_canc).cast(pl.Utf8).fill_null("")
              .str.strip_chars().str.to_uppercase().alias(col_canc)
        )
        df = df.filter(pl.col(col_canc) != "S")

    if df.height == 0:
        raise ValueError(
            f"Nenhum CFOP transitório de {rotulo_tipo} encontrado no livro "
            f"importado (após filtro de notas canceladas).\n"
            f"CFOPs procurados: {', '.join(cfops_alvo)}"
        )

    if progress_callback:
        progress_callback("livro", 3, 5, "Criando CHAVE DA NOTA AA e Chave_01...")

    col_chave = resolvido.get("chave_nota")
    if col_chave:
        df = df.with_columns(
            (pl.col(col_chave).cast(pl.Utf8).fill_null("").str.strip_chars()
             + pl.lit(".")).alias("CHAVE DA NOTA AA")
        )
    else:
        df = df.with_columns(pl.lit("").alias("CHAVE DA NOTA AA"))

    col_div = resolvido["divisao"]
    col_nf = resolvido["infem_num"]
    df = df.with_columns(
        (pl.col(col_div).cast(pl.Utf8).fill_null("").str.strip_chars()
         + pl.lit("_")
         + pl.col(col_nf).cast(pl.Utf8).fill_null("").str.strip_chars()
         ).alias("Chave_01")
    )

    if progress_callback:
        progress_callback("livro", 4, 5, "Selecionando colunas finais...")

    # Pra Saída usamos o schema que preserva os nomes ORIGINAIS do livro
    # (INFSM_NUM, INFSM_DTEM, INFSM_VAL_ICMS, etc) em vez de renomear pra
    # versão Entrada. Pra Entrada continua o schema original do usuário.
    output_cols = (
        LIVRO_OUTPUT_COLS_SAIDA if tipo == "SAIDA"
        else LIVRO_OUTPUT_COLS_ENTRADA
    )

    select_exprs = []
    for nome_final, chave_canon in output_cols:
        if chave_canon is None:
            # Coluna derivada (CHAVE DA NOTA AA, Chave_01) — já existe no df.
            if nome_final in df.columns:
                select_exprs.append(pl.col(nome_final))
            else:
                select_exprs.append(pl.lit("").alias(nome_final))
        else:
            real = resolvido.get(chave_canon)
            if real and real in df.columns:
                select_exprs.append(
                    pl.col(real).cast(pl.Utf8).fill_null("").alias(nome_final)
                )
            else:
                # Coluna ausente no livro: preserva a coluna no output, vazia.
                select_exprs.append(pl.lit("").alias(nome_final))

    df_final = df.select(select_exprs)

    # Coerções de tipo APENAS no output (datas viram dd/mm/yyyy a partir do
    # serial Excel; valores em formato US viram BR com vírgula). Excel em
    # locale BR consegue reconhecer essas células como Date e Number nativos.
    coerc_exprs = []
    for c in LIVRO_DATE_COLS:
        if c in df_final.columns:
            coerc_exprs.append(_coerce_para_data_br(c).alias(c))
    for c in LIVRO_NUM_COLS:
        if c in df_final.columns:
            coerc_exprs.append(_coerce_para_num_br(c).alias(c))
    if coerc_exprs:
        df_final = df_final.with_columns(coerc_exprs)

    # Período pra nome do arquivo: primeira ocorrência não-vazia em PERÍODO.
    periodo_raw = ""
    if "PERÍODO" in df_final.columns:
        for v in df_final["PERÍODO"].to_list():
            if v and str(v).strip():
                periodo_raw = str(v).strip()
                break
    periodo_mm_yyyy = _periodo_para_mm_yyyy(periodo_raw)

    destino = Path(destino)

    if progress_callback:
        progress_callback(
            "livro", 5, 5,
            f"Gravando {df_final.height:,} linhas em {destino.name}..."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)
    suf = destino.suffix.lower()
    if suf == ".csv":
        df_final.write_csv(str(destino), separator=";", include_bom=True)
    elif suf == ".xlsb":
        from validar_logic import _csv_para_xlsb_rapido
        tmp_csv = destino.with_suffix(".__tmp__.csv")
        try:
            with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
                f.write("﻿")
                df_final.write_csv(
                    f, separator=";", include_header=True,
                    null_value="", line_terminator="\n",
                    quote_style="necessary",
                )
            _csv_para_xlsb_rapido(
                str(tmp_csv), str(destino),
                progress_callback=progress_callback,
            )
        finally:
            try:
                tmp_csv.unlink()
            except Exception:
                pass
    else:
        if suf != ".xlsx":
            destino = destino.with_suffix(".xlsx")
        try:
            df_final.write_excel(str(destino), autofit=False)
        except TypeError:
            df_final.write_excel(str(destino))

    return {
        "destino": str(destino),
        "linhas": df_final.height,
        "tipo": rotulo_tipo,
        "periodo": periodo_mm_yyyy,
    }
