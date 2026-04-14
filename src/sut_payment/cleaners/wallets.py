from __future__ import annotations

import pandas as pd

from ..models import DataQualityIssue
from ..normalizers import as_datetime, as_text
from ..quality import issue
from .constants import WALLET_PATTERN


def clean_wallets(df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
    issues: list[DataQualityIssue] = []
    out = df.copy()
    out["partner_id"] = as_text(out["partner_id"])
    out["wallet_address"] = as_text(out["wallet_address"])
    out["kyc_status"] = as_text(out["kyc_status"]).str.lower()
    out["is_primary"] = as_text(out["is_primary"]).str.lower()
    out["connected_at"] = as_datetime(out["connected_at"])
    out["data_quality_flags"] = ""

    missing_wallet = out["wallet_address"] == ""
    invalid_wallet = ~out["wallet_address"].str.match(WALLET_PATTERN, na=False) & ~missing_wallet
    out.loc[missing_wallet, "data_quality_flags"] += "missing_wallet_address;"
    out.loc[invalid_wallet, "data_quality_flags"] += "invalid_wallet_address;"

    for partner_id in out.loc[missing_wallet, "partner_id"]:
        issues.append(issue("wallets", partner_id, "missing_wallet_address", "kept_with_flag"))
    for _, row in out.loc[invalid_wallet, ["partner_id", "wallet_address"]].iterrows():
        issues.append(
            issue(
                "wallets",
                f"{row['partner_id']}::{row['wallet_address']}",
                "invalid_wallet_address",
                "kept_with_flag",
            )
        )

    selected_rows = []
    for partner_id, group in out.groupby("partner_id", dropna=False):
        primary_valid = group[
            (group["is_primary"] == "true")
            & group["wallet_address"].str.match(WALLET_PATTERN, na=False)
        ]
        if not primary_valid.empty:
            selected = primary_valid.sort_values("connected_at", ascending=False).iloc[0]
        else:
            any_valid = group[group["wallet_address"].str.match(WALLET_PATTERN, na=False)]
            if any_valid.empty:
                selected = group.sort_values("connected_at", ascending=False).iloc[0]
                issues.append(issue("wallets", partner_id, "no_valid_wallet", "kept_latest_wallet"))
            else:
                selected = any_valid.sort_values("connected_at", ascending=False).iloc[0]
                issues.append(
                    issue(
                        "wallets",
                        partner_id,
                        "missing_valid_primary_wallet",
                        "fallback_latest_valid_wallet",
                    )
                )
        selected_rows.append(selected)

    wallets_clean = pd.DataFrame(selected_rows).reset_index(drop=True)
    return wallets_clean, issues

