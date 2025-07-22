import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import base64

# ------------------- Streamlit Setup -------------------
st.set_page_config(page_title="Wildlife & Weather Monitor", layout="wide")
st.markdown("<h1 style='text-align: center;'>🌿 AI Wildlife & Environmental Dashboard</h1>", unsafe_allow_html=True)

# ------------------- Custom Theme Styling -------------------
st.markdown("""
<style>
/* Solid dark background - stays fixed */
html, body, .stApp {
    background: #121212 !important;
    color: #f0f0f0 !important;
    font-family: 'Roboto', sans-serif !important;
    opacity: 1 !important;
}

/* Sidebar - no transparency or fade */
section[data-testid="stSidebar"] {
    background-color: #1f1f1f !important;
    border-top-right-radius: 20px;
    border-bottom-right-radius: 20px;
    padding: 2rem 1rem;
    color: #ffffff;
    box-shadow: 0 0 20px rgba(0,255,255,0.05);
    opacity: 1 !important;
}

/* Headings and metric text */
h1, h2, h3, .stMetric {
    color: #00e5ff !important;
    text-shadow: 0 0 5px #00e5ff50;
}

/* Primary button styling */
button[kind="primary"] {
    background: #00e5ff !important;
    color: #000 !important;
    border-radius: 10px !important;
    font-weight: bold !important;
    box-shadow: 0 0 10px #00e5ff !important;
}

/* Map container */
iframe {
    border: none !important;
    width: 100% !important;
    height: 576px !important;
    background-color: transparent !important;
    opacity: 1 !important;
}

/* Scrollbar styling */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background: #00e5ff; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ------------------- Session State -------------------
if "show_result" not in st.session_state:
    st.session_state.show_result = False

# ------------------- Sidebar Filters -------------------
with st.sidebar:
    st.header("🔍 Search Filters")
    area_dict = {
        "Lahore, Pakistan": (31.5497, 74.3436),
        "Islamabad, Pakistan": (33.6844, 73.0479),
        "Karachi, Pakistan": (24.8607, 67.0011),
        "New York, USA": (40.7128, -74.0060),
        "London, UK": (51.5074, -0.1278),
        "Delhi, India": (28.6139, 77.2090),
        "Tokyo, Japan": (35.6762, 139.6503),
        "Custom": None
    }

    selected_area = st.selectbox("Select Area", list(area_dict.keys()))
    if selected_area != "Custom":
        lat, lon = area_dict[selected_area]
    else:
        lat = st.number_input("Latitude", value=30.3753, format="%.4f")
        lon = st.number_input("Longitude", value=69.3451, format="%.4f")

    animal_options = [
        "All", "Deer", "Tiger", "Elephant", "Leopard", "Bear", "Fox", "Wolf", "Lion", "Cheetah",
        "Monkey", "Zebra", "Giraffe", "Panda", "Kangaroo", "Rabbit", "Crocodile", "Peacock",
        "Falcon", "Eagle", "Owl", "Dolphin", "Shark", "Whale", "Snake", "Lizard", "Frog"
    ]
    selected_animal = st.selectbox("Select Animal", animal_options)
    custom_animal = st.text_input("Or enter custom animal name (optional)", "")
    days = st.slider("Days to Analyze", 7, 30, 14)
    show_threatened = st.checkbox("🔴 Show Threatened Species Only", value=False)
    chart_type = st.radio("Trend Chart Type", ["Line Chart", "Bar Chart"])
    if st.button("🚀 Search"):
        st.session_state.show_result = True

# ------------------- Main Dashboard -------------------
if st.session_state.show_result:
    st.caption(f"🕒 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    col1, col2 = st.columns(2)

    # ---- Weather + AQ ----
    with col1:
        st.subheader("🌦️ Weather & Air Quality")
        try:
            API_KEY = "Give It Your APi"
            weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
            air_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
            weather_data = requests.get(weather_url).json()
            air_data = requests.get(air_url).json()

            if weather_data:
                st.metric("📍 Location", weather_data.get('name', 'Unknown'))
                st.metric("🌡️ Temperature", f"{weather_data['main']['temp']} °C")
                st.metric("💧 Humidity", f"{weather_data['main']['humidity']} %")
                st.write("📝 Condition:", weather_data["weather"][0]["description"].capitalize())

            if air_data:
                aqi = air_data['list'][0]['main']['aqi']
                aqi_desc = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
                st.metric("🌫️ Air Quality Index", f"{aqi} - {aqi_desc[aqi-1]}")
        except Exception as e:
            st.error(f"Error: {e}")

    # ---- iNaturalist API ----
    st.subheader("🗺️ Real Animal Sightings (iNaturalist)")
    radius_km = 50
    date_start = (datetime.datetime.today() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')

    query_term = custom_animal.strip() if custom_animal else selected_animal if selected_animal != "All" else ""
    inat_url = f"https://api.inaturalist.org/v1/observations?lat={lat}&lng={lon}&radius={radius_km}&d1={date_start}&per_page=100"
    if query_term: inat_url += f"&q={query_term}"
    if show_threatened: inat_url += "&threatened=true"

    response = requests.get(inat_url)
    inat_data = response.json().get("results", [])

    sightings_df = []
    heat_points = []
    sightings_map = folium.Map(location=[lat, lon], zoom_start=7, control_scale=True)

    for obs in inat_data:
        try:
            species = obs.get("species_guess", "Unknown")
            obs_lat = obs["geojson"]["coordinates"][1]
            obs_lon = obs["geojson"]["coordinates"][0]
            date = obs.get("observed_on", "Unknown")
            url = obs.get("uri", "#")
            folium.Marker(
                [obs_lat, obs_lon],
                popup=f"<b>{species}</b><br>{date}<br><a href='{url}' target='_blank'>View</a>",
                icon=folium.Icon(color="blue", icon="paw")
            ).add_to(sightings_map)
            heat_points.append([obs_lat, obs_lon])
            sightings_df.append({"Species": species, "Date": date})
        except:
            continue

    if heat_points:
        HeatMap(heat_points).add_to(sightings_map)

    # Map Display
    st_folium(sightings_map, width=1324, height=576)

    # ---- Trend Chart + Download ----
    with col2:
        st.subheader("📈 Animal Sightings Trend")
        if sightings_df:
            df = pd.DataFrame(sightings_df)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df.dropna(inplace=True)
            counts = df.groupby("Date").size()

            if chart_type == "Bar Chart":
                st.bar_chart(counts)
            else:
                st.line_chart(counts)

            # Downloadable CSV
            csv = df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            st.markdown(f'<a href="data:file/csv;base64,{b64}" download="animal_sightings.csv">📥 Download CSV</a>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ No sightings found for this animal/location.")
