"""
Nassau Candy Distributor — Product Line Profitability & Margin Performance Dashboard
Run with:  streamlit run app.py

Expects Nassau_Candy_Distributor.csv in the same folder as this script.
If it isn't found, the app shows a file uploader instead.
"""
import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Nassau Candy | Profitability & Margin Dashboard",
    page_icon="🍬",
    layout="wide",
)

DATA_FILENAME = "Nassau_Candy_Distributor.csv"


# ----------------------------------------------------------------------------
# DATA LOADING & CLEANING (Step 1 logic, self-contained)
# ----------------------------------------------------------------------------
@st.cache_data
def load_and_clean(file) -> pd.DataFrame:
    df = pd.read_csv(file)

    text_cols = ["Division", "Region", "Product Name", "Ship Mode",
                 "Country/Region", "City", "State/Province"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df["Product Name"] = df["Product Name"].str.replace(r"\s*-\s*", " - ", regex=True)

    df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce")
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], dayfirst=True, errors="coerce")

    for col in ["Sales", "Cost", "Gross Profit", "Units"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[(df["Sales"] > 0) & (df["Cost"] >= 0)]
    df["Gross Profit"] = df["Sales"] - df["Cost"]  # guarantee consistency
    df = df[df["Units"] > 0]
    df = df.dropna(subset=["Sales", "Cost", "Gross Profit", "Units",
                            "Division", "Product Name", "Order Date"])
    return df


# ----------------------------------------------------------------------------
# LOAD DATA
# ----------------------------------------------------------------------------
if os.path.exists(DATA_FILENAME):
    raw_df = load_and_clean(DATA_FILENAME)
else:
    st.warning(f"'{DATA_FILENAME}' not found next to app.py — upload it below.")
    uploaded = st.file_uploader("Upload Nassau Candy Distributor CSV", type="csv")
    if uploaded is None:
        st.stop()
    raw_df = load_and_clean(uploaded)

st.title("🍬 Nassau Candy Distributor")
st.subheader("Product Line Profitability & Margin Performance Dashboard")

# ----------------------------------------------------------------------------
# SIDEBAR — USER CAPABILITIES / FILTERS
# ----------------------------------------------------------------------------
st.sidebar.header("Filters")

min_date, max_date = raw_df["Order Date"].min(), raw_df["Order Date"].max()
date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    start_date, end_date = min_date, max_date

divisions = sorted(raw_df["Division"].unique())
selected_divisions = st.sidebar.multiselect("Division", divisions, default=divisions)

margin_threshold = st.sidebar.slider(
    "Margin risk threshold (%) — flag products below this",
    min_value=0, max_value=100, value=50, step=5,
)

search_term = st.sidebar.text_input("Product search", "")

# Apply filters
df = raw_df[
    (raw_df["Order Date"] >= start_date)
    & (raw_df["Order Date"] <= end_date)
    & (raw_df["Division"].isin(selected_divisions))
].copy()

if search_term:
    df = df[df["Product Name"].str.contains(search_term, case=False, na=False)]

if df.empty:
    st.error("No data matches the current filters. Try widening the date range or filters.")
    st.stop()

# ----------------------------------------------------------------------------
# CORE METRICS (Step 2 logic)
# ----------------------------------------------------------------------------
total_sales = df["Sales"].sum()
total_profit = df["Gross Profit"].sum()
total_units = df["Units"].sum()
overall_margin = total_profit / total_sales * 100 if total_sales else 0

pm = df.groupby(["Division", "Product Name"], as_index=False).agg(
    Total_Sales=("Sales", "sum"),
    Total_Units=("Units", "sum"),
    Total_Cost=("Cost", "sum"),
    Total_Gross_Profit=("Gross Profit", "sum"),
)
pm["Gross_Margin_Pct"] = pm["Total_Gross_Profit"] / pm["Total_Sales"] * 100
pm["Profit_per_Unit"] = pm["Total_Gross_Profit"] / pm["Total_Units"]
pm["Revenue_Contribution_Pct"] = pm["Total_Sales"] / total_sales * 100
pm["Profit_Contribution_Pct"] = pm["Total_Gross_Profit"] / total_profit * 100
pm["Cost_to_Sales_Ratio"] = pm["Total_Cost"] / pm["Total_Sales"]
pm["At_Risk"] = pm["Gross_Margin_Pct"] < margin_threshold
pm = pm.sort_values("Total_Gross_Profit", ascending=False)

# Top KPI row
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Sales", f"${total_sales:,.0f}")
k2.metric("Total Gross Profit", f"${total_profit:,.0f}")
k3.metric("Overall Margin", f"{overall_margin:.1f}%")
k4.metric("Units Sold", f"{total_units:,.0f}")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Product Profitability Overview",
    "🏢 Division Performance",
    "🎯 Cost vs Margin Diagnostics",
    "📈 Profit Concentration (Pareto)",
])

# ----------------------------------------------------------------------------
# TAB 1: PRODUCT PROFITABILITY OVERVIEW
# ----------------------------------------------------------------------------
with tab1:
    st.markdown("#### Product-level margin leaderboard")
    st.dataframe(
        pm[["Product Name", "Division", "Total_Sales", "Total_Gross_Profit",
            "Gross_Margin_Pct", "Profit_per_Unit", "Revenue_Contribution_Pct",
            "Profit_Contribution_Pct", "At_Risk"]]
        .style.format({
            "Total_Sales": "${:,.2f}", "Total_Gross_Profit": "${:,.2f}",
            "Gross_Margin_Pct": "{:.1f}%", "Profit_per_Unit": "${:.2f}",
            "Revenue_Contribution_Pct": "{:.1f}%", "Profit_Contribution_Pct": "{:.1f}%",
        }),
        use_container_width=True, height=420,
    )

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            pm.sort_values("Total_Gross_Profit"),
            x="Total_Gross_Profit", y="Product Name", color="Division",
            orientation="h", title="Profit Contribution by Product",
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(
            pm.sort_values("Gross_Margin_Pct"),
            x="Gross_Margin_Pct", y="Product Name", color="Division",
            orientation="h", title="Gross Margin % by Product",
        )
        fig.add_vline(x=margin_threshold, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 2: DIVISION PERFORMANCE DASHBOARD
# ----------------------------------------------------------------------------
with tab2:
    div = df.groupby("Division", as_index=False).agg(
        Total_Sales=("Sales", "sum"),
        Total_Profit=("Gross Profit", "sum"),
    )
    div["Avg_Margin_Pct"] = div["Total_Profit"] / div["Total_Sales"] * 100
    div["Revenue_Share_Pct"] = div["Total_Sales"] / total_sales * 100
    div["Profit_Share_Pct"] = div["Total_Profit"] / total_profit * 100
    div["Imbalance"] = div["Profit_Share_Pct"] - div["Revenue_Share_Pct"]

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        fig.add_bar(x=div["Division"], y=div["Revenue_Share_Pct"], name="Revenue Share %")
        fig.add_bar(x=div["Division"], y=div["Profit_Share_Pct"], name="Profit Share %")
        fig.update_layout(barmode="group", title="Revenue vs Profit Share by Division")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        # Margin distribution: order-level margin per division (box plot)
        df["Order_Margin_Pct"] = df["Gross Profit"] / df["Sales"] * 100
        fig = px.box(df, x="Division", y="Order_Margin_Pct",
                     title="Margin Distribution by Division", points="outliers")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Division summary")
    st.dataframe(
        div.style.format({
            "Total_Sales": "${:,.2f}", "Total_Profit": "${:,.2f}",
            "Avg_Margin_Pct": "{:.1f}%", "Revenue_Share_Pct": "{:.1f}%",
            "Profit_Share_Pct": "{:.1f}%", "Imbalance": "{:+.2f}",
        }),
        use_container_width=True,
    )
    st.caption("Positive Imbalance = division earns more profit share than its revenue "
               "share (profit-efficient). Negative = underperforming relative to its "
               "revenue footprint.")

# ----------------------------------------------------------------------------
# TAB 3: COST VS MARGIN DIAGNOSTICS
# ----------------------------------------------------------------------------
with tab3:
    fig = px.scatter(
        pm, x="Total_Cost", y="Total_Sales", size="Total_Units",
        color="Gross_Margin_Pct", hover_name="Product Name",
        color_continuous_scale="RdYlGn",
        title="Cost vs Sales (bubble size = units, color = margin %)",
    )
    st.plotly_chart(fig, use_container_width=True)

    flagged = pm[pm["At_Risk"]].sort_values("Gross_Margin_Pct")
    st.markdown(f"#### Margin risk flags (margin below {margin_threshold}%)")
    if flagged.empty:
        st.success("No products fall below the current margin threshold.")
    else:
        st.dataframe(
            flagged[["Product Name", "Division", "Gross_Margin_Pct",
                     "Cost_to_Sales_Ratio", "Total_Sales", "Total_Gross_Profit"]]
            .style.format({
                "Gross_Margin_Pct": "{:.1f}%", "Cost_to_Sales_Ratio": "{:.2f}",
                "Total_Sales": "${:,.2f}", "Total_Gross_Profit": "${:,.2f}",
            }),
            use_container_width=True,
        )

# ----------------------------------------------------------------------------
# TAB 4: PROFIT CONCENTRATION (PARETO) ANALYSIS
# ----------------------------------------------------------------------------
with tab4:
    par = pm.sort_values("Total_Gross_Profit", ascending=False).reset_index(drop=True)
    par["Cum_Profit_Pct"] = par["Total_Gross_Profit"].cumsum() / par["Total_Gross_Profit"].sum() * 100
    n_products = len(par)
    n_80 = (par["Cum_Profit_Pct"] <= 80).sum() + 1

    fig = go.Figure()
    fig.add_bar(x=par["Product Name"], y=par["Total_Gross_Profit"], name="Gross Profit")
    fig.add_trace(go.Scatter(
        x=par["Product Name"], y=par["Cum_Profit_Pct"], name="Cumulative %",
        yaxis="y2", mode="lines+markers", line=dict(color="firebrick"),
    ))
    fig.add_hline(y=80, line_dash="dash", line_color="gray", yref="y2")
    fig.update_layout(
        title="Pareto Chart — Profit Concentration by Product",
        yaxis=dict(title="Gross Profit ($)"),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 110]),
        xaxis=dict(tickangle=-40),
    )
    st.plotly_chart(fig, use_container_width=True)

    d1, d2 = st.columns(2)
    d1.metric("Products driving 80% of profit", f"{n_80} of {n_products}",
               f"{n_80/n_products*100:.0f}% of catalog")
    top_share = par.iloc[0]["Profit_Contribution_Pct"] if not par.empty else 0
    d2.metric("Top single product's profit share", f"{top_share:.1f}%")

    st.caption("A small cluster of products driving the large majority of profit signals "
               "concentration risk — the business is highly dependent on a few SKUs.")

st.divider()
st.caption("Nassau Candy Distributor — Product Line Profitability & Margin Performance Analysis")
