import streamlit as st
import numpy as np
from skyfield.api import load, Topos
from datetime import datetime, timedelta
import math

# ✅ Must be first
st.set_page_config(page_title="Vibrations", layout="wide")

# Load planetary data
planets = load('de421.bsp')
earth = planets['earth']
ts = load.timescale()

# Location (BV, Colorado – change if needed)
observer = Topos(latitude_degrees=38.84, longitude_degrees=-106.13)

# Utility: planetary longitude (tropical for now, can add Lahiri sidereal later)
def planetary_longitude(planet_name, date_time):
    t = ts.utc(date_time.year, date_time.month, date_time.day, date_time.hour, date_time.minute)
    astrometric = earth.at(t).observe(planets[planet_name])
    apparent = astrometric.apparent()
    lon, lat, distance = apparent.ecliptic_latlon()
    return lon.degrees % 360

# Utility: Ascendant degree
def ascendant_longitude(date_time):
    t = ts.utc(date_time.year, date_time.month, date_time.day, date_time.hour, date_time.minute)
    astrometric = (earth + observer).at(t)
    ra, dec, distance = astrometric.radec()
    # Use Earth rotation angle as proxy for Ascendant
    gst = t.gast
    asc = (gst * 15) % 360
    return asc

# Aspect check
def check_aspects(angle1, angle2, orb=1.0):
    aspects = [0, 60, 90, 120, 180]
    for a in aspects:
        if abs((angle1 - angle2) % 360 - a) <= orb or abs((angle2 - angle1) % 360 - a) <= orb:
            return a
    return None

# Sidebar inputs
st.sidebar.header("Inputs")
swing_low = st.sidebar.number_input("Swing Low Price", value=100.0, step=0.1)
swing_high = st.sidebar.number_input("Swing High Price", value=200.0, step=0.1)
bars = st.sidebar.number_input("Bars (time units)", value=30, step=1)
target_planet = st.sidebar.selectbox("Framework Planet", ["saturn", "jupiter", "mars", "venus", "mercury", "sun"])
start_date = st.sidebar.date_input("Start Date", datetime.utcnow().date())
start_time = st.sidebar.time_input("Start Time", datetime.utcnow().time())

# Main title
st.title("📊 Vibrational Harmonics with Ascendant & Moon Triggers")

# Price vibration
def price_vibration(low, high):
    diff = math.sqrt(high) - math.sqrt(low)
    angle = (diff * 180) % 360
    projection = 144 * math.sin(math.radians(angle))
    target = high - projection
    return target, angle

# Time vibration
def time_vibration(bars):
    angle = (math.sqrt(bars) * 180) % 360
    projection = 225 * math.cos(math.radians(angle))
    return bars + projection, angle

# Run calculations
price_target, price_angle = price_vibration(swing_low, swing_high)
time_target, time_angle = time_vibration(bars)

st.subheader("Vibration Targets")
st.write(f"**Price Target:** {price_target:.2f} (Angle {price_angle:.2f}°)")
st.write(f"**Time Target (bars):** {time_target:.2f} (Angle {time_angle:.2f}°)")

# Planetary framework
dt = datetime.combine(start_date, start_time)
planet_angle = planetary_longitude(target_planet, dt)
moon_angle = planetary_longitude("moon", dt)
asc_angle = ascendant_longitude(dt)

aspect_planet_asc = check_aspects(planet_angle, asc_angle)
aspect_moon_planet = check_aspects(moon_angle, planet_angle)
aspect_moon_asc = check_aspects(moon_angle, asc_angle)

# Display planetary triggers
st.subheader("Planetary Framework & Triggers")
st.write(f"**{target_planet.capitalize()} (Framework) angle:** {planet_angle:.2f}°")
st.write(f"**Moon (Trigger) angle:** {moon_angle:.2f}°")
st.write(f"**Ascendant (Amplifier) angle:** {asc_angle:.2f}°")

if aspect_planet_asc:
    st.success(f"Framework planet ↔ Ascendant aspect: {aspect_planet_asc}°")
if aspect_moon_planet:
    st.success(f"Moon trigger ↔ Framework planet aspect: {aspect_moon_planet}°")
if aspect_moon_asc:
    st.success(f"Moon trigger ↔ Ascendant aspect: {aspect_moon_asc}°")

if not any([aspect_planet_asc, aspect_moon_planet, aspect_moon_asc]):
    st.info("No exact trigger aspects at this moment.")

st.caption("🔑 Foundation: **Ascendant = amplifier, Moon = timing trigger, Planets = framework cycle.**")
