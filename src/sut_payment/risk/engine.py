from __future__ import annotations

import re

import pandas as pd

from .actions import action_for_reason
from .ai_guidance import generate_ai_risk_fields
from .severity import assign_severity
from .types import RiskOutput

WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _campaign_tx_summary(transactions_clean: pd.DataFrame) -> pd.DataFrame:
    tx = transactions_clean.copy()

    def count_status(series: pd.Series, target: str) -> int:
        return int((series == target).sum())

    summary = (
        tx.groupby("campaign_id", dropna=False)
        .agg(
            failed_tx_count=("status", lambda s: count_status(s, "failed")),
            pending_tx_count=("status", lambda s: count_status(s, "pending")),
            confirmed_tx_count=("status", lambda s: count_status(s, "confirmed")),
        )
        .reset_index()
    )
    return summary


def _build_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    wallet = str(row.get("wallet_address", "") or "").strip()
    wallet_missing = wallet == ""
    wallet_invalid = (not wallet_missing) and (WALLET_PATTERN.fullmatch(wallet) is None)

    if wallet_missing:
        reasons.append("missing_wallet_mapping")
    if wallet_invalid:
        reasons.append("invalid_wallet_address")
    if int(row.get("failed_tx_count", 0) or 0) > 0:
        reasons.append("failed_transaction")
    if int(row.get("pending_tx_count", 0) or 0) > 0:
        reasons.append("pending_settlement")
    confirmed_count = int(row.get("confirmed_tx_count", 0) or 0)
    required_sut = row.get("required_sut_amount")
    confirmed_sut_amount = row.get("confirmed_sut_amount")
    if (
        pd.notna(required_sut)
        and pd.notna(confirmed_sut_amount)
        and float(required_sut) > 0
        and 0 < float(confirmed_sut_amount) < float(required_sut)
        and "pending_settlement" not in reasons
    ):
        reasons.append("pending_settlement")
    if pd.notna(required_sut) and float(required_sut) > 0 and confirmed_count == 0:
        reasons.append("unstarted_settlement")

    balance = row.get("sut_balance")
    if pd.notna(required_sut) and pd.notna(balance) and float(balance) < float(required_sut):
        reasons.append("low_sut_balance")

    return reasons


def _build_recommended_actions(reasons: list[str]) -> list[str]:
    unique_actions: list[str] = []
    for reason in reasons:
        action = action_for_reason(reason)
        if action not in unique_actions:
            unique_actions.append(action)
    return unique_actions


def _apply_ai_reason_action(risky: pd.DataFrame) -> pd.DataFrame:
    if risky.empty:
        return risky

    risk_reasons_out: list[str] = []
    next_actions_out: list[str] = []
    for _, row in risky.iterrows():
        fallback_reasons = "; ".join(row["risk_reasons"])
        fallback_actions = " | ".join(row["recommended_next_actions"])
        context = {
            "campaign_id": row["campaign_id"],
            "campaign_name": row["campaign_name"],
            "severity": row["severity"],
            "risk_reason_keys": fallback_reasons,
            "failed_tx_count": int(row["failed_tx_count"]),
            "pending_tx_count": int(row["pending_tx_count"]),
            "confirmed_tx_count": int(row["confirmed_tx_count"]),
            "required_sut_amount": float(row["required_sut_amount"])
            if pd.notna(row["required_sut_amount"])
            else None,
            "confirmed_sut_amount": float(row["confirmed_sut_amount"])
            if pd.notna(row["confirmed_sut_amount"])
            else None,
        }
        ai_fields = generate_ai_risk_fields(context)
        if ai_fields is None:
            risk_reasons_out.append(fallback_reasons)
            next_actions_out.append(fallback_actions)
        else:
            ai_reasons, ai_actions = ai_fields
            risk_reasons_out.append(ai_reasons)
            next_actions_out.append(ai_actions)

    risky["risk_reasons"] = risk_reasons_out
    risky["recommended_next_action"] = next_actions_out
    return risky


def _action_priority_from_severity(severity: str) -> str:
    if severity == "high":
        return "Immediate"
    if severity == "medium":
        return "Today"
    return "Monitor"


def _compute_priority_score(row: pd.Series) -> float:
    severity_weight = {"high": 3.0, "medium": 2.0, "low": 1.0}
    base = severity_weight.get(str(row.get("severity", "low")), 1.0) * 100.0
    required = float(row.get("required_sut_amount") or 0.0)
    failed = float(row.get("failed_tx_count") or 0.0) * 30.0
    pending = float(row.get("pending_tx_count") or 0.0) * 15.0
    reason_count = float(row.get("risk_reason_count") or 0.0) * 10.0
    return base + (required / 100.0) + failed + pending + reason_count


def compute_risks(
    campaigns_clean: pd.DataFrame,
    wallets_clean: pd.DataFrame,
    transactions_clean: pd.DataFrame,
    balances_clean: pd.DataFrame,
) -> RiskOutput:
    tx_summary = _campaign_tx_summary(transactions_clean)
    confirmed_sut = (
        transactions_clean[transactions_clean["status"] == "confirmed"]
        .groupby("campaign_id", dropna=False)["sut_amount"]
        .sum()
        .reset_index(name="confirmed_sut_amount")
    )
    merged = campaigns_clean.merge(
        wallets_clean[["partner_id", "wallet_address"]],
        on="partner_id",
        how="left",
    )
    merged = merged.merge(
        balances_clean[["wallet_address", "sut_balance"]],
        on="wallet_address",
        how="left",
    )
    merged = merged.merge(tx_summary, on="campaign_id", how="left")
    merged = merged.merge(confirmed_sut, on="campaign_id", how="left")

    for column in ("failed_tx_count", "pending_tx_count", "confirmed_tx_count"):
        merged[column] = merged[column].fillna(0).astype(int)
    merged["confirmed_sut_amount"] = merged["confirmed_sut_amount"].fillna(0.0)

    merged["risk_reasons"] = merged.apply(_build_reasons, axis=1)
    merged["risk_reason_keys"] = merged["risk_reasons"].apply(lambda items: "; ".join(items))
    merged["severity"] = merged["risk_reasons"].apply(assign_severity)
    merged["recommended_next_actions"] = merged["risk_reasons"].apply(_build_recommended_actions)
    merged["risk_reason_count"] = merged["risk_reasons"].apply(len)

    risky = merged[merged["risk_reason_count"] > 0].copy()
    risky = _apply_ai_reason_action(risky)
    risky["risk_priority_score"] = risky.apply(_compute_priority_score, axis=1)
    risky["action_priority"] = risky["severity"].apply(_action_priority_from_severity)

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    risky["severity_rank"] = risky["severity"].map(severity_rank).fillna(0)
    top_risky_campaigns = risky.sort_values(
        ["severity_rank", "risk_priority_score", "risk_reason_count", "required_sut_amount"],
        ascending=[False, False, False, False],
        na_position="last",
    )[
        [
            "campaign_id",
            "partner_id",
            "campaign_name",
            "severity",
            "action_priority",
            "risk_priority_score",
            "risk_reason_keys",
            "risk_reasons",
            "recommended_next_action",
            "failed_tx_count",
            "pending_tx_count",
            "confirmed_tx_count",
        ]
    ].reset_index(drop=True)

    reason_distribution = (
        risky.assign(reason=risky["risk_reason_keys"].str.split("; "))
        .explode("reason")
        .groupby(["severity", "reason"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["severity", "count"], ascending=[True, False])
        .reset_index(drop=True)
    )

    return RiskOutput(
        top_risky_campaigns=top_risky_campaigns,
        risk_distribution=reason_distribution,
    )
