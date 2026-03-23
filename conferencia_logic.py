#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from pathlib import Path
import pandas as pd
import polars as pl

CACHE_DIR = Path.home() / "AppData" / "Local" / "ValidadorVIVO"
CACHE_CONFERENCIA_META = CACHE_DIR / "conferencia_bases_meta.json"
CACHE_RAICMS_META = CACHE_DIR / "raicms_meta.json"


def _to_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _tipo_por_cfop(cfop):
    cfop = (str(cfop or "").strip())
    if not cfop:
        return ""
    if cfop[:1] in {"1", "2", "3"}:
        return "Entrada"
    if cfop[:1] in {"5", "6", "7"}:
        return "Saída"
    return ""


def carregar_meta_json(path):
    if not Path(path).exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def encontrar_execucao_complementar(meta_execucao):
    base_dir_execs = CACHE_DIR / "execucoes_conferencia"
    if not base_dir_execs.exists():
        return None

    periodo_ref = str(meta_execucao.get("periodo", "")).strip()
    base_dir_ref = str(meta_execucao.get("base_dir", "")).strip()
    tipo_ref = str(meta_execucao.get("tipo_movimento", "")).strip().upper()

    if tipo_ref == "ENTRADA":
        tipo_alvo = "SAIDA"
    elif tipo_ref == "SAIDA":
        tipo_alvo = "ENTRADA"
    else:
        return None

    for sub in sorted(base_dir_execs.iterdir(), reverse=True):
        if not sub.is_dir():
            continue

        meta_path = sub / "meta.json"
        if not meta_path.exists():
            continue

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue

        if (
            str(meta.get("periodo", "")).strip() == periodo_ref
            and str(meta.get("base_dir", "")).strip() == base_dir_ref
            and str(meta.get("tipo_movimento", "")).strip().upper() == tipo_alvo
        ):
            return meta

    return None


def montar_base_fiscal(parquet_path, base_nome, livro_filtro="Ambos"):
    lf = pl.scan_parquet(str(parquet_path))
    cols = lf.collect_schema().names()

    col_cfop = "CFOP" if "CFOP" in cols else ("CFOP_COD" if "CFOP_COD" in cols else None)
    if not col_cfop:
        raise ValueError(f"A base {base_nome} não possui CFOP nem CFOP_COD.")

    col_div = "Divisão" if "Divisão" in cols else None
    col_map = "Mapeamento" if "Mapeamento" in cols else None

    if not col_div or not col_map:
        raise ValueError(f"A base {base_nome} não possui as colunas mínimas esperadas.")

    if "Valor Fiscal" in cols:
        col_valor = "Valor Fiscal"
    elif "Valor_ICMS_Conf" in cols:
        col_valor = "Valor_ICMS_Conf"
    elif "VAL_ICMS" in cols:
        col_valor = "VAL_ICMS"
    elif "INFSM_VAL_ICMS" in cols:
        col_valor = "INFSM_VAL_ICMS"
    else:
        raise ValueError(
            f"A base {base_nome} não possui coluna de valor de ICMS para conferência."
        )

    if "Tipo" in cols:
        expr_tipo = (
            pl.col("Tipo")
            .cast(pl.Utf8)
            .fill_null("")
            .str.strip_chars()
            .alias("Tipo")
        )
    else:
        expr_tipo = (
            pl.when(pl.col(col_cfop).cast(pl.Utf8).str.slice(0, 1).is_in(["1", "2", "3"]))
            .then(pl.lit("Entrada"))
            .when(pl.col(col_cfop).cast(pl.Utf8).str.slice(0, 1).is_in(["5", "6", "7"]))
            .then(pl.lit("Saída"))
            .otherwise(pl.lit(""))
            .alias("Tipo")
        )

    lf = lf.with_columns([
        pl.col(col_div).cast(pl.Utf8).fill_null("").str.strip_chars().str.to_uppercase().alias("Divisão"),
        pl.col(col_cfop).cast(pl.Utf8).fill_null("").str.strip_chars().alias("CFOP"),
        pl.col(col_map).cast(pl.Utf8).fill_null("").str.strip_chars().alias("Mapeamento"),
        expr_tipo,
        pl.col(col_valor).cast(pl.Float64, strict=False).fill_null(0).alias("Valor"),
        pl.lit(base_nome).alias("Fonte"),
    ])

    if livro_filtro == "Livro de Entrada":
        lf = lf.filter(pl.col("Tipo").str.to_uppercase() == "ENTRADA")
    elif livro_filtro == "Livro de Saída":
        lf = lf.filter(pl.col("Tipo").str.to_uppercase().is_in(["SAÍDA", "SAIDA"]))

    lf = lf.with_columns([
        (pl.col("Divisão") + pl.lit("_") + pl.col("CFOP")).alias("Chave")
    ])

    out = (
        lf.group_by(["Chave", "Fonte", "Tipo", "Divisão", "CFOP", "Mapeamento"])
        .agg([
            pl.col("Valor").sum().alias("Valor Fiscal"),
            pl.col("Valor").abs().sum().alias("Abs"),
        ])
        .sort(["Divisão", "CFOP", "Mapeamento", "Fonte"])
        .collect()
        .to_pandas()
    )

    return out


def montar_base_p9(excel_p9_path, livro_filtro="Ambos"):
    xls = pd.ExcelFile(excel_p9_path)

    if "Consolidado" not in xls.sheet_names:
        raise ValueError("O arquivo P9 não possui a aba 'Consolidado'.")

    df = pd.read_excel(excel_p9_path, sheet_name="Consolidado")

    req = ["Divisão", "CFOP", "Mapeamento", "Imposto Creditado"]
    falt = [c for c in req if c not in df.columns]
    if falt:
        raise ValueError(f"A aba Consolidado do P9 não possui as colunas: {falt}")

    df["Divisão"] = df["Divisão"].fillna("").astype(str).str.strip()
    df["CFOP"] = df["CFOP"].fillna("").astype(str).str.strip()
    df["Mapeamento"] = df["Mapeamento"].fillna("").astype(str).str.strip()
    df["Fonte"] = "Apuração P9"
    df["Tipo"] = df["CFOP"].apply(_tipo_por_cfop)
    df["Imposto Creditado"] = _to_num(df["Imposto Creditado"]).round(2)

    if livro_filtro == "Livro de Entrada":
        df = df[df["Tipo"] == "Entrada"].copy()
    elif livro_filtro == "Livro de Saída":
        df = df[df["Tipo"] == "Saída"].copy()

    df["Chave"] = df["Divisão"] + "_" + df["CFOP"]

    grp = (
        df.groupby(["Chave", "Fonte", "Tipo", "Divisão", "CFOP", "Mapeamento"], dropna=False, as_index=False)
          .agg({"Imposto Creditado": "sum"})
    )
    grp["Imposto Creditado"] = _to_num(grp["Imposto Creditado"]).round(2)
    grp["Abs"] = grp["Imposto Creditado"].abs()

    grp = grp.rename(columns={"Imposto Creditado": "Apuração Vivo"})
    return grp


def montar_sheet_conferencia(df_fiscal, df_p9):
    chaves = ["Chave", "Tipo", "Divisão", "CFOP", "Mapeamento"]

    fiscal = (
        df_fiscal[chaves + ["Valor Fiscal"]].copy()
        if not df_fiscal.empty
        else pd.DataFrame(columns=chaves + ["Valor Fiscal"])
    )
    p9 = (
        df_p9[chaves + ["Apuração Vivo"]].copy()
        if not df_p9.empty
        else pd.DataFrame(columns=chaves + ["Apuração Vivo"])
    )

    final = pd.merge(
        p9,
        fiscal,
        how="outer",
        on=chaves
    )

    final["Apuração Vivo"] = _to_num(final.get("Apuração Vivo", 0)).round(2)
    final["Livro Entrada / Saída"] = _to_num(final.get("Valor Fiscal", 0)).round(2)
    final.drop(columns=[c for c in ["Valor Fiscal"] if c in final.columns], inplace=True)

    def calcular_total_geral(row):
        a = float(row["Apuração Vivo"] or 0)
        b = float(row["Livro Entrada / Saída"] or 0)

        # sinais opostos -> somar
        if (a < 0 and b > 0) or (a > 0 and b < 0):
            total = a + b
        else:
            # mesmo sinal -> comparar por diferença de magnitude
            total = abs(a) - abs(b)

        if abs(total) < 0.005:
            return 0.0

        return round(total, 2)

    final["Total Geral"] = final.apply(calcular_total_geral, axis=1)

    final["Status"] = ""

    mask_ok = final["Total Geral"].abs() < 0.005
    final.loc[mask_ok, "Status"] = "Ok"

    pend = final[final["Status"].eq("")].copy()
    if not pend.empty:
        totais_div = (
            pend.groupby("Divisão", dropna=False)["Total Geral"]
                .sum()
                .reset_index()
                .rename(columns={"Total Geral": "_soma_div"})
        )
        pend = pend.merge(totais_div, on="Divisão", how="left")

        div_zero = set(
            pend.loc[pend["_soma_div"].abs() < 0.005, "Divisão"].astype(str).tolist()
        )
        if div_zero:
            final.loc[
                final["Status"].eq("") & final["Divisão"].astype(str).isin(div_zero),
                "Status"
            ] = "Soma zero entre CFOPs"

    final = final[
        ["Chave", "Tipo", "CFOP", "Mapeamento", "Apuração Vivo", "Livro Entrada / Saída", "Total Geral", "Status", "Divisão"]
    ].copy()

    final = final.sort_values(["Divisão", "CFOP", "Mapeamento", "Chave"], kind="stable")
    return final

def executar_conferencia(bases_selecionadas, livro_filtro, pasta_destino, meta_execucao):
    if not meta_execucao:
        raise ValueError("Nenhuma execução consolidada foi selecionada.")

    meta_p9 = carregar_meta_json(CACHE_RAICMS_META)
    if not meta_p9:
        raise ValueError("Nenhum arquivo P9 processado foi encontrado. Execute a Validação P9 primeiro.")

    excel_p9 = meta_p9.get("arquivo_final")
    if not excel_p9 or not Path(excel_p9).exists():
        raise ValueError("O último arquivo P9 consolidado não foi encontrado no cache.")

    metas_para_usar = []

    # Caso novo: combo em modo AMBOS já entrega entrada + saída prontas
    if isinstance(meta_execucao, dict) and meta_execucao.get("modo") == "AMBOS":
        meta_entrada = meta_execucao.get("entrada")
        meta_saida = meta_execucao.get("saida")

        if not meta_entrada or not meta_saida:
            raise ValueError("Execução em modo 'Ambos' está incompleta.")

        metas_para_usar.extend([meta_entrada, meta_saida])

    else:
        # Caso normal: uma execução só
        metas_para_usar.append(meta_execucao)

    frames_fiscal = []

    for meta in metas_para_usar:
        for base in bases_selecionadas:
            chave = base.lower()
            parquet_path = meta.get(chave)

            if parquet_path and Path(parquet_path).exists():
                frames_fiscal.append(
                    montar_base_fiscal(
                        parquet_path,
                        base,
                        livro_filtro=livro_filtro
                    )
                )

    if not frames_fiscal:
        raise ValueError("Nenhuma base fiscal selecionada foi encontrada na execução escolhida.")

    df_fiscal = pd.concat(frames_fiscal, ignore_index=True) if frames_fiscal else pd.DataFrame()
    df_p9 = montar_base_p9(excel_p9, livro_filtro=livro_filtro)
    df_conf = montar_sheet_conferencia(df_fiscal, df_p9)

    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    if isinstance(meta_execucao, dict) and meta_execucao.get("modo") == "AMBOS":
        periodo_txt = str(meta_execucao.get("periodo", "SEM_PERIODO")).replace("/", "_").replace(", ", "__")
        tipo_txt = "AMBOS"
    else:
        periodo_txt = str(meta_execucao.get("periodo", "SEM_PERIODO")).replace("/", "_").replace(", ", "__")
        tipo_txt = str(meta_execucao.get("tipo_movimento", "")).upper()

    out = pasta_destino / f"CONFERENCIA_P9_x_FISCAL__{periodo_txt}__{tipo_txt}.xlsx"

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_fiscal.to_excel(writer, index=False, sheet_name="Base_Fiscal")
        df_p9.to_excel(writer, index=False, sheet_name="Apuracao_P9")
        df_conf.to_excel(writer, index=False, sheet_name="Conferencia")

    return {
        "arquivo_saida": str(out),
        "linhas_fiscal": len(df_fiscal),
        "linhas_p9": len(df_p9),
        "linhas_conferencia": len(df_conf),
    }


def listar_execucoes_conferencia():
    base_dir = CACHE_DIR / "execucoes_conferencia"
    if not base_dir.exists():
        return []

    itens = []
    for sub in sorted(base_dir.iterdir(), reverse=True):
        if not sub.is_dir():
            continue
        meta_path = sub / "meta.json"
        if not meta_path.exists():
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            itens.append(meta)
        except Exception:
            continue

    return itens