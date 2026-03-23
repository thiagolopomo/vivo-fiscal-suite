#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import time
import unicodedata
from pathlib import Path
from decimal import Decimal
import polars as pl


def _norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", s.lower().strip())


def achar_col(colunas, alvo):
    alvo_n = _norm(alvo)
    candidatos = [c for c in colunas if _norm(c).startswith(alvo_n)]
    if not candidatos:
        raise ValueError(f"Coluna '{alvo}' não encontrada. Disponíveis: {colunas}")
    return candidatos[0]


def _ck(c):
    return (pl.col(c).cast(pl.Utf8).fill_null("")
            .str.replace_all(r"[\u200B-\u200F\uFEFF]", "")
            .str.replace_all("\u00A0", " ")
            .str.replace_all(r"\.0$", "")
            .str.replace_all(r"\s+", "").str.strip_chars())


def _ck0(c):
    return _ck(c).str.replace_all(r"^0+", "")


def br2d(x):
    if x is None:
        return Decimal("0")
    s = str(x).strip()
    if not s:
        return Decimal("0")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip()
    if "-" in s:
        neg = True
    s = re.sub(r"[^0-9\.,]", "", s)
    if not s:
        return Decimal("0")
    s = s.replace(".", "").replace(",", ".")
    d = Decimal(s)
    return -d if neg else d


def d2br(d):
    return f"{d:.2f}".replace(".", ",")


def soma_lista(lista):
    if lista is None:
        return Decimal("0")
    return sum((br2d(str(v)) for v in lista if v is not None), Decimal("0"))


def detectar_razoes_na_pasta(pasta):
    pasta = Path(pasta)
    if not pasta.exists():
        raise FileNotFoundError(f"Pasta de Razões não encontrada: {pasta}")
    r222, r223 = None, None
    for f in sorted(pasta.iterdir()):
        if not f.is_file() or not f.name.upper().endswith(".CSV"):
            continue
        n = f.name.upper()
        if "222" in n and r222 is None:
            r222 = f
        elif "223" in n and r223 is None:
            r223 = f
    return r222, r223


def ler_nc(path):
    ext = Path(path).suffix.lower()
    if ext == ".parquet":
        return pl.read_parquet(str(path))
    if ext == ".csv":
        return pl.read_csv(str(path), separator=";", encoding="utf8",
                           infer_schema_length=0, ignore_errors=True, truncate_ragged_lines=True)
    raise ValueError(f"Formato NC não suportado: {ext}")


def ler_razao_csv(path):
    if path is None:
        return None
    return pl.read_csv(str(path), separator=";", encoding="utf8",
                       infer_schema_length=0, ignore_errors=True, truncate_ragged_lines=True)


def _build_map(ztm, keys, vi2, ste, cfop, nfe, dte, dof, dob, sfx):
    sub = ztm.join(keys, on="CHAVE", how="inner")
    return (
        sub.group_by("CHAVE").agg([
            pl.first(vi2).cast(pl.Utf8).alias(f"V2_{sfx}_s"),
            pl.col(vi2).cast(pl.Utf8).alias(f"V2_{sfx}_l"),
            pl.first(ste).cast(pl.Utf8).alias(f"ST_{sfx}_s"),
            pl.col(ste).cast(pl.Utf8).alias(f"ST_{sfx}_l"),
            pl.first(cfop).alias(f"CF_{sfx}"),
            pl.first(nfe).alias(f"NE_{sfx}"),
            pl.first(dte).alias(f"DE_{sfx}"),
            pl.first(dof).alias(f"DF_{sfx}"),
            pl.first(dob).alias(f"DB_{sfx}"),
        ]).with_columns([
            pl.col(f"V2_{sfx}_l").map_elements(lambda l: d2br(soma_lista(l)), return_dtype=pl.Utf8).alias(f"V2_{sfx}_sum"),
            pl.col(f"ST_{sfx}_l").map_elements(lambda l: d2br(soma_lista(l)), return_dtype=pl.Utf8).alias(f"ST_{sfx}_sum"),
            pl.col(f"V2_{sfx}_l").map_elements(lambda l: soma_lista(l) == Decimal("0"), return_dtype=pl.Boolean).alias(f"_iz_{sfx}"),
            pl.col(f"V2_{sfx}_l").map_elements(lambda l: soma_lista(l) > Decimal("0"), return_dtype=pl.Boolean).alias(f"_ip_{sfx}"),
        ]).drop([f"V2_{sfx}_l", f"ST_{sfx}_l"])
    )


def executar_analise_ztmm(parquet_ztm, caminho_nc, pasta_razoes, pasta_destino, progress_callback=None):
    t0 = time.time()
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    def rpt(e, a, t, m):
        if progress_callback:
            progress_callback(e, a, t, m)

    rpt("lendo", 1, 8, "Lendo base ZTMM...")
    cz = pl.read_parquet(str(parquet_ztm), n_rows=0).columns

    rpt("lendo", 2, 8, "Lendo Não Conciliados...")
    nc = ler_nc(caminho_nc)
    cn = nc.columns
    cn_orig = nc.columns.copy()

    rpt("mapeando", 3, 8, "Mapeando colunas...")
    cd_nc = achar_col(cn, "Divisão")
    ci_nc = achar_col(cn, "ID Origem")
    cf_nc = achar_col(cn, "NotaFiscal")
    cm_nc = achar_col(cn, "Material")

    cd_z = achar_col(cz, "Divisão")
    co_z = achar_col(cz, "Documento")
    cs_z = achar_col(cz, "NF Saída")
    cm_z = achar_col(cz, "Material")
    vi2 = achar_col(cz, "Valor ICMS_2")
    ste = achar_col(cz, "Valor ST E")
    cfop = achar_col(cz, "CFOP")
    nfe = achar_col(cz, "NF Eletrôn")
    dte = achar_col(cz, "Data de En")
    dob = achar_col(cz, "Doc. Contá")
    forn = achar_col(cz, "Fornecedor")
    dof = co_z

    rpt("lendo", 3, 8, "Lendo ZTM...")
    ztm = pl.read_parquet(str(parquet_ztm),
                          columns=[cd_z, co_z, cs_z, cm_z, vi2, ste, cfop, nfe, dte, dob, forn])

    rpt("chaves", 4, 8, "Criando chaves...")
    nc = nc.with_columns(pl.concat_str([_ck(cd_nc), _ck(ci_nc), _ck(cf_nc), _ck0(cm_nc)], separator="_").alias("CHAVE"))
    ztm = ztm.with_columns(pl.concat_str([_ck(cd_z), _ck(co_z), _ck(cs_z), _ck0(cm_z)], separator="_").alias("CHAVE"))

    rpt("contagens", 5, 8, "Contando ocorrências...")
    ncc = nc.group_by("CHAVE").agg(pl.len().alias("cnt_nc"))
    ztc = ztm.group_by("CHAVE").agg(pl.len().alias("cnt_ztm"))
    ac = ncc.join(ztc, on="CHAVE", how="full").with_columns([pl.col("cnt_nc").fill_null(0), pl.col("cnt_ztm").fill_null(0)])

    zi = (ztm.join(ac, on="CHAVE", how="inner").group_by("CHAVE").agg([
        pl.first("cnt_nc").alias("cnt_nc"), pl.first("cnt_ztm").alias("cnt_ztm"),
        pl.col(forn).n_unique().alias("n_fornec"), pl.col(dte).n_unique().alias("n_data_ent")]))

    k1 = zi.filter((pl.col("cnt_nc") > 0) & (pl.col("cnt_nc") == pl.col("cnt_ztm"))).select("CHAVE")
    k2i = (zi.join(k1, on="CHAVE", how="anti")
           .filter((pl.col("cnt_nc") > 0) & (pl.col("cnt_ztm") > 0))
           .select("CHAVE", "n_fornec", "n_data_ent"))
    k2 = k2i.select("CHAVE")
    k2m = k2i.filter((pl.col("n_fornec") > 1) | (pl.col("n_data_ent") > 1)).select("CHAVE")

    rpt("mappings", 6, 8, f"Ch1: {k1.height} | Ch2: {k2.height}")
    m1 = _build_map(ztm, k1, vi2, ste, cfop, nfe, dte, dof, dob, "c1")
    m2 = _build_map(ztm, k2, vi2, ste, cfop, nfe, dte, dof, dob, "c2")

    rpt("joins", 7, 8, "Montando resultado...")
    s1, s2 = k1["CHAVE"], k2["CHAVE"]
    nj = nc.join(m1, on="CHAVE", how="left").join(m2, on="CHAVE", how="left")
    nj = nj.with_columns(
        pl.when(pl.col("CHAVE").is_in(s1)).then(pl.lit("1"))
        .when(pl.col("CHAVE").is_in(s2)).then(pl.lit("2"))
        .otherwise(None).alias("Chave_Conciliacao"))
    nj = nj.with_columns([
        pl.when(pl.col("Chave_Conciliacao") == "1").then(pl.col("CHAVE")).otherwise(None).alias("Chave_1_Join"),
        pl.when(pl.col("Chave_Conciliacao") == "2").then(pl.col("CHAVE")).otherwise(None).alias("Chave_2_Join")])

    def pk(a, b, al):
        return (pl.when(pl.col("Chave_Conciliacao") == "1").then(pl.col(a))
                .when(pl.col("Chave_Conciliacao") == "2").then(pl.col(b)).otherwise(None).alias(al))

    nj = nj.with_columns([pk("CF_c1", "CF_c2", "CFOP Saída ZTM"), pk("NE_c1", "NE_c2", "NF Entrada"),
                           pk("DE_c1", "DE_c2", "Data NF Entrada"), pk("DF_c1", "DF_c2", "Doc de faturamento"),
                           pk("DB_c1", "DB_c2", "Doc de Baixa")])

    ni = (nj.join(ac, on="CHAVE", how="left")
          .join(zi.select(["CHAVE", "n_fornec", "n_data_ent"]), on="CHAVE", how="left")
          .with_columns([pl.col("cnt_nc").fill_null(0), pl.col("cnt_ztm").fill_null(0),
                          pl.col("n_fornec").fill_null(0), pl.col("n_data_ent").fill_null(0)]))

    def vsel(s_sfx, sum_sfx, al):
        return (pl.when(pl.col("Chave_Conciliacao") == "1").then(
            pl.when((pl.col("cnt_nc") == 1) & (pl.col("cnt_ztm") == 1)).then(pl.col(f"V2_c1_s")).otherwise(pl.col(f"V2_c1_sum")))
                .when((pl.col("Chave_Conciliacao") == "2") & (pl.col("n_fornec") == 1) & (pl.col("n_data_ent") == 1))
                .then(pl.when((pl.col("cnt_nc") == 1) & (pl.col("cnt_ztm") == 1)).then(pl.col(f"V2_c2_s")).otherwise(pl.col(f"V2_c2_sum")))
                .otherwise(None).alias(al))

    def stsel(al):
        return (pl.when(pl.col("Chave_Conciliacao") == "1").then(
            pl.when((pl.col("cnt_nc") == 1) & (pl.col("cnt_ztm") == 1)).then(pl.col("ST_c1_s")).otherwise(pl.col("ST_c1_sum")))
                .when((pl.col("Chave_Conciliacao") == "2") & (pl.col("n_fornec") == 1) & (pl.col("n_data_ent") == 1))
                .then(pl.when((pl.col("cnt_nc") == 1) & (pl.col("cnt_ztm") == 1)).then(pl.col("ST_c2_s")).otherwise(pl.col("ST_c2_sum")))
                .otherwise(None).alias(al))

    ni = ni.with_columns([vsel("s", "sum", "Valor ICMS - Entrada ZTM"), stsel("Valor ICMS Sub Trib - Entrada ZTM")])

    ni = ni.with_columns([
        (pl.lit("'") + pl.col("cnt_nc").cast(pl.Utf8) + pl.lit(":") + pl.col("cnt_ztm").cast(pl.Utf8)).alias("Status_CNT_NC_ZTM"),
        pl.when(pl.col("Chave_Conciliacao").is_null() & pl.col(ci_nc).cast(pl.Utf8).str.strip_chars().is_in(["", "NULL", "None"]))
        .then(pl.lit("Sem ID Origem")).otherwise(None).alias("_o1"),
        pl.when(pl.col("Chave_Conciliacao").is_null() & (pl.col("cnt_nc") > 0) & (pl.col("cnt_ztm") > 0) & (pl.col("n_fornec") > 1))
        .then(pl.lit("Não conciliado por diferença no Fornecedor")).otherwise(None).alias("_o2"),
        pl.when(pl.col("Chave_Conciliacao").is_null() & (pl.col("cnt_nc") > 0) & (pl.col("cnt_ztm") > 0) & (pl.col("n_data_ent") > 1))
        .then(pl.lit("Não conciliado por diferença de Data de Entrada")).otherwise(None).alias("_o3"),
        pl.when((pl.col("Chave_Conciliacao") == "1") & (pl.col("_iz_c1") == True) & (pl.col("_ip_c2") == True))
        .then(pl.lit("Conciliado na Chave 1 com ICMS=0, Chave 2 teria ICMS>0")).otherwise(None).alias("_o4"),
        pl.when((pl.col("Chave_Conciliacao") == "2") & (pl.col("n_fornec") > 1))
        .then(pl.lit("Mais de um Fornecedor | Trazida a informação do mesmo jeito")).otherwise(None).alias("_o5"),
        pl.when((pl.col("Chave_Conciliacao") == "2") & (pl.col("n_data_ent") > 1))
        .then(pl.lit("Mais de uma Data de Entr | Trazida a informação do mesmo jeito")).otherwise(None).alias("_o6"),
    ])
    ni = ni.with_columns(pl.concat_str(["_o1", "_o2", "_o3", "_o4", "_o5", "_o6"], separator=" | ", ignore_nulls=True).alias("Obs"))
    ni = ni.drop(["_o1", "_o2", "_o3", "_o4", "_o5", "_o6"])

    cb = ni.columns
    sb = set(cb)
    nm = ni.filter((pl.col("Chave_Conciliacao") == "2") & ((pl.col("n_fornec") > 1) | (pl.col("n_data_ent") > 1)))

    if nm.height > 0:
        zm = ztm.join(k2m, on="CHAVE", how="inner").select(["CHAVE", vi2, ste, cfop, nfe, dte, dof, dob])
        nm = nm.with_columns(pl.int_range(0, pl.len()).over("CHAVE").cast(pl.Int64).alias("__nr"))
        zm = (zm.with_columns(pl.int_range(0, pl.len()).over("CHAVE").cast(pl.Int64).alias("__zr"))
              .join(ncc, on="CHAVE", how="left")
              .with_columns((pl.col("__zr") % pl.col("cnt_nc")).cast(pl.Int64).alias("__np")))
        ne = (nm.join(zm, left_on=["CHAVE", "__nr"], right_on=["CHAVE", "__np"], how="inner")
              .drop(["__nr", "__zr", "__np"], strict=False))
        ca = ne.columns

        def zz(n):
            return n + "_right" if n + "_right" in ca else n

        ne = ne.with_columns([
            pl.col(zz(vi2)).cast(pl.Utf8).alias("Valor ICMS - Entrada ZTM"),
            pl.col(zz(ste)).cast(pl.Utf8).alias("Valor ICMS Sub Trib - Entrada ZTM"),
            pl.col(zz(cfop)).alias("CFOP Saída ZTM"), pl.col(zz(nfe)).alias("NF Entrada"),
            pl.col(zz(dte)).alias("Data NF Entrada"), pl.col(zz(dof)).alias("Doc de faturamento"),
            pl.col(zz(dob)).alias("Doc de Baixa")])
        dr = [c for c in ne.columns if c not in sb]
        if dr:
            ne = ne.drop(dr)
        ne = ne.select(cb)
    else:
        ne = nm.select(cb)

    nr = ni.filter(~((pl.col("Chave_Conciliacao") == "2") & ((pl.col("n_fornec") > 1) | (pl.col("n_data_ent") > 1)))).select(cb)
    nf = pl.concat([nr, ne], how="vertical")

    nf = nf.with_row_count("_ig")
    dp = (nf.filter((pl.col("cnt_nc") > 1) & (
        (pl.col("Chave_Conciliacao") == "1") | ((pl.col("Chave_Conciliacao") == "2") & (pl.col("n_fornec") == 1) & (pl.col("n_data_ent") == 1))))
          .group_by("CHAVE").agg(pl.col("_ig").min().alias("_ik")))
    nf = nf.join(dp, on="CHAVE", how="left")
    nf = nf.with_columns(pl.when(pl.col("_ik").is_not_null() & (pl.col("_ig") != pl.col("_ik"))).then(True).otherwise(False).alias("_id"))
    nf = nf.with_columns([
        pl.when(pl.col("_id")).then(None).otherwise(pl.col("Valor ICMS - Entrada ZTM")).alias("Valor ICMS - Entrada ZTM"),
        pl.when(pl.col("_id")).then(None).otherwise(pl.col("Valor ICMS Sub Trib - Entrada ZTM")).alias("Valor ICMS Sub Trib - Entrada ZTM"),
        pl.when(pl.col("_id")).then(
            pl.when(pl.col("Obs").is_null() | (pl.col("Obs") == "")).then(pl.lit("Linha Duplicada - Sem Totais"))
            .otherwise(pl.col("Obs") + pl.lit(" | Linha Duplicada - Sem Totais"))).otherwise(pl.col("Obs")).alias("Obs")])

    rpt("razoes", 8, 8, "Processando Razões 222/223...")
    r2p, r3p = detectar_razoes_na_pasta(pasta_razoes)

    def pr(df_r):
        if df_r is None:
            return None
        cr = df_r.columns
        ci = achar_col(cr, "ID Origem")
        cm = achar_col(cr, "MontanteRazão")
        r = df_r.with_columns([pl.col(ci).cast(pl.Utf8).str.strip_chars().fill_null("").alias("__I"),
                                pl.col(cm).cast(pl.Utf8).alias("__M")]).select(["__I", "__M"])
        return (r.filter(pl.col("__I") != "").group_by("__I").agg([pl.len().alias("__C"), pl.col("__M").alias("__L")])
                .with_columns(pl.col("__L").map_elements(lambda l: d2br(soma_lista(l)), return_dtype=pl.Utf8).alias("__S"))
                .select(["__I", "__S", "__C"]))

    s2 = pr(ler_razao_csv(r2p))
    s3 = pr(ler_razao_csv(r3p))

    nf = nf.with_columns(pl.col(ci_nc).cast(pl.Utf8).str.strip_chars().fill_null("").alias("__IO"))
    if s2 is not None:
        s2 = s2.rename({"__S": "__S2", "__C": "__C2", "__I": "__IO"})
        nf = nf.join(s2, on="__IO", how="left")
    else:
        nf = nf.with_columns([pl.lit(None).cast(pl.Utf8).alias("__S2"), pl.lit(None).cast(pl.Int64).alias("__C2")])
    if s3 is not None:
        s3 = s3.rename({"__S": "__S3", "__C": "__C3", "__I": "__IO"})
        nf = nf.join(s3, on="__IO", how="left")
    else:
        nf = nf.with_columns([pl.lit(None).cast(pl.Utf8).alias("__S3"), pl.lit(None).cast(pl.Int64).alias("__C3")])

    pref = ((pl.col("Valor ICMS - Entrada ZTM").is_not_null() | pl.col("CFOP Saída ZTM").is_not_null()
             | pl.col("Chave_Conciliacao").is_not_null()) & (~pl.col("_id")))
    idk = (nf.filter(pl.col("__IO") != "").group_by("__IO").agg([
        pl.when(pref).then(pl.col("_ig")).otherwise(None).min().alias("__p"),
        pl.col("_ig").min().alias("__a")])
           .with_columns(pl.coalesce([pl.col("__p"), pl.col("__a")]).alias("__ki")).select(["__IO", "__ki"]))
    nf = nf.join(idk, on="__IO", how="left")
    cnd = (pl.col("__IO") != "") & pl.col("__ki").is_not_null() & (pl.col("_ig") == pl.col("__ki"))
    nf = nf.with_columns([
        pl.when(cnd).then(pl.col("__S2")).otherwise(None).alias("Valor no Razão 222"),
        pl.when(cnd).then(pl.col("__S3")).otherwise(None).alias("Valor no Razão 223"),
        pl.when(cnd).then(pl.col("__C2").cast(pl.Int64)).otherwise(None).alias("cnt_rz222"),
        pl.when(cnd).then(pl.col("__C3").cast(pl.Int64)).otherwise(None).alias("cnt_rz223")])

    novas = ["cnt_nc", "cnt_ztm", "cnt_rz222", "cnt_rz223",
             "Valor ICMS - Entrada ZTM", "Valor ICMS Sub Trib - Entrada ZTM",
             "CFOP Saída ZTM", "NF Entrada", "Data NF Entrada", "Doc de faturamento", "Doc de Baixa",
             "Valor no Razão 222", "Valor no Razão 223", "Chave_1_Join", "Chave_2_Join",
             "Chave_Conciliacao", "Status_CNT_NC_ZTM", "Obs"]
    co = [c for c in cn_orig if c not in novas] + novas
    co = [c for c in co if c in nf.columns]
    nfinal = nf.select(co)

    nb = Path(caminho_nc).stem
    op = pasta_destino / f"{nb}_COM_ZTM.parquet"
    oc = pasta_destino / f"{nb}_COM_ZTM.csv"
    nfinal.write_parquet(str(op), compression="zstd")
    nfinal.write_csv(str(oc), separator=";", null_value="", include_bom=True)

    st = nfinal.select([
        pl.col("Valor ICMS - Entrada ZTM").is_not_null().sum().alias("i"),
        pl.col("Valor ICMS Sub Trib - Entrada ZTM").is_not_null().sum().alias("s")]).row(0)

    return {
        "parquet_saida": str(op), "csv_saida": str(oc),
        "linhas_nc": nc.height, "linhas_nc_final": nfinal.height, "linhas_ztm": ztm.height,
        "chaves_1": k1.height, "chaves_2": k2.height,
        "preenchidos_icms": st[0], "preenchidos_st": st[1],
        "razao_222": str(r2p) if r2p else "Não encontrado",
        "razao_223": str(r3p) if r3p else "Não encontrado",
        "tempo_total": round(time.time() - t0, 2),
    }
