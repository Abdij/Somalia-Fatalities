from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import numpy as np


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

# Multiple possible API endpoints (in order of likelihood)
ACLED_API_ENDPOINTS = [
    "https://api.acleddata.com/acled/read",
    "https://acleddata.com/api/acled/read",
    "https://data.acleddata.com/acled/read",
]

COUNTRY = "Somalia"
PAGE_LIMIT = 10000

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


def create_sample_data() -> pd.DataFrame:
    """Create enhanced sample Somalia data for demonstration"""
    st.info("📊 Using enhanced sample data for demonstration. Add a valid ACLED token to see real data.")
    
    # Create more realistic sample data for Somalia
    np.random.seed(42)  # for reproducibility
    
    # Define regions and their coordinates
    regions = {
        "Banaadir": {"locations": ["Mogadishu", "Hamar", "Waberi"], 
                    "lat_range": (2.0, 2.1), "lon_range": (45.3, 45.4)},
        "Lower Shabelle": {"locations": ["Afgooye", "Merca", "Qoryooley", "Barawa"],
                          "lat_range": (1.5, 2.2), "lon_range": (44.5, 45.2)},
        "Gedo": {"locations": ["Garbahaarey", "Bardera", "Luuq", "Dolow"],
                "lat_range": (2.5, 4.0), "lon_range": (41.5, 42.8)},
        "Bay": {"locations": ["Baidoa", "Burhakaba", "Dinsoor"],
               "lat_range": (2.5, 3.5), "lon_range": (42.5, 44.0)},
        "Mudug": {"locations": ["Galkayo", "Hobyo", "Harardhere"],
                 "lat_range": (5.0, 7.5), "lon_range": (47.0, 49.0)},
    }
    
    event_types = {
        "Battles": ["Armed clash", "Government regain territory", "Non-state actor overtakes territory"],
        "Violence against civilians": ["Attack", "Abduction/forced disappearance", "Sexual violence"],
        "Explosions/Remote violence": ["Suicide bomb", "Remote explosive/landmine", "Shelling/artillery"],
        "Protests": ["Peaceful protest", "Protest with intervention", "Excessive force against protesters"],
        "Strategic developments": ["Agreement", "Headquarters or base established", "Looting/property destruction"]
    }
    
    # Generate dates as pandas datetime objects
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
    
    rows = []
    
    for region, info in regions.items():
        for location in info["locations"]:
            # Generate multiple events per location
            n_events = np.random.randint(5, 20)
            
            for _ in range(n_events):
                # Random date
                date = np.random.choice(dates)
                
                # Random event type and sub-event type
                event_type = np.random.choice(list(event_types.keys()))
                sub_event_type = np.random.choice(event_types[event_type])
                
                # Random coordinates within region range
                lat = np.random.uniform(info["lat_range"][0], info["lat_range"][1])
                lon = np.random.uniform(info["lon_range"][0], info["lon_range"][1])
                
                # Fatalities based on event type
                if event_type == "Battles":
                    fatalities = np.random.poisson(5)
                elif event_type == "Violence against civilians":
                    fatalities = np.random.poisson(3)
                elif event_type == "Explosions/Remote violence":
                    fatalities = np.random.poisson(4)
                else:
                    fatalities = np.random.poisson(1)
                
                rows.append({
                    "event_date": date,
                    "country": "Somalia",
                    "admin1": region,
                    "admin2": location,
                    "location": location,
                    "latitude": lat,
                    "longitude": lon,
                    "event_type": event_type,
                    "sub_event_type": sub_event_type,
                    "fatalities": fatalities,
                })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Convert event_date to datetime if it isn't already
    df["event_date"] = pd.to_datetime(df["event_date"])
    
    # Add derived columns using pandas datetime methods
    df["year"] = df["event_date"].dt.year
    df["month"] = df["event_date"].dt.month
    df["month_name"] = df["event_date"].dt.strftime("%B")
    df["has_coords"] = df["latitude"].notna() & df["longitude"].notna()
    
    return df


# =========================================================
# ACLED DOWNLOAD WITH MULTIPLE ENDPOINTS
# =========================================================
def test_api_endpoint(endpoint: str, token: str, params: Dict) -> tuple[bool, Optional[Dict]]:
    """Test if an API endpoint is accessible"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "somalia-acled-bubble-map",
    }
    
    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            return True, r.json()
        else:
            return False, None
    except:
        return False, None


@st.cache_data(show_spinner=True, ttl=3600)
def fetch_acled_all_somalia(token: str) -> pd.DataFrame:
    if not token:
        st.warning("🔑 No ACLED token found. Using sample data.")
        return create_sample_data()

    # Test parameters
    test_params = {
        "country": COUNTRY,
        "limit": 1,
        "fields": ",".join(ACLED_FIELDS[:3]),  # Just a few fields for testing
        "format": "json",
    }
    
    # Find working endpoint
    working_endpoint = None
    st.info("🔍 Testing ACLED API endpoints...")
    
    for endpoint in ACLED_API_ENDPOINTS:
        st.write(f"Testing: {endpoint}")
        success, _ = test_api_endpoint(endpoint, token, test_params)
        if success:
            working_endpoint = endpoint
            st.success(f"✅ Found working endpoint: {endpoint}")
            break
        else:
            st.write(f"❌ Failed: {endpoint}")
    
    if not working_endpoint:
        st.error("❌ Could not connect to any ACLED API endpoint. Using sample data.")
        return create_sample_data()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "somalia-acled-bubble-map",
    }

    rows: List[Dict[str, Any]] = []
    page = 1
    max_pages = 5  # Limit pages to avoid long loading times
    retries = 3

    # Show progress
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        while page <= max_pages:
            for attempt in range(retries):
                try:
                    status_text.text(f"Fetching page {page} (attempt {attempt + 1}/{retries})...")
                    
                    params = {
                        "country": COUNTRY,
                        "limit": PAGE_LIMIT,
                        "page": page,
                        "fields": ",".join(ACLED_FIELDS),
                        "format": "json",
                    }

                    with st.expander(f"Debug - Page {page} Request", expanded=False):
                        st.write(f"Endpoint: {working_endpoint}")
                        st.write(f"Params: {params}")

                    r = requests.get(
                        working_endpoint, 
                        headers=headers, 
                        params=params, 
                        timeout=30
                    )

                    if r.status_code == 401:
                        st.error("🔑 ACLED token is invalid or expired.")
                        return create_sample_data()

                    r.raise_for_status()
                    payload = r.json()
                    
                    # Handle different response formats
                    if isinstance(payload, dict):
                        batch = payload.get("data", [])
                        if not batch:
                            batch = payload.get("results", [])
                    else:
                        batch = payload if isinstance(payload, list) else []

                    if not batch:
                        status_text.text(f"No more data on page {page}")
                        break

                    rows.extend(batch)
                    
                    # Update progress
                    progress_bar.progress(min(page * 20, 100))
                    
                    # If we got fewer items than the limit, we're done
                    if len(batch) < PAGE_LIMIT:
                        status_text.text(f"Completed - fetched {len(rows)} total events")
                        break
                        
                    break  # Success, exit retry loop
                    
                except requests.exceptions.RequestException as e:
                    if attempt == retries - 1:
                        st.warning(f"Failed to fetch page {page} after {retries} attempts")
                        st.write(f"Error: {str(e)}")
                    else:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue

            page += 1

    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return create_sample_data()
    finally:
        progress_bar.empty()
        status_text.empty()

    if not rows:
        st.warning("No Somalia data found from API. Using sample data.")
        return create_sample_data()

    st.success(f"✅ Successfully fetched {len(rows)} events from ACLED")
    
    # Convert to DataFrame
    df = pd.DataFrame(rows)

    # Process dates and numbers
    df["event_date"] = pd.to_datetime(df.get("event_date"), errors="coerce")
    df["fatalities"] = pd.to_numeric(df.get("fatalities"), errors="coerce").fillna(0)
    df["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")

    # Fill missing values
    for col in ["admin1", "admin2", "location", "event_type", "sub_event_type"]:
        df[col] = safe_str_series(df, col)

    # Filter out rows with no date
    df = df[df["event_date"].notna()].copy()
    
    # Add derived columns using pandas datetime methods
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
        color_discrete_sequence=px.colors.qualitative.Set1,
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
        st.error("No data available. Please try again later.")
        st.stop()

    available_years = sorted(raw_df["year"].dropna().astype(int).unique().tolist())

    st.sidebar.markdown("""
    <div style="font-size:1.2rem; font-weight:800; color:#a61b1b; margin-bottom:8px;">
        Filters
    </div>
    """, unsafe_allow_html=True)

    if available_years:
        selected_year = st.sidebar.selectbox(
            "Year",
            options=available_years,
            index=len(available_years) - 1,
        )
    else:
        selected_year = 2023

    month_options = ["All"] + [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    selected_month = st.sidebar.selectbox("Month", options=month_options, index=0)

    # Filter by year
    if available_years:
        year_df = raw_df[raw_df["year"] == selected_year].copy()
    else:
        year_df = raw_df.copy()
        selected_year = "All"

    if not year_df.empty:
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

        # Get unique event types and sub-event types
        event_options = sorted(year_df["event_type"].dropna().astype(str).unique().tolist())
        subevent_options = sorted(year_df["sub_event_type"].dropna().astype(str).unique().tolist())

        selected_events = st.sidebar.multiselect(
            "Event type",
            options=event_options,
            default=event_options,
        )

        selected_subevents = st.sidebar.multiselect(
            "Sub-event type",
            options=subevent_options,
            default=subevent_options,
        )

        # Apply filters
        filtered = year_df.copy()

        if selected_month != "All":
            filtered = filtered[filtered["month_name"] == selected_month].copy()

        filtered = filtered[
            (filtered["event_date"].dt.date >= start_date) &
            (filtered["event_date"].dt.date <= end_date)
        ].copy()

        if selected_events:
            filtered = filtered[filtered["event_type"].isin(selected_events)].copy()

        if selected_subevents:
            filtered = filtered[filtered["sub_event_type"].isin(selected_subevents)].copy()

    else:
        filtered = pd.DataFrame()
        selected_events = []
        selected_subevents = []

    # Create map title
    if selected_month == "All":
        map_title = f"ACLED Fatalities in Somalia ({selected_year})"
    else:
        map_title = f"ACLED Fatalities in Somalia ({selected_month} {selected_year})"

    # Display map
    if filtered.empty:
        st.info("📊 No events found for the selected filters. Try adjusting your filters.")
    
    st.plotly_chart(
        build_bubble_map(filtered, map_title),
        use_container_width=True
    )

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Selected Year", str(selected_year))
    with c2:
        st.metric("Events", f"{len(filtered):,}")
    with c3:
        st.metric("Fatalities", f"{int(filtered['fatalities'].sum()):,}" if not filtered.empty else "0")
    with c4:
        st.metric("Locations Mapped", f"{int(filtered['has_coords'].sum()):,}" if not filtered.empty else "0")

    # Top locations
    st.markdown("### 📍 Top Affected Locations")
    if not filtered.empty and len(filtered) > 0:
        top_locations = (
            filtered.groupby(["admin1", "admin2", "location"], as_index=False)["fatalities"]
            .sum()
            .sort_values("fatalities", ascending=False)
            .head(10)
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
        st.info("No locations to display")

    # Data preview
    st.markdown("### 👁️ Data Preview")
    preview_cols = [
        "event_date", "admin1", "admin2", "location",
        "event_type", "sub_event_type", "fatalities"
    ]
    if not filtered.empty and len(filtered) > 0:
        st.dataframe(
            filtered[preview_cols].sort_values("event_date", ascending=False).head(100),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Showing first 100 of {len(filtered)} events")
    else:
        st.info("No data to preview")

except Exception as e:
    st.error(f"Error loading data: {e}")
    with st.expander("Show detailed error"):
        import traceback
        st.code(traceback.format_exc())
