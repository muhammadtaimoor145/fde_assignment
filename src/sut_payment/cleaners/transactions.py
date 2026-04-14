from __future__ import annotations

import pandas as pd

from ..models import DataQualityIssue
from ..normalizers import as_datetime, as_number, as_text
from ..quality import issue
from .constants import VALID_TX_STATUSES


def clean_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
    issues: list[DataQualityIssue] = []
    out = df.copy()

    for col in ("tx_hash", "wallet_address", "merchant_wallet", "status", "campaign_id", "chain"):
        out[col] = as_text(out[col])
    out["sut_amount"] = as_number(out["sut_amount"])
    out["krw_equivalent"] = as_number(out["krw_equivalent"])
    out["block_timestamp"] = as_datetime(out["block_timestamp"])
    out["status"] = out["status"].str.lower()
    out["data_quality_flags"] = ""

    invalid_status = ~out["status"].isin(VALID_TX_STATUSES)
    invalid_timestamp = out["block_timestamp"].isna()
    blank_hash = out["tx_hash"] == ""
    blank_wallet = out["wallet_address"] == ""

    out.loc[invalid_status, "data_quality_flags"] += "invalid_tx_status;"
    out.loc[invalid_timestamp, "data_quality_flags"] += "invalid_block_timestamp;"
    out.loc[blank_hash, "data_quality_flags"] += "blank_tx_hash;"
    out.loc[blank_wallet, "data_quality_flags"] += "blank_wallet_address;"

    for campaign_id in out.loc[invalid_status, "campaign_id"]:
        issues.append(issue("transactions", campaign_id, "invalid_tx_status", "kept_with_flag"))
    for campaign_id in out.loc[invalid_timestamp, "campaign_id"]:
        issues.append(issue("transactions", campaign_id, "invalid_block_timestamp", "kept_with_flag"))
    for campaign_id in out.loc[blank_hash, "campaign_id"]:
        issues.append(issue("transactions", campaign_id, "blank_tx_hash", "used_composite_key"))
    for campaign_id in out.loc[blank_wallet, "campaign_id"]:
        issues.append(issue("transactions", campaign_id, "blank_wallet_address", "kept_with_flag"))

    composite_key = (
        out["campaign_id"]
        + "::"
        + out["wallet_address"]
        + "::"
        + out["sut_amount"].astype(str)
        + "::"
        + out["status"]
        + "::"
        + out["block_timestamp"].astype(str)
    )
    effective_key = out["tx_hash"].where(out["tx_hash"] != "", composite_key)
    duplicate_key = effective_key.duplicated(keep=False)
    for campaign_id in out.loc[duplicate_key, "campaign_id"]:
        issues.append(issue("transactions", campaign_id, "duplicate_transaction", "deduplicated_keep_last"))

    out = (
        out.assign(_effective_key=effective_key)
        .drop_duplicates(subset=["_effective_key"], keep="last")
        .drop(columns=["_effective_key"])
        .reset_index(drop=True)
    )
    return out, issues

