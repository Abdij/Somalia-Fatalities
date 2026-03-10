from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# =========================================================
# PAGE
# =========================================================
st.set_page_config(
    page_title="Somalia ACLED Fatalities",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #f7f9fc 0%, #eef3f8 100%);
        color: #1f2937;
        font-family: "Segoe UI", sans-serif;
    }

    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 1450px;
    }

    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    h1, h2, h3 {
        color: #111827;
    }

    div[data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        padding: 16px 18px;
        border-radius: 16px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
    }

    div[data-testid="metric-container"] label {
        color: #6b7280 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }

    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #111827 !important;
        font-weight: 800 !important;
    }

    div[data-testid="stPlotlyChart"] {
        background: #ffffff;
        border-radius: 18px;
        padding: 10px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
    }

    div[data-testid="stDataFrame"] {
        background: #ffffff;
        border-radius: 16px;
        padding: 8px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
    }

    div[data-testid="stAlert"] {
        border-radius: 14px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="
    background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
    padding: 22px 26px;
    border-radius: 20px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 8px 24px rgba(0,0,0,0.05);
    margin-bottom: 18px;
">
    <div style="font-size: 2.2rem; font-weight: 800; color: #a61b1b; margin-bottom: 4px;">
        Somalia ACLED Fatalities
    </div>
    <div style="font-size: 1rem; color: #4b5563;">
        Interactive bubble map by location with year, month, date, event type, and sub-event type filters
    </div>
</div>
""", unsafe_allow_html=True)


# =========================================================
# CONFIG
# =========================================================
ACLED_TOKEN = st.secrets.get("ACLED_TOKEN", "")

ACLED_BASE_URL = "https://acleddata.com/api/acled/read"

COUNTRY = 706   # Somalia ISO code
PAGE_LIMIT = 5000

ACLED_FIELDS = [
    "event_id_cnty",
    "event_date",
    "year",
    "country",
    "admin1",
    "admin2",
    "location",
    "latitude",
    "longitude",
    "event_type",
    "sub_event_type",
    "fatalities",
]


# =========================================================
# HELPERS
# =========================================================
def safe_str_series(df: pd.DataFrame, col: str, default: str = "Unknown") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="object")
    return df[col].fillna(default).astype(str)


def make_empty_map(title: str):
    fig = px.scatter_mapbox()
    fig.update_layout(
        title=title,
        mapbox_style="carto-positron",
        margin=dict(l=0, r=0, t=55, b=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )
    return fig


# =========================================================
# ACLED DOWNLOAD
# =========================================================
@st.cache_data(show_spinner=True, ttl=3600)
def fetch_acled_all_somalia(token: str) -> pd.DataFrame:
    if not token:
        raise ValueError("Missing ACLED token in Streamlit secrets.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "somalia-acled-bubble-map",
    }

    rows: List[Dict[str, Any]] = []
    page = 1

while True:
      params = {
    "iso": COUNTRY,
    "limit": PAGE_LIMIT,
    "page": page,
    "fields": "|".join(ACLED_FIELDS),
    "_format": "json",
}

    r = requests.get(ACLED_BASE_URL, headers=headers, params=params, timeout=90)

        if r.status_code == 401:
            raise ValueError("ACLED token expired or unauthorized. Update Streamlit secrets with a new token.")

        r.raise_for_status()

        payload = r.json()
        batch = payload.get("data", []) if isinstance(payload, dict) else payload

        if not batch:
            break

        rows.extend(batch)

        if len(batch) < PAGE_LIMIT:
            break

        page += 1

    if not rows:
        raise ValueError("ACLED request succeeded, but returned no Somalia rows.")

    df = pd.DataFrame(rows)

    df["event_date"] = pd.to_datetime(df.get("event_date"), errors="coerce")
    df["fatalities"] = pd.to_numeric(df.get("fatalities"), errors="coerce").fillna(0)
    df["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")

    df["admin1"] = safe_str_series(df, "admin1")
    df["admin2"] = safe_str_series(df, "admin2")
    df["location"] = safe_str_series(df, "location")
    df["event_type"] = safe_str_series(df, "event_type")
    df["sub_event_type"] = safe_str_series(df, "sub_event_type")

    df = df[df["event_date"].notna()].copy()
    df["year"] = df["event_date"].dt.year
    df["month"] = df["event_date"].dt.month
    df["month_name"] = df["event_date"].dt.strftime("%B")
    df["has_coords"] = df["latitude"].notna() & df["longitude"].notna()

    return df


# =========================================================
# MAP BUILDER
# =========================================================
def build_bubble_map(df: pd.DataFrame, title: str):
    map_df = df[df["has_coords"]].copy()

    if map_df.empty:
        return make_empty_map(title)

    map_df["bubble_size"] = map_df["fatalities"].clip(lower=0).apply(
        lambda x: 8 if x == 0 else min(42, 8 + (x ** 0.5) * 2.2)
    )

    fig = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        color="event_type",
        size="bubble_size",
        size_max=42,
        zoom=5.2,
        center={"lat": 5.8, "lon": 46.2},
        hover_name="location",
        hover_data={
            "event_date": True,
            "admin1": True,
            "admin2": True,
            "event_type": True,
            "sub_event_type": True,
            "fatalities": True,
            "latitude": False,
            "longitude": False,
            "bubble_size": False,
        },
        opacity=0.72,
        title=title,
    )

    fig.update_layout(
        mapbox_style="carto-positron",
        margin=dict(l=0, r=0, t=55, b=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        legend=dict(
            title="Event type",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="rgba(0,0,0,0.08)",
            borderwidth=1,
            font=dict(size=12),
        ),
        title=dict(
            text=title,
            x=0.01,
            xanchor="left",
            font=dict(size=22, color="#111827"),
        ),
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Date: %{customdata[0]|%Y-%m-%d}<br>"
            "Region: %{customdata[1]}<br>"
            "District: %{customdata[2]}<br>"
            "Event type: %{customdata[3]}<br>"
            "Sub-event type: %{customdata[4]}<br>"
            "Fatalities: %{customdata[5]}<extra></extra>"
        )
    )

    return fig


# =========================================================
# RUN
# =========================================================
try:
    raw_df = fetch_acled_all_somalia(ACLED_TOKEN)

    if raw_df.empty:
        st.error("ACLED returned no Somalia data. Check whether the deployed token is missing, expired, or outdated.")
        st.stop()

    available_years = sorted(raw_df["year"].dropna().astype(int).unique().tolist())

    st.sidebar.markdown("""
    <div style="font-size:1.2rem; font-weight:800; color:#a61b1b; margin-bottom:8px;">
        Filters
    </div>
    """, unsafe_allow_html=True)

    selected_year = st.sidebar.selectbox(
        "Year",
        options=available_years,
        index=len(available_years) - 1,
    )

    month_options = ["All"] + [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    selected_month = st.sidebar.selectbox("Month", options=month_options, index=0)

    year_df = raw_df[raw_df["year"] == selected_year].copy()

    if year_df.empty:
        st.warning("No data found for the selected year.")
        st.stop()

    min_date = year_df["event_date"].min().date()
    max_date = year_df["event_date"].max().date()

    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    subevent_options = sorted(year_df["sub_event_type"].dropna().astype(str).unique().tolist())
    selected_subevents = st.sidebar.multiselect(
        "Sub-event type",
        options=subevent_options,
        default=subevent_options,
    )

    event_options = sorted(year_df["event_type"].dropna().astype(str).unique().tolist())
    selected_events = st.sidebar.multiselect(
        "Event type",
        options=event_options,
        default=event_options,
    )

    filtered = year_df.copy()

    if selected_month != "All":
        filtered = filtered[filtered["month_name"] == selected_month].copy()

    filtered = filtered[
        (filtered["event_date"].dt.date >= start_date) &
        (filtered["event_date"].dt.date <= end_date)
    ].copy()

    if selected_subevents:
        filtered = filtered[filtered["sub_event_type"].isin(selected_subevents)].copy()
    else:
        filtered = filtered.iloc[0:0].copy()

    if selected_events:
        filtered = filtered[filtered["event_type"].isin(selected_events)].copy()
    else:
        filtered = filtered.iloc[0:0].copy()

    if selected_month == "All":
        map_title = f"ACLED fatalities in Somalia ({selected_year})"
    else:
        map_title = f"ACLED fatalities in Somalia ({selected_month} {selected_year})"

    if filtered.empty:
        st.warning("No events found for the selected filters.")

    st.plotly_chart(
        build_bubble_map(filtered, map_title),
        use_container_width=True
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Selected year", str(selected_year))
    with c2:
        st.metric("Events", f"{len(filtered):,}")
    with c3:
        st.metric("Fatalities", f"{int(filtered['fatalities'].sum()):,}" if not filtered.empty else "0")
    with c4:
        st.metric("Locations mapped", f"{int(filtered['has_coords'].sum()):,}" if not filtered.empty else "0")

    st.markdown("### Top affected locations")
    if not filtered.empty:
        top_locations = (
            filtered.groupby(["admin1", "admin2", "location"], as_index=False)["fatalities"]
            .sum()
            .sort_values("fatalities", ascending=False)
        )
        st.dataframe(
            top_locations.rename(
                columns={
                    "admin1": "Region",
                    "admin2": "District",
                    "location": "Location",
                    "fatalities": "Fatalities",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No locations to display for the selected filters.")

    st.markdown("### Data preview")
    preview_cols = [
        "event_date", "admin1", "admin2", "location",
        "event_type", "sub_event_type", "fatalities"
    ]
    st.dataframe(
        filtered[preview_cols].sort_values("event_date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()
