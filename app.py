import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date, timedelta

st.set_page_config(
    page_title="Consumer Complaint Intelligence Platform",
    page_icon="📊",
    layout="wide"
)

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"


@st.cache_data(ttl=60 * 60)
def load_cfpb_data(days_back: int = 365, size: int = 2000) -> pd.DataFrame:
    """
    Pull recent complaints from the CFPB Consumer Complaint Database API.
    Cached for 1 hour so the app stays fast.
    """

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    params = {
        "format": "json",
        "size": size,
        "no_aggs": "true",
        "date_received_min": start_date.isoformat(),
        "date_received_max": end_date.isoformat(),
        "sort": "created_date_desc",
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()

    # CFPB API usually returns Elasticsearch-style hits.
    raw_hits = payload.get("hits", {}).get("hits", [])

    records = []
    for hit in raw_hits:
        source = hit.get("_source", {})
        records.append({
            "date_received": source.get("date_received"),
            "product": source.get("product"),
            "sub_product": source.get("sub_product"),
            "issue": source.get("issue"),
            "sub_issue": source.get("sub_issue"),
            "company": source.get("company"),
            "state": source.get("state"),
            "submitted_via": source.get("submitted_via"),
            "company_response": source.get("company_response"),
            "timely_response": source.get("timely"),
            "consumer_disputed": source.get("consumer_disputed"),
            "narrative": source.get("complaint_what_happened"),
            "complaint_id": source.get("complaint_id"),
        })

    df = pd.DataFrame(records)

    if not df.empty:
        df["date_received"] = pd.to_datetime(df["date_received"], errors="coerce")
        df = df.dropna(subset=["date_received"])
        df["month"] = df["date_received"].dt.to_period("M").astype(str)

    return df


st.title("📊 Consumer Complaint Intelligence Platform")

st.markdown(
    """
    Explore real consumer finance complaints from the CFPB Consumer Complaint Database.
    This dashboard analyzes complaint volume, products, companies, states, and response patterns.
    """
)

with st.sidebar:
    st.header("Controls")
    days_back = st.selectbox(
        "Lookback window",
        options=[90, 180, 365, 730],
        index=2
    )

    sample_size = st.selectbox(
        "Complaint sample size",
        options=[500, 1000, 2000, 5000],
        index=2
    )

    refresh = st.button("Refresh data")

if refresh:
    st.cache_data.clear()

with st.spinner("Loading real CFPB complaint data..."):
    df = load_cfpb_data(days_back=days_back, size=sample_size)

if df.empty:
    st.error("No data loaded. The CFPB API may be temporarily unavailable or the query returned no records.")
    st.stop()

st.success(f"Loaded {len(df):,} real complaints.")

# KPI cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total complaints", f"{len(df):,}")

with col2:
    st.metric("Products", df["product"].nunique())

with col3:
    st.metric("Companies", df["company"].nunique())

with col4:
    timely_rate = (
        df["timely_response"]
        .astype(str)
        .str.lower()
        .eq("yes")
        .mean()
        * 100
    )
    st.metric("Timely response rate", f"{timely_rate:.1f}%")

st.divider()

# Complaint trend
st.subheader("Complaint Volume Over Time")

monthly = (
    df.groupby("month")
    .size()
    .reset_index(name="complaints")
    .sort_values("month")
)

fig_monthly = px.line(
    monthly,
    x="month",
    y="complaints",
    markers=True,
    title="Monthly Complaint Volume"
)

st.plotly_chart(fig_monthly, use_container_width=True)

# Product and company charts
left, right = st.columns(2)

with left:
    st.subheader("Top Products")

    product_counts = (
        df["product"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    product_counts.columns = ["product", "complaints"]

    fig_product = px.bar(
        product_counts,
        x="complaints",
        y="product",
        orientation="h",
        title="Top 10 Products by Complaint Volume"
    )
    fig_product.update_layout(yaxis={"categoryorder": "total ascending"})

    st.plotly_chart(fig_product, use_container_width=True)

with right:
    st.subheader("Top Companies")

    company_counts = (
        df["company"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    company_counts.columns = ["company", "complaints"]

    fig_company = px.bar(
        company_counts,
        x="complaints",
        y="company",
        orientation="h",
        title="Top 10 Companies by Complaint Volume"
    )
    fig_company.update_layout(yaxis={"categoryorder": "total ascending"})

    st.plotly_chart(fig_company, use_container_width=True)

st.divider()

# Raw data preview
st.subheader("Data Preview")

preview_cols = [
    "date_received",
    "product",
    "issue",
    "company",
    "state",
    "company_response",
    "timely_response",
]

st.dataframe(
    df[preview_cols].head(50),
    use_container_width=True
)