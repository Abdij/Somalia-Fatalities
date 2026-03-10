from __future__ import annotations
import os
import re
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# =========================================================
# PAGE
# =========================================================
st.set_page_config(page_title="Somalia ACLED Fatalities", layout="wide")
st.title("Somalia ACLED Fatalities")
st.caption("Bubble map by location with year, month, date, and sub-event type filters")


# =========================================================
# CONFIG
# =========================================================

ACLED_TOKEN = os.getenv("ACLED_TOKEN")
if not ACLED_TOKEN:
    st.error("ACLED token not found. Please set the ACLED_TOKEN environment variable.")
    st.stop()
ACLED_BASE_URL = "https://acleddata.com/api/acled/read"
COUNTRY = "Somalia"
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
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="#f7f7f7",
    )
    return fig


# =========================================================
# ACLED DOWNLOAD
# =========================================================
@st.cache_data(show_spinner=True)
def fetch_acled_all_somalia(token: str) -> pd.DataFrame:
    if not token:
        raise ValueError("Missing ACLED token.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "somalia-acled-bubble-map",
    }

    rows: List[Dict[str, Any]] = []
    page = 1

    while True:
        params = {
            "country": COUNTRY,
            "limit": PAGE_LIMIT,
            "page": page,
            "fields": "|".join(ACLED_FIELDS),
            "_format": "json",
        }

        r = requests.get(ACLED_BASE_URL, headers=headers, params=params, timeout=90)
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
        return pd.DataFrame(columns=ACLED_FIELDS)

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

    # avoid zero-size bubbles disappearing completely
    map_df["bubble_size"] = map_df["fatalities"].clip(lower=0).apply(
        lambda x: 8 if x == 0 else min(40, 8 + (x ** 0.5) * 2.2)
    )

    fig = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        color="event_type",
        size="bubble_size",
        size_max=40,
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
        opacity=0.70,
        title=title,
    )

    fig.update_layout(
        mapbox_style="carto-positron",
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="#f7f7f7",
        legend_title_text="Event type",
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
        st.warning("No ACLED Somalia data was returned.")
        st.stop()

    available_years = sorted(raw_df["year"].dropna().astype(int).unique().tolist())

    st.sidebar.header("Filters")

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