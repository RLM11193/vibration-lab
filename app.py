# app.py
import streamlit as st
import swisseph as swe
import datetime
import math

# --- Utility functions ---
def wrap_deg(x):
    return x % 360.0

def angular_diff(a, b):
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d

def jd_from_dt_utc(dt):
    return swe.julday(dt.year, dt.month, dt.day,
                      dt.hour + dt.minute/60 + dt.second/3600)

# --- Planet list ---
PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
}

ASPECTS = {
    "Conjunction (0°)": 0,
    "Sextile (60°)": 60,
    "Square (90°)": 90,
    "Trine (120°)": 120,
    "Opposition (180°)": 180,
}

# --- Core calculation ---
def get_positions(jd, lat, lon, sidereal=False):
    flags = swe.FLG_MOSEPH
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL

    positions = {}
    for name, pid in PLANETS.items():
        try:
            lon, _lat, _dist, _speed = swe.calc_ut(jd, pid, flags)
            positions[name] = wrap_deg(lon)
        except Exception as e:
            positions[name] = float("nan")

    # Ascendant / Houses
    try:
        cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags)
        positions["Ascendant"] = wrap_deg(ascmc[0])
    except Exception:
        positions["Ascendant"] = float("nan")

    return positions

# --- Triggers logic ---
def check_triggers(positions):
    events = []
    asc = positions.get("Ascendant", float("nan"))
    moon = positions.get("Moon", float("nan"))

    if math.isnan(asc) or math.isnan(moon):
        return ["Ascendant or Moon not available"]

    # Asc → Moon trigger
    for name, lon in positions.items():
        if name in ["Ascendant", "Moon"] or math.isnan(lon):
            continue
        for aspect_name, aspect_angle in ASPECTS.items():
            if angular_diff(moon, lon) < 2:  # ±2° orb
                events.append(f"Moon triggered {name} ({aspect_name})")

    # Ascendant → Moon trigger
    for aspect_name, aspect_angle in ASPECTS.items():
        if angular_diff(asc, moon) < 2:
            events.append(f"Ascendant triggered Moon ({aspect_name})")

    return events if events else ["No exact triggers now"]

# --- Streamlit UI ---
def main():
    st.title("Gann Astro-Vibration Scanner")

    # Inputs
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("Date", datetime.date.today())
        time = st.time_input("Time (UTC)", datetime.datetime.utcnow().time())
    with col2:
        lat = st.number_input("Latitude", -90.0, 90.0, 39.0)
        lon = st.number_input("Longitude", -180.0, 180.0, -105.0)
        sidereal = st.checkbox("Use Sidereal (Lahiri)", value=True)

    # JD
    dt = datetime.datetime.combine(date, time)
    jd = jd_from_dt_utc(dt)

    # Positions
    positions = get_positions(jd, lat, lon, sidereal)

    st.subheader("Planetary Longitudes")
    for name, lon in positions.items():
        st.write(f"{name}: {lon:.2f}°")

    # Aspects
    st.subheader("Aspects to Ascendant & Moon")
    events = check_triggers(positions)
    for e in events:
        st.write("- " + e)

if __name__ == "__main__":
    main()
