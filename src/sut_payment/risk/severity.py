from __future__ import annotations


HIGH_REASONS = {
    "missing_wallet_mapping",
    "invalid_wallet_address",
    "failed_transaction",
    "low_sut_balance",
}


def assign_severity(reasons: list[str]) -> str:
    if not reasons:
        return "low"
    if any(reason in HIGH_REASONS for reason in reasons):
        return "high"
    return "medium"
