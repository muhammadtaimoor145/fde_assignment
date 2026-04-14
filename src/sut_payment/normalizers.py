from __future__ import annotations

import pandas as pd


def as_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().replace({"nan": "", "None": ""})


def as_number(series: pd.Series) -> pd.Series:
    cleaned = as_text(series).str.replace(",", "", regex=False).replace({"": pd.NA})
    return pd.to_numeric(cleaned, errors="coerce")


def as_datetime(series: pd.Series) -> pd.Series:
    cleaned = as_text(series).replace({"BAD_DATE": pd.NA, "": pd.NA})
    return pd.to_datetime(cleaned, errors="coerce")
