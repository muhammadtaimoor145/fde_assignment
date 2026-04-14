from __future__ import annotations

import pandas as pd

from .schemas import ReconciliationKpis
from .types import ReconciliationOutput


def _confirmed_aggregates(transactions_clean: pd.DataFrame) -> pd.DataFrame:
    confirmed = transactions_clean[transactions_clean["status"] == "confirmed"].copy()
    if confirmed.empty:
        return pd.DataFrame(
            columns=["campaign_id", "confirmed_sut_amount", "confirmed_krw_equivalent"]
        )
    return (
        confirmed.groupby("campaign_id", dropna=False)
        .agg(
            confirmed_sut_amount=("sut_amount", "sum"),
            confirmed_krw_equivalent=("krw_equivalent", "sum"),
        )
        .reset_index()
    )


def _tx_status_counts(transactions_clean: pd.DataFrame) -> pd.DataFrame:
    tx = transactions_clean.copy()
    return (
        tx.groupby("campaign_id", dropna=False)
        .agg(
            failed_tx_count=("status", lambda s: int((s == "failed").sum())),
            pending_tx_count=("status", lambda s: int((s == "pending").sum())),
        )
        .reset_index()
    )


def compute_reconciliation(
    campaigns_clean: pd.DataFrame,
    transactions_clean: pd.DataFrame,
) -> ReconciliationOutput:
    confirmed_agg = _confirmed_aggregates(transactions_clean)
    tx_counts = _tx_status_counts(transactions_clean)

    merged = campaigns_clean.merge(confirmed_agg, on="campaign_id", how="left")
    merged = merged.merge(tx_counts, on="campaign_id", how="left")
    merged["confirmed_sut_amount"] = merged["confirmed_sut_amount"].fillna(0.0)
    merged["confirmed_krw_equivalent"] = merged["confirmed_krw_equivalent"].fillna(0.0)
    merged["failed_tx_count"] = merged["failed_tx_count"].fillna(0).astype(int)
    merged["pending_tx_count"] = merged["pending_tx_count"].fillna(0).astype(int)

    required = merged["required_sut_amount"]
    confirmed = merged["confirmed_sut_amount"]
    merged["settlement_coverage_ratio"] = (confirmed / required).where(required > 0)
    merged["reconciliation_gap_sut"] = required - confirmed

    merged["expected_krw_equivalent"] = merged["actual_spend_krw"]
    merged["reconciliation_gap_krw_equivalent"] = (
        merged["expected_krw_equivalent"] - merged["confirmed_krw_equivalent"]
    )

    merged["settlement_state"] = "fully_settled"
    merged.loc[merged["reconciliation_gap_sut"] > 0, "settlement_state"] = "under_settled"
    merged.loc[merged["reconciliation_gap_sut"] < 0, "settlement_state"] = "over_settled"

    merged["urgency"] = "normal"
    urgent_mask = (
        (merged["reconciliation_gap_sut"] > 0)
        & ((merged["failed_tx_count"] > 0) | (merged["pending_tx_count"] > 0))
    )
    merged.loc[urgent_mask, "urgency"] = "high"

    reconciliation_table = merged[
        [
            "campaign_id",
            "partner_id",
            "campaign_name",
            "required_sut_amount",
            "confirmed_sut_amount",
            "settlement_coverage_ratio",
            "reconciliation_gap_sut",
            "expected_krw_equivalent",
            "confirmed_krw_equivalent",
            "reconciliation_gap_krw_equivalent",
            "settlement_state",
            "urgency",
            "failed_tx_count",
            "pending_tx_count",
        ]
    ].sort_values(
        ["urgency", "reconciliation_gap_sut"],
        ascending=[False, False],
        na_position="last",
    )

    kpis = ReconciliationKpis(
        under_settled_campaign_count=int((reconciliation_table["settlement_state"] == "under_settled").sum()),
        total_unresolved_sut_gap=float(
            reconciliation_table.loc[
                reconciliation_table["reconciliation_gap_sut"] > 0, "reconciliation_gap_sut"
            ].sum()
        ),
        average_settlement_coverage_ratio=float(
            reconciliation_table["settlement_coverage_ratio"].dropna().mean()
            if reconciliation_table["settlement_coverage_ratio"].notna().any()
            else 0.0
        ),
    )

    return ReconciliationOutput(
        reconciliation_table=reconciliation_table.reset_index(drop=True),
        reconciliation_kpis=pd.DataFrame([kpis.model_dump()]),
    )
