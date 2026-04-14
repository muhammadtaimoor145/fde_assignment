from __future__ import annotations

import pandas as pd

from ..models import DataQualityIssue
from ..normalizers import as_datetime, as_number, as_text
from ..quality import issue
from .constants import WALLET_PATTERN


def clean_balances(df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
    issues: list[DataQualityIssue] = []
    out = df.copy()
    out["wallet_address"] = as_text(out["wallet_address"])
    out["sut_balance"] = as_number(out["sut_balance"])
    out["discount_rate"] = as_number(out["discount_rate"])
    out["last_updated"] = as_datetime(out["last_updated"])
    out["data_quality_flags"] = ""

    invalid_wallet = ~out["wallet_address"].str.match(WALLET_PATTERN, na=False)
    out.loc[invalid_wallet, "data_quality_flags"] += "invalid_wallet_address;"
    for wallet_address in out.loc[invalid_wallet, "wallet_address"]:
        issues.append(issue("balances", wallet_address, "invalid_wallet_address", "kept_with_flag"))

    out = (
        out.sort_values("last_updated", ascending=False, na_position="last")
        .drop_duplicates(subset=["wallet_address"], keep="first")
        .reset_index(drop=True)
    )
    return out, issues

