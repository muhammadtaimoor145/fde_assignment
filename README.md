# SUT Payment Launch Rescue - MVP Dashboard

## 1) Problem Statement

Campaign operations and blockchain settlement data exist in separate systems:

Off-chain campaign operations data (CSV files) — contains campaign setup, expected spend, and operational status
On-chain SUT transaction data (mock blockchain logs) — contains actual payment execution details

Because of this separation, the operations team lacks visibility into the true settlement state when payments are processed via blockchain.

As a result:

Campaigns may appear healthy in operations dashboards
But actual settlement may be incomplete or broken, due to:
failed transactions
pending transactions
missing or incorrect wallet mappings
insufficient wallet balance

Additionally, operators cannot easily determine:

Whether a payment is fully completed or partially settled
How much settlement is still pending
What financial impact (cost or savings) is associated with using SUT.



## 2) Scope and Product Decisions

### In Scope

- Campaign-level savings estimation
- Risk detection and triage view
- Action recommendations for operators
- Campaign-first UI for easy operations usage

### Out of Scope

- Real-time chain integration / RPC
- Authentication / production workflow tooling
- Smart contract deployment

### Solution

This solution focuses on three business questions:

1. How much could each campaign save if it used SUT settlement?
2. Which campaigns are at risk today because of failed payment, pending settlement, wallet mapping issues, or low balance?
3. What should operations do next for highest-risk campaigns?

### Key Product Choice

Reconciliation-heavy UI was intentionally removed from the final front-end flow to keep operator experience focused on the 3 core challenge questions.

## 3) Architecture Overview

The code is structured into small, modular layers:

- `src/sut_payment/cleaning.py` + `src/sut_payment/cleaners/*`
  - Data ingestion and normalization
- `src/sut_payment/savings/*`
  - Savings logic
- `src/sut_payment/risk/*`
  - Risk detection, priority scoring, actions, AI-enhanced explanation
- `src/sut_payment/app.py`
  - Streamlit presentation layer

## 4) Data Model / Object Model

The system is built around these business objects:

- **Partner**
  - `partner_id`, `partner_name`, `discount_rate`, metadata
- **Campaign**
  - `campaign_id`, `partner_id`, `campaign_name`, `actual_spend_krw`, `required_sut_amount`, status fields
- **Wallet**
  - `partner_id`, `wallet_address`, `is_primary`, KYC/connection fields
- **SUTTransaction**
  - `tx_hash`, `campaign_id`, `status`, `sut_amount`, timestamps
- **Balance** (support object)
  - `wallet_address`, `sut_balance`

Core relationships:

- Partner 1 -> many Campaigns
- Partner 1 -> many Wallet rows (cleaning picks canonical wallet)
- Campaign 1 -> many Transactions
- Wallet -> Balance via wallet address

## 5) Data Cleaning Process and Decisions

Cleaning is deterministic and occurs before any business calculation.

### Inputs

- `partners.csv`
- `campaigns.csv`
- `wallets.csv`
- `sut_transactions.jsonl`
- `mock_balances.json`

### Cleaning Rules

- Normalize numeric fields (remove commas, cast safely)
- Normalize dates/timestamps (`BAD_DATE` -> null)
- Normalize text/status values (trim, lowercase where required)
- Deduplicate campaign records by `campaign_id` (prefer latest sync)
- Deduplicate transactions by `tx_hash` with fallback composite key for blank hash
- Canonical wallet selection per partner:
  - prefer valid primary wallet
  - otherwise fallback to latest valid wallet

### Why This Matters

Without this layer, savings and risk outputs are unstable due to duplicates, invalid formats, and mixed datatypes.

## 6) Savings Logic

Implemented in `src/sut_payment/savings/engine.py`.

### Formula

`estimated_savings_krw = actual_spend_krw * discount_rate`

### Flow

1. Join campaign with partner on `partner_id`
2. Validate partner linkage and discount presence
3. Calculate campaign-level savings
4. Aggregate partner-level savings
5. Surface KPI metrics

### Why This Decision

This follows business clarification that savings are based on **actual spend**, not budget.

## 7) Risk Logic

Implemented in `src/sut_payment/risk/engine.py`.

### Campaign transaction summary metrics

- `failed_tx_count`
- `pending_tx_count`
- `confirmed_tx_count`
- `confirmed_sut_amount`

### Risk categories and criteria

- **failed payment**
  - `failed_tx_count > 0`
- **pending settlement**
  - `pending_tx_count > 0`, or partial settlement (`0 < confirmed_sut_amount < required_sut_amount`)
- **wallet issue**
  - missing wallet mapping, or invalid wallet format
- **low balance**
  - `sut_balance < required_sut_amount`
- **unstarted settlement**
  - required SUT exists but no confirmed settlement (`confirmed_tx_count == 0`)

### Severity

Severity is rule-based (not ML) and assigned from triggered reason keys (see `src/sut_payment/risk/severity.py`):

- `high` if any high-critical key is present:
  - `missing_wallet_mapping`
  - `invalid_wallet_address`
  - `failed_transaction`
  - `low_sut_balance`
- `medium` if campaign has risk reasons but none of the high-critical keys
  - typical examples: `pending_settlement`, `unstarted_settlement`
- `low` if no risk reason is triggered

Implementation logic:

- if reasons list is empty -> `low`
- else if any reason exists in `HIGH_REASONS` -> `high`
- else -> `medium`

### Priority and Top Risky Ranking

Added explicit priority outputs:

- `risk_priority_score`
- `action_priority` (`Immediate`, `Today`, `Monitor`)

Top risky campaigns are sorted by severity + priority score so the ops queue is explicit.

## 8) Next Actions Logic

Base deterministic actions are mapped by reason key in `src/sut_payment/risk/actions.py`.

To increase trust and readability, backend also supports AI-enhanced reason/action text generation (with safe fallback).

## 9) AI Model Usage

AI is used in backend risk layer to generate user-friendly:

- `risk_reasons` text
- `recommended_next_action` text

Configuration from `.env`:

- `OPENAI_API_KEY` or `api_key`
- `OPENAI_MODEL` or `model` (example: `gpt-4.1-nano`)

Fallback behavior:

- If model call fails or env is missing, deterministic rule-based text is used.

## 10) Front-End Workflow

Streamlit app (`src/sut_payment/app.py`) is campaign-first:

1. Filter by risk category (Failed, Pending, Wallet Issues, Low Balance, Risk-Free)
2. Select campaign
3. View:
   - savings impact
   - risk reason + next action
   - top risky campaigns panel with ranked priority

This design was chosen to make operator decisions immediate and understandable.

## 11) Why These Decisions Are Defensible

- Keep business logic deterministic for trust and auditability
- Use AI only for explanation quality, not core scoring truth
- Explicit top-risk ranking satisfies "top risky campaigns" requirement
- Campaign-first UX reduces ambiguity for operators

## 12) Project Structure

```text
sut_payment/
  src/sut_payment/
    app.py
    cleaning.py
    cleaners/
    savings/
    risk/
  requirements.txt
  pyproject.toml
  RISK_IDENTIFICATION_RULES.md
```

## 13) Run Instructions

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
streamlit run .\src\sut_payment\app.py
```
