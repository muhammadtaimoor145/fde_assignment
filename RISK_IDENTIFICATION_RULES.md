# Risk Identification Rules

This document explains how the app classifies campaigns into:

- failed payment
- pending settlement
- wallet issue
- low balance
- risk-free

These rules are implemented in `src/sut_payment/risk/engine.py` and `src/sut_payment/risk/actions.py`.

## 1) Data Inputs Used

Risk detection is campaign-level and uses:

- `campaigns_clean`
  - `campaign_id`
  - `required_sut_amount`
  - `data_quality_flags`
- `wallets_clean`
  - `partner_id`
  - `wallet_address`
- `transactions_clean`
  - `campaign_id`
  - `status`
  - `sut_amount`
  - `data_quality_flags`
- `balances_clean`
  - `wallet_address`
  - `sut_balance`

## 2) Transaction Summary Built Per Campaign

For each campaign, the engine computes:

- `failed_tx_count`
- `pending_tx_count`
- `confirmed_tx_count`
- `tx_quality_issue_count`
- `confirmed_sut_amount` (sum of `sut_amount` where `status == "confirmed"`)

## 3) Rule Definitions by Category

### A) Failed Payment

Campaign is flagged as failed when:

- `failed_tx_count > 0`

Internal reason key:

- `failed_transaction`

## B) Pending Settlement

Campaign is flagged as pending when either:

1. It has on-chain pending tx:
   - `pending_tx_count > 0`
2. It is partially settled:
   - `required_sut_amount > 0`
   - `0 < confirmed_sut_amount < required_sut_amount`

Internal reason key:

- `pending_settlement`

## C) Wallet Issue

Wallet issue includes two cases:

1. Missing wallet mapping:
   - wallet address is empty
   - reason: `missing_wallet_mapping`
2. Invalid wallet format:
   - wallet does not match `0x` + 40 hex characters
   - reason: `invalid_wallet_address`

In the app sidebar, the "Wallet Issues" button checks for either of these reason keys.

## D) Low Balance

Campaign is flagged for low balance when:

- `required_sut_amount` is present
- `sut_balance` is present
- `sut_balance < required_sut_amount`

Internal reason key:

- `low_sut_balance`

## E) Additional Risk Rule (Operational)

Campaign is flagged as unstarted settlement when:

- `required_sut_amount > 0`
- `confirmed_tx_count == 0`

Internal reason key:

- `unstarted_settlement`

This prevents campaigns with required settlement but no confirmed tx from appearing risk-free.

## F) Data-Quality Risk

Campaign is flagged for severe data quality issue when:

- campaign `data_quality_flags` is non-empty
  OR
- `tx_quality_issue_count > 0`

Internal reason key:

- `severe_data_quality_issue`

## 4) Severity Logic

Severity is assigned from reason keys:

- `high` if any of:
  - `missing_wallet_mapping`
  - `invalid_wallet_address`
  - `failed_transaction`
  - `low_sut_balance`
  - `severe_data_quality_issue`
- `medium` if campaign has risk reasons but none of the high list
- `low` if no risk reasons

Implemented in `src/sut_payment/risk/severity.py`.

## 5) Risk-Free Definition

A campaign is risk-free in the app when:

- it is NOT present in `top_risky_campaigns`
- equivalently, its computed `risk_reasons` list is empty

Sidebar button "Risk-Free Campaigns" returns:

- `all campaign_ids from campaign_savings`
- minus `campaign_ids present in top_risky_campaigns`

## 6) Action Mapping

For every risk reason, action text is mapped in:

- `src/sut_payment/risk/actions.py`

Examples:

- `failed_transaction` -> pause settlement, investigate root cause, retry after validation
- `pending_settlement` -> monitor and escalate beyond threshold
- `low_sut_balance` -> request immediate top-up
- `severe_data_quality_issue` -> resolve invalid/duplicate records first

