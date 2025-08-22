import streamlit as st
import numpy as np
from datetime import datetime, date
from skyfield.api import load, wgs84

# --------------- Stable setup (cached) ---------------

@st.cache_resource
def get_timescale_and_ephemeris():
    ts = load.timescale()
    eph = load('de421.bsp')  # auto-downloads once, then cached on Streamlit
    return ts, eph

ts, eph = get_timescale_and_ephemeris()

PLANET_KEYS = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter barycenter",
    "Saturn": "saturn barycenter",
    "Uranus": "uranus barycenter",
    "Neptune": "neptune barycenter",
    "Pluto": "pluto barycenter",
}

# --------------- Math helpers ---------------

def wrap_deg(x: float) -> float:
    return x % 360.0

def ang_diff(a: float, b: float) -> float:
    """Smallest absolute angular difference in degrees."""
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d

def approx_asc_deg(time_obj, lon_deg: float) -> float:
    """
    Simple + fast Ascendant proxy:
      LST ≈ GAST + longitude
      We use LST in degrees as a clean intraday timer (good trigger proxy).
    """
    gast_deg = (time_obj.gast * 15.0) % 360.0
    lst_deg = (gast_deg + lon_deg) % 360.0
    return lst_deg

# --------------- Astro computation ---------------

@st.cache_data(show_spinner=False)
def compute_ecliptic_lons(lat_deg: float, lon_deg: float, start_d: date, hours: int):
    """Return dict of planet→lon arrays + separate arrays for Moon + Asc proxy."""
    observer = wgs84.latlon(latitude_degrees=lat_deg, longitude_degrees=lon_deg)

    times = [ts.utc(start_d.year, start_d.month, start_d.day, h) for h in range(int(hours))]
    # Pre-size containers
    lon_map = {name: np.zeros(len(times), dtype=float) for name in PLANET_KEYS.keys()}

    for i, t in enumerate(times):
        # Asc proxy (LST)
        lon_map.setdefault("ASC", np.zeros(len(times), dtype=float))
        lon_map["ASC"][i] = approx_asc_deg(t, lon_deg)

        # Planet ecliptic longitudes
        for name, key in PLANET_KEYS.items():
            try:
                astrometric = observer.at(t).observe(eph[key]).apparent()
                lon, lat, _ = astrometric.ecliptic_latlon()
                lon_map[name][i] = wrap_deg(lon.degrees)
            except Exception:
                lon_map[name][i] = np.nan  # never crash the app

    return times, lon_map

def find_triggers(times, lon_map, tol_deg: float):
    """Asc ↔ Moon ↔ Planets triggers at 0/90/120/180 ± tolerance."""
    aspects = [0, 90, 120, 180]
    alerts = []
    asc = lon_map["ASC"]
    moon = lon_map["Moon"]

    for i, t in enumerate(times):
        if np.isnan(asc[i]) or np.isnan(moon[i]):
            continue

        # Moon ↔ Asc conjunct
        if ang_diff(moon[i], asc[i]) <= tol_deg:
            alerts.append(f"{t.utc_strftime('%Y-%m-%d %H:%M')} • Moon {moon[i]:.1f}° conjunct ASC {asc[i]:.1f}°")

        # Asc ↔ Planets aspects
        for pname, arr in lon_map.items():
            if pname in ("ASC", "Moon"):  # handled separately
                continue
            if np.isnan(arr[i]):
                continue
            for asp in aspects:
                if abs(ang_diff(asc[i], arr[i]) - asp) <= tol_deg:
                    alerts.append(
                        f"{t.utc_strftime('%Y-%m-%d %H:%M')} • ASC {asc[i]:.1f}° {asp}° {pname} {arr[i]:.1f}°"
                    )

        # Moon ↔ Planets aspects
        for pname, arr in lon_map.items():
            if pname in ("ASC", "Moon"):
                continue
            if np.isnan(arr[i]):
                continue
            for asp in aspects:
                if abs(ang_diff(moon[i], arr[i]) - asp) <= tol_deg:
                    alerts.append(
                        f"{t.utc_strftime('%Y-%m-%d %H:%M')} • Moon {moon[i]:.1f}° {asp}° {pname} {arr[i]:.1f}°"
                    )

    return alerts

# --------------- Vibration math (price–time) ---------------

def vibration_math(price_high: float, price_low: float, swing_bars: int):
    """
    Compact “law of vibration” scaffold:
    - Price angle via sqrt transform
    - ΔP from sin(angle), ΔT from cos(sqrt(bars))
    Returns (target_price, delta_price, delta_time_bars)
    """
    sqrt_high = np.sqrt(max(price_high, 0.0))
    sqrt_low = np.sqrt(max(price_low, 0.0))
    price_angle = (sqrt_high - sqrt_low) * 180.0  # deg

    dP = 144.0 * np.sin(np.radians(price_angle % 360.0))
    dT = 225.0 * np.cos(np.radians((np.sqrt(max(swing_bars, 0)) * 180.0) % 360.0))

    target_price = price_high + dP
    return float(target_price), float(dP), float(dT)

# --------------- UI ---------------

st.set_page_config(page_title="Vibrations", layout="wide")
st.markdown("<h1 style='text-align:center'>📈 Vibrational Harmonics Lab — Gann Fusion</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Location & Window")
    lat = st.number_input("Latitude (°)", value=38.84, step=0.01, format="%.2f")
    lon = st.number_input("Longitude West=− (°)", value=-106.13, step=0.01, format="%.2f")
    start_d = st.date_input("Start date (UTC)", value=date.today())
    hours = st.slider("Scan horizon (hours ahead)", 12, 240, 120, step=12)
    tol = st.slider("Aspect tolerance (°)", 0.2, 2.0, 1.0, step=0.1)

    st.markdown("---")
    st.subheader("Vibration Inputs")
    swing_high = st.number_input("Swing HIGH price", value=45761.88, format="%.2f")
    swing_low = st.number_input("Swing LOW price", value=43335.46, format="%.2f")
    swing_bars = st.number_input("Swing length (bars)", value=34, step=1)

# Compute astro
times, lon_map = compute_ecliptic_lons(lat, lon, start_d, hours)

# Top row: planetary snapshot
colL, colR = st.columns([1, 1])
with colL:
    st.subheader("Planetary ecliptic longitudes (last hour)")
    snap = {k: v[-1] for k, v in lon_map.items() if k != "ASC"}
    lines = [f"• {k:<7}: {snap[k]:6.2f}°" for k in PLANET_KEYS.keys()]
    st.code("\n".join(lines), language="text")

with colR:
    st.subheader("ASC & Moon snapshot (last hour)")
    st.code(f"ASC  : {lon_map['ASC'][-1]:.2f}°\nMoon : {lon_map['Moon'][-1]:.2f}°", language="text")

# Triggers
st.subheader("🔔 Trigger Alerts (ASC ↔ Moon ↔ Planets)")
alerts = find_triggers(times, lon_map, tol)
if alerts:
    for a in alerts:
        st.write("•", a)
else:
    st.info("No exact triggers found in this window under current tolerance.")

# Vibration math section
st.subheader("📐 Vibration Math (ΔP / ΔT)")
target_price, dP, dT = vibration_math(swing_high, swing_low, int(swing_bars))
st.write(f"Swing HIGH: **{swing_high:.2f}**  |  Swing LOW: **{swing_low:.2f}**  |  Bars: **{int(swing_bars)}**")
st.write(f"ΔP (price vibration): **{dP:.2f}**")
st.write(f"ΔT (time vibration, bars): **{dT:.2f}**")
st.success(f"🎯 **Target Price**: {target_price:.2f}")

st.caption("Intraday timing uses ASC; swing confirmation via Moon; framework aligns with Saturn/Jupiter—sidereal proxy via ecliptic longitudes.")
