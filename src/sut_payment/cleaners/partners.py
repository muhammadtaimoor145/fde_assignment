from __future__ import annotations

import pandas as pd

from ..models import DataQualityIssue
from ..normalizers import as_number, as_text
from ..quality import issue


def clean_partners(df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
    issues: list[DataQualityIssue] = []
    out = df.copy()
    out["partner_id"] = as_text(out["partner_id"])
    out["partner_name"] = as_text(out["partner_name"])
    out["discount_rate"] = as_number(out["discount_rate"])
    out["status"] = as_text(out["status"]).str.lower()
    out["data_quality_flags"] = ""

    missing_discount = out["discount_rate"].isna()
    out.loc[missing_discount, "data_quality_flags"] += "missing_discount_rate;"
    for partner_id in out.loc[missing_discount, "partner_id"]:
        issues.append(issue("partners", partner_id, "missing_discount_rate", "kept_with_flag"))

    return out, issues

