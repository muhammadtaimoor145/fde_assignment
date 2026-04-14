from __future__ import annotations

ACTION_MAP = {
    "missing_wallet_mapping": "Request a primary partner wallet and block settlement until mapped.",
    "invalid_wallet_address": "Validate wallet format and replace with an approved address.",
    "failed_transaction": "Pause settlement for this campaign, identify the failed transaction root cause, and retry only after validation checks pass.",
    "pending_settlement": "Monitor pending transaction and escalate if pending beyond threshold.",
    "low_sut_balance": "Request immediate SUT top-up to cover required settlement before the next retry.",
    "unstarted_settlement": "No confirmed settlement found. Initiate first settlement transaction and monitor confirmation.",
    "severe_data_quality_issue": "Resolve duplicate/invalid campaign or transaction records first, then rerun settlement reconciliation.",
}


def action_for_reason(reason: str) -> str:
    return ACTION_MAP.get(reason, "Investigate campaign details and resolve before settlement.")
