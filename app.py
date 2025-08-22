import streamlit as st
import numpy as np
from datetime import datetime, timedelta
from skyfield.api import load, Topos

# === Setup ===
planets = load('de421.bsp')
ts = load.timescale()

planet_map = {
    "Sun": planets['sun'],
    "Moon": planets['moon'],
    "Mercury": planets['mercury'],
    "Venus": planets['venus'],
    "Mars": planets['mars'],
    "Jupiter": planets['jupiter barycenter'],
    "Saturn": planets['saturn barycenter'],
    "Uranus": planets['uranus barycenter'],
    "Neptune": planets['neptune barycenter'],
    "Pluto": planets['pluto barycenter']
}

# === Utility ===
def wrap_angle(deg):
    return deg % 360

def angle_diff(a, b):
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d

# === Cached positions ===
def compute_positions(times, observer):
    lon_map = {}
    for pname, pobj in planet_map.items():
        lons = []
        for t in times:
            astrometric = observer.at(t).observe(pobj).apparent()
            lon, lat, dist = astrometric.ecliptic_latlon()
            lons.append(wrap_angle(lon.degrees))
        lon_map[pname] = np.array(lons)
    return lon_map

# === Triggers ===
def trigger_check(times, lon_map, asc_arr, moon_arr):
    alerts = []
    for i, t in enumerate(times):
        asc = asc_arr[i]
        moon = moon_arr[i]
        if np.isnan(asc) or np.isnan(moon):
            continue

        # Moon ↔ Asc
        if angle_diff(moon, asc) < 1:
            alerts.append(f"{t.utc_strftime('%Y-%m-%d %H:%M')} | Moon {moon:.1f}° conjunct Asc {asc:.1f}°")

        # Asc ↔ Planets
        for pname, lons in lon_map.items():
            for asp in [0, 90, 120, 180]:
                if abs(angle_diff(asc, lons[i]) - asp) < 1:
                    alerts.append(f"{t.utc_strftime('%Y-%m-%d %H:%M')} | Asc {asc:.1f}° {asp}° {pname} {lons[i]:.1f}°")

        # Moon ↔ Planets
        for pname, lons in lon_map.items():
            for asp in [0, 90, 120, 180]:
                if abs(angle_diff(moon, lons[i]) - asp) < 1:
                    alerts.append(f"{t.utc_strftime('%Y-%m-%d %H:%M')} | Moon {moon:.1f}° {asp}° {pname} {lons[i]:.1f}°")

    return alerts

# === Vibration Math ===
def vibration_math(price_high, price_low, bars):
    sqrt_high = np.sqrt(price_high)
    sqrt_low = np.sqrt(price_low)
    price_angle = (sqrt_high - sqrt_low) * 180

    # Price projection
    delta_p = 144 * np.sin(np.radians(price_angle % 360))
    target_price = price_high + delta_p

    # Time projection
    delta_t = 225 * np.cos(np.radians(np.sqrt(bars) * 180 % 360))

    return target_price, delta_p, delta_t

# === Streamlit App ===
st.set_page_config(layout="wide")
st.title("📈 Vibrational Harmonics Lab — Gann Fusion")

# Sidebar Inputs
st.sidebar.header("Astro Settings")
lat = st.sidebar.number_input("Latitude", value=39.0)
lon = st.sidebar.number_input("Longitude", value=-105.0)
start_date = st.sidebar.date_input("Start Date", datetime.utcnow().date())
bars = st.sidebar.number_input("Bars (hours)", value=72)

observer = Topos(latitude_degrees=lat, longitude_degrees=lon)
times = [ts.utc(start_date.year, start_date.month, start_date.day, h) for h in range(int(bars))]

# Planetary positions
lon_map = compute_positions(times, observer)
asc_arr = np.array([(t.gast * 15) % 360 for t in times])  # Simplified Ascendant
moon_arr = lon_map["Moon"]

# --- Planetary Triggers ---
st.subheader("🔔 Trigger Alerts")
alerts = trigger_check(times, lon_map, asc_arr, moon_arr)
if alerts:
    for a in alerts:
        st.write("⚡", a)
else:
    st.write("No exact astro triggers in this window.")

# --- Vibration Math ---
st.sidebar.header("Price-Time Settings")
price_high = st.sidebar.number_input("Swing High", value=3438.84)
price_low = st.sidebar.number_input("Swing Low", value=3295.00)
time_bars = st.sidebar.number_input("Bars (swing length)", value=30)

target_price, delta_p, delta_t = vibration_math(price_high, price_low, time_bars)

st.subheader("📐 Vibration Math Results")
st.write(f"Swing High: {price_high}, Swing Low: {price_low}, Bars: {time_bars}")
st.write(f"ΔP (price vibration): {delta_p:.2f}")
st.write(f"ΔT (time vibration): {delta_t:.2f}")
st.write(f"🎯 Target Price: {target_price:.2f}")
