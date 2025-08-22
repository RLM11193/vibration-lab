# app.py  — Vibrations (Ascendant + Moon triggers, Skyfield de421-safe)

import streamlit as st
import math
from datetime import datetime
from skyfield.api import load

# ---- Streamlit must be first ----
st.set_page_config(page_title="Vibrations", layout="wide")

# ---- Skyfield setup ----
# de421.bsp uses *barycenter* names for outer planets.
PLANET_KEY = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars",
    "jupiter": "jupiter barycenter",
    "saturn": "saturn barycenter",
    "uranus": "uranus barycenter",
    "neptune": "neptune barycenter",
    "pluto": "pluto barycenter",
}

@st.cache(allow_output_mutation=True)
def load_kernel():
    eph = load("de421.bsp")
    ts = load.timescale()
    return eph, ts

eph, ts = load_kernel()
earth = eph["earth"]

# ---- Astro helpers ----
def ecliptic_lon(planet_name: str, dt: datetime) -> float:
    """Geocentric ecliptic longitude (degrees, 0–360) using de421 keys safely."""
    key = PLANET_KEY[planet_name.lower()]
    t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute)
    lon, lat, _ = earth.at(t).observe(eph[key]).apparent().ecliptic_latlon()
    return float(lon.degrees % 360.0)

def ascendant_deg(dt: datetime, lon_east_deg: float = -106.13, lat_deg: float = 38.84) -> float:
    """
    Simple Ascendant proxy:
    use local apparent sidereal time (GAST + longitude) as an ecliptic trigger angle.
    (Fast & robust for intraday timing even if not a full astronomical ASC.)
    """
    t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute)
    lst_deg = (t.gast * 15.0 + lon_east_deg) % 360.0
    return lst_deg

def aspect(angle1: float, angle2: float, orb: float = 1.0):
    """Return exact aspect (0,60,90,120,180) within orb, else None."""
    for a in (0, 60, 90, 120, 180):
        d = (angle1 - angle2) % 360.0
        d = min(d, 360.0 - d)
        if abs(d - a) <= orb:
            return a
    return None

# ---- Vibration math ----
def price_vibration(low: float, high: float):
    """Square-root delta → price angle → sin projection."""
    diff = math.sqrt(max(high, 0.0)) - math.sqrt(max(low, 0.0))
    ang = (diff * 180.0) % 360.0
    proj = 144.0 * math.sin(math.radians(ang))
    target = high - proj
    return target, ang

def time_vibration(bars: float):
    """Sqrt(bars) → time angle → cos projection."""
    ang = (math.sqrt(max(bars, 0.0)) * 180.0) % 360.0
    proj = 225.0 * math.cos(math.radians(ang))
    return bars + proj, ang

# ---- UI ----
st.title("Triggers")
st.subheader("Vibration Targets")

with st.sidebar:
    st.header("Inputs")
    low = st.number_input("Swing Low Price", value=100.00, step=0.01, format="%.2f")
    high = st.number_input("Swing High Price", value=200.00, step=0.01, format="%.2f")
    bars = st.number_input("Bars (time units)", value=30, step=1)
    framework_planet = st.selectbox(
        "Framework Planet",
        ["saturn", "jupiter", "mars", "venus", "mercury", "sun"],
        index=0,
    )
    start_date = st.date_input("Start Date", datetime.utcnow().date())
    start_time = st.time_input("Start Time", datetime.utcnow().time())
    # location (east positive)
    lat = st.number_input("Latitude (deg)", value=38.84, step=0.01)
    lon_west = st.number_input("Longitude West (deg, positive=West)", value=106.13, step=0.01)
    lon_east = -float(lon_west)  # convert to east-positive

# Compute vibration targets
ptarget, pang = price_vibration(low, high)
ttarget, tang = time_vibration(bars)
st.write(f"**Price Target:** {ptarget:.2f} (Angle {pang:.2f}°)")
st.write(f"**Time Target (bars):** {ttarget:.2f} (Angle {tang:.2f}°)")

# ---- Planetary framework & triggers ----
st.subheader("Planetary Framework & Triggers")

dt = datetime.combine(start_date, start_time)

try:
    planet_lon = ecliptic_lon(framework_planet, dt)
    moon_lon = ecliptic_lon("moon", dt)
    asc_lon = ascendant_deg(dt, lon_east_deg=lon_east, lat_deg=lat)

    a_pa = aspect(planet_lon, asc_lon)      # Planet ↔ Ascendant
    a_mp = aspect(moon_lon, planet_lon)     # Moon ↔ Planet
    a_ma = aspect(moon_lon, asc_lon)        # Moon ↔ Ascendant

    st.write(f"**{framework_planet.capitalize()} (framework) angle:** {planet_lon:.2f}°")
    st.write(f"**Moon (trigger) angle:** {moon_lon:.2f}°")
    st.write(f"**Ascendant (amplifier) angle:** {asc_lon:.2f}°")

    hits = []
    if a_pa is not None:
        hits.append(f"Framework planet ↔ Ascendant: **{a_pa}°**")
    if a_mp is not None:
        hits.append(f"Moon ↔ Framework planet: **{a_mp}°**")
    if a_ma is not None:
        hits.append(f"Moon ↔ Ascendant: **{a_ma}°**")

    if hits:
        for h in hits:
            st.success(h)
    else:
        st.info("No exact trigger aspects (0/60/90/120/180) within 1.0° orb at the selected time.")

except KeyError as e:
    st.error(
        "Planet key not found in the de421 ephemeris. "
        "Use these names: sun, moon, mercury, venus, mars, jupiter, saturn, uranus, neptune, pluto."
    )
    st.caption(f"Internal error: {e}")
except Exception as e:
    st.error("Unexpected error while computing planetary angles.")
    st.caption(str(e))

st.caption("🔑 Foundation: **Ascendant = amplifier · Moon = timing trigger · Framework planet = cycle.**")
