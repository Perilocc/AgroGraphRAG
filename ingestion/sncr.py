from pathlib import Path
import pandas as pd

COLUMN_MAPPING = {
    "CÓDIGO DO IMOVEL": "codigo_imovel",
    "DENOMIÇÃO DO IMÓVEL": "denominacao",
    "CÓDIGO DO MUNICÍPIO (IBGE)": "codigo_municipio",
    "MUNICÍPIO": "municipio",
    "UF": "uf",
    "ÁREA TOTAL": "area_total",
    "TITULAR": "titular",
    "NATUREZA JURÍDICA": "natureza_juridica",
    "CONDIÇÃO DA PESSOA": "condicao_pessoa",
    "PERCENTUAL DE DETENÇÃO": "percentual_detencao",
    "PAÍS": "pais",
}


def _normalize_sncr(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()

    missing = set(COLUMN_MAPPING) - set(df.columns)

    if missing:
        raise ValueError(f"Colunas ausentes no CSV: {missing}")

    df = df.rename(columns=COLUMN_MAPPING)

    for column in df.select_dtypes(include=["str"]):
        df[column] = df[column].str.strip()

    df["area_total"] = pd.to_numeric(
        df["area_total"].str.replace(",", ".", regex=False),
        errors="coerce",
    )

    df["percentual_detencao"] = pd.to_numeric(
        df["percentual_detencao"].str.replace(",", ".", regex=False),
        errors="coerce",
    )

    return df


def read_sncr(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        file_path,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
        dtype=str,
    )

    return _normalize_sncr(df)


def iter_sncr(file_path: Path, chunksize: int = 5000):
    if chunksize <= 0:
        raise ValueError("chunksize deve ser maior que zero.")

    reader = pd.read_csv(
        file_path,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
        dtype=str,
        chunksize=chunksize,
    )

    for chunk in reader:
        yield _normalize_sncr(chunk)
