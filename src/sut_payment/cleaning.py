from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cleaners.balances import clean_balances
from .cleaners.campaigns import clean_campaigns
from .cleaners.partners import clean_partners
from .cleaners.transactions import clean_transactions
from .cleaners.wallets import clean_wallets
from .io import load_csv, load_json, load_jsonl
from .models import CleanedDataBundle
from .quality import issues_to_df, summarize_issues
from .types import CleanOutput


def load_and_clean(data_dir: Path) -> CleanOutput:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data folder not found: {data_dir}")

    partners_raw = load_csv(data_dir / "partners.csv")
    campaigns_raw = load_csv(data_dir / "campaigns.csv")
    wallets_raw = load_csv(data_dir / "wallets.csv")
    transactions_raw = load_jsonl(data_dir / "sut_transactions.jsonl")
    balances_raw = pd.DataFrame(load_json(data_dir / "mock_balances.json"))

    partners_clean, p_issues = clean_partners(partners_raw)
    campaigns_clean, c_issues = clean_campaigns(campaigns_raw)
    wallets_clean, w_issues = clean_wallets(wallets_raw)
    transactions_clean, t_issues = clean_transactions(transactions_raw)
    balances_clean, b_issues = clean_balances(balances_raw)

    all_issues = [*p_issues, *c_issues, *w_issues, *t_issues, *b_issues]
    issues_df = issues_to_df(all_issues)
    summary_df = summarize_issues(issues_df)

    _ = CleanedDataBundle(
        partners_clean_count=len(partners_clean),
        campaigns_clean_count=len(campaigns_clean),
        wallets_clean_count=len(wallets_clean),
        transactions_clean_count=len(transactions_clean),
        balances_clean_count=len(balances_clean),
        issue_count=len(issues_df),
    )

    return CleanOutput(
        partners_clean=partners_clean,
        campaigns_clean=campaigns_clean,
        wallets_clean=wallets_clean,
        transactions_clean=transactions_clean,
        balances_clean=balances_clean,
        data_quality_issues=issues_df,
        data_quality_summary=summary_df,
    )
