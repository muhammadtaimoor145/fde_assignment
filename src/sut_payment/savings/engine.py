from __future__ import annotations

import pandas as pd

from .schemas import SavingsKpi
from .strategy import ActualSpendDiscountStrategy, SavingsStrategy
from .types import SavingsOutput


def _build_kpis(campaign_savings: pd.DataFrame) -> pd.DataFrame:
    total_estimated_savings = float(campaign_savings["estimated_savings_krw"].sum(skipna=True))
    calculable_count = int(campaign_savings["estimated_savings_krw"].notna().sum())
    missing_spend_count = int(campaign_savings["actual_spend_krw"].isna().sum())

    validated = SavingsKpi(
        total_estimated_savings_krw=total_estimated_savings,
        campaigns_with_calculable_savings=calculable_count,
        campaigns_missing_actual_spend=missing_spend_count,
    )
    return pd.DataFrame([validated.model_dump()])


def compute_savings(
    campaigns_clean: pd.DataFrame,
    partners_clean: pd.DataFrame,
    strategy: SavingsStrategy | None = None,
) -> SavingsOutput:
    selected_strategy = strategy or ActualSpendDiscountStrategy()
    partner_columns = ["partner_id", "partner_name", "discount_rate"]
    merged = campaigns_clean.merge(
        partners_clean[partner_columns],
        on="partner_id",
        how="left",
    )

    merged["savings_flags"] = ""
    missing_partner = merged["partner_name"].isna()
    missing_discount = merged["discount_rate"].isna()
    missing_spend = merged["actual_spend_krw"].isna()

    merged.loc[missing_partner, "savings_flags"] += "missing_partner_linkage;"
    merged.loc[missing_discount, "savings_flags"] += "missing_discount_rate;"
    merged.loc[missing_spend, "savings_flags"] += "missing_actual_spend;"

    merged["estimated_savings_krw"] = selected_strategy.compute(
        actual_spend=merged["actual_spend_krw"],
        discount_rate=merged["discount_rate"],
    )

    campaign_columns = [
        "campaign_id",
        "partner_id",
        "partner_name",
        "campaign_name",
        "actual_spend_krw",
        "discount_rate",
        "estimated_savings_krw",
        "savings_flags",
    ]
    campaign_savings = merged[campaign_columns].sort_values(
        "estimated_savings_krw",
        ascending=False,
        na_position="last",
    )

    partner_savings = (
        campaign_savings.groupby(["partner_id", "partner_name"], dropna=False)
        .agg(
            total_estimated_savings_krw=("estimated_savings_krw", "sum"),
            campaigns_with_savings=("estimated_savings_krw", lambda s: int(s.notna().sum())),
            campaigns_missing_spend=("actual_spend_krw", lambda s: int(s.isna().sum())),
        )
        .reset_index()
        .sort_values("total_estimated_savings_krw", ascending=False, na_position="last")
    )

    savings_kpis = _build_kpis(campaign_savings)
    return SavingsOutput(
        campaign_savings=campaign_savings.reset_index(drop=True),
        partner_savings=partner_savings.reset_index(drop=True),
        savings_kpis=savings_kpis,
    )
