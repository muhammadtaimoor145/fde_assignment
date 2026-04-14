from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from sut_payment.cleaning import load_and_clean
from sut_payment.risk.engine import compute_risks
from sut_payment.savings.engine import compute_savings


@st.cache_data(show_spinner=False)
def run_pipeline(data_dir: str) -> dict[str, pd.DataFrame]:
    cleaned = load_and_clean(Path(data_dir))
    savings = compute_savings(cleaned.campaigns_clean, cleaned.partners_clean)
    risks = compute_risks(
        campaigns_clean=cleaned.campaigns_clean,
        wallets_clean=cleaned.wallets_clean,
        transactions_clean=cleaned.transactions_clean,
        balances_clean=cleaned.balances_clean,
    )
    return {
        "campaigns_clean": cleaned.campaigns_clean,
        "transactions_clean": cleaned.transactions_clean,
        "campaign_savings": savings.campaign_savings,
        "partner_savings": savings.partner_savings,
        "savings_kpis": savings.savings_kpis,
        "top_risky_campaigns": risks.top_risky_campaigns,
        "risk_distribution": risks.risk_distribution,
    }


def _apply_filters(
    campaign_savings_df: pd.DataFrame,
    risks_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    selected_campaign_id: str,
) -> pd.DataFrame:
    _ = transactions_df
    selected_savings = campaign_savings_df[
        campaign_savings_df["campaign_id"] == selected_campaign_id
    ].reset_index(drop=True)
    selected_risk = risks_df[risks_df["campaign_id"] == selected_campaign_id].reset_index(drop=True)
    return pd.DataFrame(
        {
            "selected_savings": [selected_savings],
            "selected_risk": [selected_risk],
        }
    )


def _severity_color_map() -> dict[str, str]:
    return {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}


def _campaign_ids_for_risk(risks_df: pd.DataFrame, risk_key: str) -> list[str]:
    if risks_df.empty:
        return []
    source_col = "risk_reason_keys" if "risk_reason_keys" in risks_df.columns else "risk_reasons"
    if risk_key == "wallet_issue":
        mask = risks_df[source_col].str.contains(
            "missing_wallet_mapping|invalid_wallet_address",
            na=False,
        )
    else:
        mask = risks_df[source_col].str.contains(risk_key, na=False)
    return risks_df.loc[mask, "campaign_id"].dropna().tolist()


def _campaign_ids_for_risk_free(
    campaign_savings_df: pd.DataFrame,
    risks_df: pd.DataFrame,
) -> list[str]:
    all_campaign_ids = set(campaign_savings_df["campaign_id"].dropna().tolist())
    risky_campaign_ids = set(risks_df["campaign_id"].dropna().tolist())
    risk_free_campaign_ids = sorted(all_campaign_ids - risky_campaign_ids)
    return risk_free_campaign_ids


def _show_impact_summary(
    selected_savings: pd.DataFrame,
    selected_risk: pd.DataFrame,
) -> None:
    savings_value = (
        float(selected_savings.iloc[0]["estimated_savings_krw"])
        if not selected_savings.empty and pd.notna(selected_savings.iloc[0]["estimated_savings_krw"])
        else 0.0
    )
    severity = (
        str(selected_risk.iloc[0]["severity"]).upper()
        if not selected_risk.empty
        else "LOW"
    )
    action_flag = "Yes" if not selected_risk.empty else "No"

    col1, col2, col3 = st.columns(3)
    col1.metric("Campaign Savings Potential (KRW)", f"{savings_value:,.0f}")
    col2.metric("Needs Immediate Action", action_flag)
    col3.metric("Current Risk Severity", severity)

    st.info(
        "Campaign-level impact: use this view to decide if settlement can continue, "
        "what risk exists, and how much savings is achievable."
    )
    st.warning(f"Current campaign severity: {severity}")


def _render_overview_charts(
    selected_savings: pd.DataFrame,
) -> None:
    if selected_savings.empty:
        st.info("Selected campaign has insufficient data for overview.")
        return

    spend_vs_savings = pd.DataFrame(
        {
            "metric": ["Actual Spend (KRW)", "Estimated Savings (KRW)"],
            "value": [
                float(selected_savings.iloc[0]["actual_spend_krw"] or 0),
                float(selected_savings.iloc[0]["estimated_savings_krw"] or 0),
            ],
        }
    )
    fig_savings = px.bar(
        spend_vs_savings,
        x="metric",
        y="value",
        color="metric",
        title="Spend vs Savings for Selected Campaign",
        labels={"value": "Amount (KRW)", "metric": "Metric"},
    )
    st.plotly_chart(fig_savings, use_container_width=True)

def _render_savings_view(selected_savings: pd.DataFrame) -> None:
    if selected_savings.empty:
        st.info("No savings data available for the selected campaign.")
        return

    row = selected_savings.iloc[0]
    waterfall_df = pd.DataFrame(
        {
            "label": ["Actual Spend", "Discount Effect", "Post-SUT Effective Cost"],
            "value": [
                float(row["actual_spend_krw"] or 0),
                -float(row["estimated_savings_krw"] or 0),
                float((row["actual_spend_krw"] or 0) - (row["estimated_savings_krw"] or 0)),
            ],
        }
    )
    fig = go.Figure(
        go.Waterfall(
            x=waterfall_df["label"],
            y=waterfall_df["value"],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )
    )
    fig.update_layout(title="How SUT Impacts Campaign Cost")
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_view(selected_risk: pd.DataFrame) -> None:
    if selected_risk.empty:
        st.success("No active risk flags for this campaign.")
        return

    row = selected_risk.iloc[0]
    st.markdown(f"### {row['campaign_id']} - {row['campaign_name']}")
    st.markdown(f"**Severity:** `{row['severity'].upper()}`")
    if "action_priority" in row:
        st.markdown(f"**Action priority:** `{row['action_priority']}`")
    if "risk_priority_score" in row:
        st.markdown(f"**Risk priority score:** `{float(row['risk_priority_score']):.1f}`")
    st.markdown(f"**Risk reasons:** {row['risk_reasons']}")
    st.markdown(f"**Next actions:** {row['recommended_next_action']}")


def _render_top_risky_campaigns_panel(risks_df: pd.DataFrame, top_n: int = 5) -> None:
    if risks_df.empty:
        st.info("No risky campaigns found.")
        return

    top_n_df = risks_df.head(top_n).copy().reset_index(drop=True)
    top_n_df["rank"] = top_n_df.index + 1
    fig = px.bar(
        top_n_df,
        x="campaign_name",
        y="risk_priority_score",
        color="severity",
        title=f"Top {top_n} Risky Campaigns",
        labels={"risk_priority_score": "Risk Priority Score", "campaign_name": "Campaign"},
        color_discrete_map=_severity_color_map(),
    )
    st.plotly_chart(fig, use_container_width=True)

    for _, row in top_n_df.iterrows():
        st.markdown(
            f"**#{int(row['rank'])} {row['campaign_name']}** - "
            f"Severity: `{row['severity']}`, "
            f"Action: `{row['action_priority']}`"
        )


def _reason_fix_guide(reason_key: str) -> str:
    mapping = {
        "failed_transaction": "Check failure cause, correct parameters/wallet state, then retry settlement with monitoring.",
        "pending_settlement": "Set a pending timeout SLA and escalate if confirmation does not arrive in the allowed window.",
        "missing_wallet_mapping": "Collect and verify partner primary wallet, then map it before sending settlement.",
        "invalid_wallet_address": "Re-validate wallet format and ownership proof, then replace invalid address.",
        "low_sut_balance": "Top up wallet above required settlement amount plus safety buffer before retry.",
        "unstarted_settlement": "Create initial settlement tx for campaign and track until first confirmation.",
    }
    return mapping.get(reason_key, "Investigate root cause and apply corrective action before next settlement.")


def _render_risk_campaigns_tab(risks_df: pd.DataFrame) -> None:
    st.subheader("Top Risk Campaign Queue")
    if risks_df.empty:
        st.success("No risky campaigns detected.")
        return

    top_n = st.slider("How many risky campaigns to show", min_value=3, max_value=10, value=5, step=1)
    top_df = risks_df.head(top_n).copy().reset_index(drop=True)
    top_df["rank"] = top_df.index + 1

    for _, row in top_df.iterrows():
        campaign_title = (
            f"#{int(row['rank'])} {row['campaign_name']} "
            f"({row['campaign_id']}) - {row['severity'].upper()}"
        )
        with st.expander(campaign_title, expanded=False):
            st.markdown(f"**Why this campaign is risky:** {row['risk_reasons']}")
            st.markdown(f"**Immediate next action:** {row['recommended_next_action']}")
            st.markdown(f"**Action priority:** `{row['action_priority']}`")
            st.markdown(f"**Risk priority score:** `{float(row['risk_priority_score']):.1f}`")

            reason_keys = str(row.get("risk_reason_keys", "")).split("; ")
            reason_keys = [key.strip() for key in reason_keys if key.strip()]
            if reason_keys:
                st.markdown("**How to set/fix this permanently:**")
                for key in reason_keys:
                    st.markdown(f"- `{key}`: {_reason_fix_guide(key)}")


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="SUT Payment Launch Rescue", layout="wide")
    st.title("SUT Payment Launch Rescue Dashboard")
    st.caption("Unified MVP for savings, risk, and reconciliation decisions")

    default_data_dir = Path(__file__).resolve().parents[3] / "2026_04_09-FDE-Quest" / "data"
    data_dir = st.sidebar.text_input("Data folder", str(default_data_dir))

    pipeline = run_pipeline(data_dir)
    campaigns_df = pipeline["campaigns_clean"]
    campaign_savings_df = pipeline["campaign_savings"]
    risks_df = pipeline["top_risky_campaigns"]

    st.sidebar.subheader("Risk Finder")
    finder_col1, finder_col2 = st.sidebar.columns(2)
    finder_col3, finder_col4 = st.sidebar.columns(2)

    risk_filtered_campaign_ids: list[str] = []
    if finder_col1.button("Failed Payment", use_container_width=True):
        risk_filtered_campaign_ids = _campaign_ids_for_risk(risks_df, "failed_transaction")
    if finder_col2.button("Pending Settlement", use_container_width=True):
        risk_filtered_campaign_ids = _campaign_ids_for_risk(risks_df, "pending_settlement")
    if finder_col3.button("Wallet Issues", use_container_width=True):
        risk_filtered_campaign_ids = _campaign_ids_for_risk(risks_df, "wallet_issue")
    if finder_col4.button("Low Balance", use_container_width=True):
        risk_filtered_campaign_ids = _campaign_ids_for_risk(risks_df, "low_sut_balance")
    if st.sidebar.button("Risk-Free Campaigns", use_container_width=True):
        risk_filtered_campaign_ids = _campaign_ids_for_risk_free(
            campaign_savings_df=campaign_savings_df,
            risks_df=risks_df,
        )

    if "risk_filtered_campaign_ids" not in st.session_state:
        st.session_state["risk_filtered_campaign_ids"] = []
    if risk_filtered_campaign_ids:
        st.session_state["risk_filtered_campaign_ids"] = risk_filtered_campaign_ids

    if st.sidebar.button("Clear Risk Filter", use_container_width=True):
        st.session_state["risk_filtered_campaign_ids"] = []

    filtered_campaign_df = campaign_savings_df.copy()
    if st.session_state["risk_filtered_campaign_ids"]:
        filtered_campaign_df = filtered_campaign_df[
            filtered_campaign_df["campaign_id"].isin(st.session_state["risk_filtered_campaign_ids"])
        ]
        st.sidebar.caption(
            f"Campaigns matching selected filter: {len(filtered_campaign_df)}"
        )

    if filtered_campaign_df.empty:
        filtered_campaign_df = campaign_savings_df.copy()
        st.sidebar.warning("No campaigns found for selected risk filter.")

    campaign_option_map = (
        filtered_campaign_df[["campaign_id", "campaign_name"]]
        .drop_duplicates()
        .assign(label=lambda df: df["campaign_name"] + " (" + df["campaign_id"] + ")")
    )
    selected_label = st.sidebar.selectbox("Campaign", campaign_option_map["label"].tolist())
    selected_campaign_id = str(
        campaign_option_map.loc[campaign_option_map["label"] == selected_label, "campaign_id"].iloc[0]
    )
    selected_campaign_name = str(
        campaign_option_map.loc[campaign_option_map["label"] == selected_label, "campaign_name"].iloc[0]
    )

    selected_data = _apply_filters(
        campaign_savings_df=campaign_savings_df,
        risks_df=pipeline["top_risky_campaigns"],
        transactions_df=pipeline["transactions_clean"],
        selected_campaign_id=selected_campaign_id,
    )
    selected_savings = selected_data.iloc[0]["selected_savings"]
    selected_risk = selected_data.iloc[0]["selected_risk"]

    partner_name = (
        str(selected_savings.iloc[0]["partner_name"])
        if not selected_savings.empty and pd.notna(selected_savings.iloc[0]["partner_name"])
        else "Unknown Partner"
    )
    st.markdown(f"### Partner: {partner_name}")
    st.markdown(f"### Campaign: {selected_campaign_name} (`{selected_campaign_id}`)")

    _show_impact_summary(
        selected_savings=selected_savings,
        selected_risk=selected_risk,
    )

    tab_overview, tab_savings, tab_risk, tab_risk_campaigns = st.tabs(
        ["Overview", "Savings", "Risk and Actions", "Risk Campaigns"]
    )

    with tab_overview:
        st.subheader("Operator Overview")
        _render_overview_charts(
            selected_savings=selected_savings,
        )

    with tab_savings:
        st.subheader("Savings Impact")
        _render_savings_view(selected_savings=selected_savings)

    with tab_risk:
        st.subheader("Risk and Actionability")
        _render_risk_view(selected_risk=selected_risk)

    with tab_risk_campaigns:
        _render_top_risky_campaigns_panel(risks_df=risks_df, top_n=5)
        _render_risk_campaigns_tab(risks_df=risks_df)


if __name__ == "__main__":
    main()
