import streamlit as st
import numpy as np
from datetime import datetime, timedelta
from math import isnan

# === Astrology calc imports ===
from flatlib import ephem, const, angle
from flatlib.chart import Chart
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos

# === Setup ===
PLANETS = [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS,
           const.JUPITER, const.SATURN, const.URANUS, const.NEPTUNE, const.PLUTO]

# Utility
def angle_diff(a, b):
    """ Smallest difference in degrees between two angles """
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d

# Cached planet positions
def cached_positions(times, pos):
    lon_map, dec_map = {}, {}

    for p in PLANETS:
        lons, decs = [], []
        for t in times:
            try:
                dt = Datetime(t.strftime("%Y-%m-%d %H:%M"), pos.timezone)
                chart = Chart(dt, pos)
                obj = chart.get(p)
                lons.append(obj.lon)
                decs.append(obj.lat)
            except Exception:
                lons.append(np.nan)
                decs.append(np.nan)
        lon_map[p] = np.array(lons)
        dec_map[p] = np.array(decs)

    return lon_map, dec_map

# Trigger logic
def trigger_check(times, lon_map, asc_arr, moon_arr):
    alerts = []
    for i, t in enumerate(times):
        asc = asc_arr[i]
        moon = moon_arr[i]

        if isnan(asc) or isnan(moon):
            continue

        # Moon ↔ Asc
        if angle_diff(moon, asc) < 1:
            alerts.append(f"{t}: Moon {moon:.1f}° conjunct Asc {asc:.1f}°")

        # Asc ↔ Planets
        for p, lons in lon_map.items():
            if isnan(lons[i]): 
                continue
            for asp in [0, 90, 120, 180]:
                if angle_diff(asc, lons[i]) < 1 and angle_diff(asc, lons[i]) == asp:
                    alerts.append(f"{t}: Asc {asc:.1f}° {asp}° {p} {lons[i]:.1f}°")

        # Moon ↔ Planets
        for p, lons in lon_map.items():
            if isnan(lons[i]): 
                continue
            for asp in [0, 90, 120, 180]:
                if angle_diff(moon, lons[i]) < 1 and angle_diff(moon, lons[i]) == asp:
                    alerts.append(f"{t}: Moon {moon:.1f}° {asp}° {p} {lons[i]:.1f}°")

    return alerts

# === Streamlit App ===
st.set_page_config(layout="wide")
st.title("📈 Harmonic Vibration Wave Analyzer")

# Inputs
st.sidebar.header("Settings")
lat = st.sidebar.number_input("Latitude", value=39.0)
lon = st.sidebar.number_input("Longitude", value=-105.0)
tz = st.sidebar.text_input("Timezone", "0:00")
start_date = st.sidebar.date_input("Start Date", datetime.utcnow().date())
bars = st.sidebar.number_input("Bars (hours)", value=48)

pos = GeoPos(lat, lon)
times = [start_date + timedelta(hours=i) for i in range(int(bars))]

# Compute
lon_map, dec_map = cached_positions(times, pos)

# Ascendant & Moon arrays
asc_arr, moon_arr = [], []
for t in times:
    try:
        dt = Datetime(t.strftime("%Y-%m-%d %H:%M"), tz)
        chart = Chart(dt, pos)
        asc_arr.append(chart.get(const.ASC).lon)
        moon_arr.append(chart.get(const.MOON).lon)
    except Exception:
        asc_arr.append(np.nan)
        moon_arr.append(np.nan)
asc_arr = np.array(asc_arr)
moon_arr = np.array(moon_arr)

# Display sections
st.subheader("Planetary Positions")
for p in PLANETS:
    st.write(f"{p}: {lon_map[p][-1]:.2f}°")

st.subheader("Trigger Alerts")
alerts = trigger_check(times, lon_map, asc_arr, moon_arr)
if alerts:
    for a in alerts:
        st.write("🔔", a)
else:
    st.write("No exact triggers found in this window.")
