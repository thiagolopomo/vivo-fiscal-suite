#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import os
import re
import gc
import json
import time
import shutil
import tempfile
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        div = m.group(1)
        # 85MN é um alias legado que aparece em nomes de arquivo mas não
        # existe como divisão real — o valor correto é 85MG (Minas Gerais).
        # Mesma normalização feita em validar_logic.py e raicms_logic.py.
        if div == "85MN":
            return "85MG"
        return div

    return ""


def _parse_txt_para_parquet(caminho_txt, parte_path):
    """Lê um TXT ZTMM, parseia via pl.read_csv e grava como parquet.

    Muito mais rápido que o parser manual em Python porque o `pl.read_csv`
    roda em código nativo (SIMD), libera o GIL e constrói o Arrow direto
    sem passar por `list[list[str]]` intermediário.

    Retorna (parte_path, height) ou None se o arquivo estiver vazio/inválido.
    """
    with open(caminho_txt, "rb") as f:
        raw = f.read()

    text = raw.decode("latin-1", errors="ignore")
    del raw
    lines = text.splitlines()
    del text

    header_idx = None
    for i, linha in enumerate(lines):
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

    header_raw = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    header = ajustar_header_duplicados(header_raw)
    divisao = extrair_divisao(caminho_txt)

    # Em vez de splittar cada célula em Python, apenas filtramos as linhas
    # de dados relevantes (descartando "-----|-----|-----", linhas vazias e
    # lixo fora da tabela) e deixamos o parser nativo do polars fazer o split.
    data_buf = []
    for linha in lines[header_idx + 1:]:
        if not linha.startswith("|"):
            continue
        s = linha.strip()
        if not s or set(s) <= set("-|"):
            continue
        data_buf.append(linha.strip().strip("|"))

    del lines

    if not data_buf:
        return None

    csv_bytes = "\n".join(data_buf).encode("utf-8", errors="replace")
    del data_buf

    schema = {name: pl.Utf8 for name in header}

    # quote_char=None desliga o parsing de aspas, replicando o split("|") cru
    # do parser antigo. Sem isso, o polars ao ver um `"` numa descrição
    # entraria em modo "quoted" e engoliria os separadores seguintes.
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
        # Fallback: alguns builds de polars não aceitam `schema` direto no
        # read_csv com has_header=False. Usa new_columns + infer_schema_length=0.
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

    # Remove whitespace das células (vetorizado, nativo).
    df = df.with_columns([pl.col(c).str.strip_chars() for c in df.columns])

    # Divisão como constante — metadata, não copia dados.
    df = df.with_columns(pl.lit(divisao).alias("Divisão"))

    df.write_parquet(str(parte_path), compression=COMPRESSION)
    height = df.height
    del df
    return parte_path, height


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
    tmp_dir = Path(tempfile.mkdtemp(prefix="ztmm_parts_", dir=str(CACHE_DIR)))
    temp_parts = []

    # Paraleliza o parsing via threads: o pl.read_csv libera o GIL durante
    # o parse nativo, então threads dão ganho real sem o overhead de
    # spawn/pickle do multiprocessing no Windows. Cap em 4 workers pra
    # equilibrar throughput com pressão de memória (cada worker pode ter
    # um arquivo inteiro em RAM durante o parse).
    max_workers = max(1, min(4, os.cpu_count() or 2))

    def _worker(args):
        idx, caminho = args
        parte_path = tmp_dir / f"parte_{idx:06d}.parquet"
        try:
            resultado = _parse_txt_para_parquet(caminho, parte_path)
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
                # status "vazio" e "erro" são ignorados (mantém o comportamento
                # anterior de pular TXTs sem tabela)

        if not temp_parts:
            raise ValueError("Nenhum TXT com dados válidos encontrado.")

        # Ordena os temp_parts para manter determinismo na ordem do concat
        temp_parts = sorted(temp_parts)

        if progress_callback:
            progress_callback("consolidando", 1, 1, "Concatenando DataFrames...")

        parquet_path = CACHE_DIR / "ZTMM_Consolidado.parquet"

        # Concat em streaming: lê os parquets temporários como LazyFrames e
        # grava direto no parquet final sem carregar tudo de uma vez.
        # diagonal_relaxed tolera diferenças de colunas entre arquivos
        # (alguns TXTs de ZTMM podem ter colunas extras dependendo da planta).
        lazy_frames = [pl.scan_parquet(str(p)) for p in temp_parts]
        lf = pl.concat(lazy_frames, how="diagonal_relaxed")

        try:
            lf.sink_parquet(str(parquet_path), compression=COMPRESSION)
        except Exception:
            # Fallback: se o engine de streaming não suportar diagonal_relaxed
            # na versão atual, coleta em modo streaming e grava normalmente.
            df_final = lf.collect(streaming=True)
            df_final.write_parquet(str(parquet_path), compression=COMPRESSION)
            del df_final
            gc.collect()

        # Total de linhas e divisões lidos diretamente do parquet final,
        # sem materializar o DataFrame inteiro.
        lf_final = pl.scan_parquet(str(parquet_path))
        total_linhas = int(lf_final.select(pl.len()).collect().item())

        divs_df = (
            lf_final
            .select(pl.col("Divisão").cast(pl.Utf8).fill_null("").str.strip_chars())
            .unique()
            .collect()
        )
        divisoes = sorted(set(
            str(x).strip() for x in divs_df["Divisão"].to_list()
            if str(x).strip()
        ))
        del divs_df, lf_final
        gc.collect()

        meta = {
            "parquet_path": str(parquet_path),
            "total_linhas": total_linhas,
            "divisoes": divisoes,
            "pasta_origem": str(pasta_txts),
            "data_processamento": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tempo_total": round(time.time() - t0, 2),
        }
        with open(CACHE_ZTMM_META, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback("finalizado", 1, 1, parquet_path.name)

        return str(parquet_path), total_linhas, divisoes
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


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
