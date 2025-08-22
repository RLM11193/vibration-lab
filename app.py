import streamlit as st
import math
import datetime
import swisseph as swe

# ---------------------------
# Utility Functions
# ---------------------------

def digital_root(n: int) -> int:
    return 1 + ((n - 1) % 9) if n > 0 else 0

# Pythagorean/Chaldean mapping
PLANET_MAP = {
    1: "Sun", 2: "Moon", 3: "Jupiter",
    4: "Rahu", 5: "Mercury", 6: "Venus",
    7: "Ketu", 8: "Saturn", 9: "Mars"
}

def numerology_planet(value: float):
    return PLANET_MAP[digital_root(int(round(value)))]

def sincos_projection(anchor_price, direction, theta_deg, swing_range):
    theta = math.radians(theta_deg)
    A = 0.618 * swing_range
    B = 0.382 * swing_range
    dP_sin = A * math.sin(theta)
    dP_cos = B * math.cos(theta)
    return anchor_price + direction * (dP_sin + dP_cos)

def square_of_nine_prices(anchor_price, steps=8):
    r0 = math.sqrt(anchor_price)
    results = []
    for k in range(1, steps+1):
        angle = 45 * k
        r = r0 + (angle/360)
        results.append(r**2)
    return results

def planetary_day_hour_ruler(dt, lat, lon):
    weekday = dt.weekday()  # Monday=0
    day_rulers = ["Moon","Mars","Mercury","Jupiter","Venus","Saturn","Sun"]
    day_ruler = day_rulers[weekday]

    # simple hour ruler cycle
    seq = ["Saturn","Jupiter","Mars","Sun","Venus","Mercury","Moon"]
    start = seq.index(day_ruler)
    elapsed_hours = dt.hour
    hour_ruler = seq[(start + elapsed_hours) % 7]

    return day_ruler, hour_ruler

# ---------------------------
# Main App
# ---------------------------

st.set_page_config(page_title="Gann Harmonic Vibration Analyzer", layout="wide")
st.title("📐 Harmonic Vibration Forecast")

st.sidebar.header("Inputs")

anchor_price = st.sidebar.number_input("Anchor Price", value=100.0, format="%.2f")
swing_high   = st.sidebar.number_input("Swing High", value=110.0, format="%.2f")
swing_low    = st.sidebar.number_input("Swing Low", value=90.0, format="%.2f")
bars_between = st.sidebar.number_input("Bars Between Swings", value=30, step=1)

date_anchor  = st.sidebar.date_input("Anchor Date", value=datetime.date.today())
lat = st.sidebar.number_input("Latitude", value=39.0, format="%.2f")
lon = st.sidebar.number_input("Longitude", value=-105.0, format="%.2f")

helio = st.sidebar.checkbox("Heliocentric Framework (Jup/Sat)")

# ---------------------------
# Compute
# ---------------------------

swing_range = swing_high - swing_low
direction   = 1 if anchor_price < swing_high else -1

# Numerology planets
p_price = numerology_planet(anchor_price)
p_range = numerology_planet(abs(swing_range))
p_time  = numerology_planet(bars_between)

st.subheader("🔢 Numerology Mapping")
st.write(f"Price → {p_price}, Range → {p_range}, Time → {p_time}")

# Candidate degrees (example harmonic echoes)
degrees = [0, 45, 90, 120, 135, 180, 225, 270, 300, 315, 360]

best = None
best_score = -999
best_info = None

for deg in degrees:
    # Price targets
    p_sincos = sincos_projection(anchor_price, direction, deg, swing_range)
    p_spiral = anchor_price + direction * math.sqrt(abs(swing_range)) * math.cos(math.radians(deg))
    p_mid = (p_sincos + p_spiral) / 2

    # Square of Nine
    sq9 = square_of_nine_prices(anchor_price)
    near_sq9 = any(abs(p_mid - x) < 2.0 for x in sq9)

    # Scoring
    score = 0
    if abs(p_sincos - p_spiral) < 1.0: score += 3
    else: score += 1
    if near_sq9: score += 2

    # Numerology boost
    if p_price in [p_price, p_range, p_time]: score += 2

    if score > best_score:
        best_score = score
        best = deg
        best_info = (p_sincos, p_spiral, p_mid)

# ---------------------------
# Output
# ---------------------------

st.subheader("📊 Best Harmonic Target")
if best is not None:
    p_sincos, p_spiral, p_mid = best_info
    st.write(f"**Degree:** {best}°")
    st.write(f"Sin/Cos Price: {p_sincos:.2f}")
    st.write(f"Spiral Price: {p_spiral:.2f}")
    st.write(f"Midpoint Price: {p_mid:.2f}")
    st.write(f"**Score:** {best_score}")

st.caption("This combines numerology, harmonic degrees, sin/cos projection, spiral mapping, and Square-of-Nine checks. Stations, declinations, lunar phases, and planetary rulers can be layered in next.")
