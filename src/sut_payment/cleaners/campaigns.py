from __future__ import annotations

import pandas as pd

from ..models import DataQualityIssue
from ..normalizers import as_datetime, as_number, as_text
from ..quality import issue


def clean_campaigns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
    issues: list[DataQualityIssue] = []
    out = df.copy()
    for col in ("campaign_id", "partner_id", "campaign_name", "booking_status"):
        out[col] = as_text(out[col])
    out["budget_krw"] = as_number(out["budget_krw"])
    out["actual_spend_krw"] = as_number(out["actual_spend_krw"])
    out["required_sut_amount"] = as_number(out["required_sut_amount"])
    out["start_date"] = as_datetime(out["start_date"])
    out["end_date"] = as_datetime(out["end_date"])
    out["last_sync_at"] = as_datetime(out["last_sync_at"])
    out["booking_status"] = out["booking_status"].str.lower()
    out["data_quality_flags"] = ""

    invalid_start = out["start_date"].isna()
    out.loc[invalid_start, "data_quality_flags"] += "invalid_start_date;"
    for campaign_id in out.loc[invalid_start, "campaign_id"]:
        issues.append(issue("campaigns", campaign_id, "invalid_start_date", "kept_with_flag"))

    missing_spend = out["actual_spend_krw"].isna()
    out.loc[missing_spend, "data_quality_flags"] += "missing_actual_spend;"
    for campaign_id in out.loc[missing_spend, "campaign_id"]:
        issues.append(issue("campaigns", campaign_id, "missing_actual_spend", "kept_with_flag"))

    duplicate_campaign = out.duplicated(subset=["campaign_id"], keep=False)
    for campaign_id in out.loc[duplicate_campaign, "campaign_id"]:
        issues.append(issue("campaigns", campaign_id, "duplicate_campaign_id", "kept_latest_sync"))

    out = (
        out.sort_values("last_sync_at", ascending=False, na_position="last")
        .drop_duplicates(subset=["campaign_id"], keep="first")
        .reset_index(drop=True)
    )
    return out, issues

