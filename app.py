# Vibration Lab — Full Harmonic + Trigger Ladder (stable, phone-friendly)
# Requires: streamlit, pyswisseph, numpy, pandas, pytz

import math
import datetime as dt
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import pytz
import streamlit as st
import swisseph as swe

# =========================================
# CONFIG / CONSTANTS
# =========================================

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN
}
PLANET_ORDER = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]

ASPECTS = {0:6.0, 60:4.0, 90:6.0, 120:6.0, 180:6.0}       # deg : default orb
SQ9_STEP_DEGS = [45,90,135,180,225,270,315,360]

# guardrails
MAX_SCAN_POINTS = 4000
MAX_WINDOW_DAYS = 30
VALID_YEAR_RANGE = (1900, 2099)

# tolerances
DEC_TOL = 0.30         # declination parallel/contra
PHASE_TOL = 3.0        # near 0/90/180/270
PADA_GATE_TOL = 0.10   # within 0.10° of a pada boundary

# =========================================
# STREAMLIT SETUP
# =========================================

st.set_page_config(page_title="Vibration Lab — Law of Vibration", layout="wide")
st.title("Vibration Lab — Law of Vibration (Full Engine)")

# =========================================
# EPHEMERIS FLAGS / SIDEREAL
# =========================================

@st.cache_resource(show_spinner=False)
def get_ephe_flags() -> int:
    """
    Use Swiss files if present, else Moshier (no external files needed on Streamlit Cloud).
    """
    try:
        swe.set_ephe_path("./ephe")
        return swe.FLG_SWIEPH
    except Exception:
        return swe.FLG_MOSEPH

EPH_FLAGS = get_ephe_flags()
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)  # Lahiri for nakshatra/pada

# =========================================
# UTILS
# =========================================

def wrap_deg(x: float) -> float:
    return x % 360.0

def dmin(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return d if d <= 180 else 360-d

def jd_from_dt_utc(t: dt.datetime) -> float:
    return swe.julday(t.year, t.month, t.day, t.hour + t.minute/60 + t.second/3600.0)

def digital_root(n: int) -> int:
    return 1 + ((n - 1) % 9) if n > 0 else 0

PLANET_MAP = {1:"Sun",2:"Moon",3:"Jupiter",4:"Rahu",5:"Mercury",6:"Venus",7:"Ketu",8:"Saturn",9:"Mars"}

def numerology_planet(value: float) -> str:
    return PLANET_MAP[digital_root(int(round(abs(value))))]

def square_of_nine_prices(anchor_price: float) -> List[float]:
    r0 = math.sqrt(max(anchor_price, 1e-8))
    return [(r0 + step/360.0)**2 for step in SQ9_STEP_DEGS]

def sincos_projection(anchor_price: float, direction: int, theta_deg: float, swing_range: float) -> float:
    theta = math.radians(theta_deg)
    A = 0.618 * swing_range
    B = 0.382 * swing_range
    return anchor_price + direction * (A*math.sin(theta) + B*math.cos(theta))

def spiral_projection(anchor_price: float, direction: int, theta_deg: float, swing_range: float) -> float:
    # light √-spiral proxy aligned to angle; sufficiently fast for Cloud
    return anchor_price + direction * math.sqrt(abs(swing_range)) * math.cos(math.radians(theta_deg))

# Robust Ascendant with house fallback
def ascendant_deg(t_utc: dt.datetime, lat: float, lon_east: float, flags: int) -> float:
    jd = jd_from_dt_utc(t_utc)
    for sys in (b'P', b'K', b'E'):  # Placidus → Koch → Equal
        try:
            _cusps, ascmc = swe.houses_ex(jd, flags, lat, lon_east, sys)
            return wrap_deg(float(ascmc[0]))
        except Exception:
            continue
    # last resort equal houses
    try:
        _cusps, ascmc = swe.houses(jd, lat, lon_east, 'E')
        return wrap_deg(float(ascmc[0]))
    except Exception:
        return float("nan")

def planet_lon(t_utc: dt.datetime, planet: str, flags: int, helio=False) -> float:
    pid = PLANET_IDS[planet]
    jdu = jd_from_dt_utc(t_utc)
    flg = flags | (swe.FLG_HELCTR if helio else 0)
    lon = swe.calc_ut(jdu, pid, flg)[0]
    return wrap_deg(float(lon))

def planet_dec(t_utc: dt.datetime, planet: str, flags: int, helio=False) -> float:
    pid = PLANET_IDS[planet]
    jdu = jd_from_dt_utc(t_utc)
    flg = flags | swe.FLG_EQUATORIAL | (swe.FLG_HELCTR if helio else 0)
    return float(swe.calc_ut(jdu, pid, flg)[1])  # declination in degrees

def moon_phase_deg(t_utc: dt.datetime, flags: int) -> float:
    jdu = jd_from_dt_utc(t_utc)
    lon_sun  = swe.calc_ut(jdu, swe.SUN, flags)[0]
    lon_moon = swe.calc_ut(jdu, swe.MOON, flags)[0]
    return wrap_deg(lon_moon - lon_sun)

def near_station(t_utc: dt.datetime, planet: str, flags: int, helio=False, thresh=0.05) -> bool:
    lon0 = planet_lon(t_utc - dt.timedelta(days=1), planet, flags, helio)
    lon1 = planet_lon(t_utc + dt.timedelta(days=1), planet, flags, helio)
    spd = wrap_deg(lon1 - lon0) / 2.0
    return abs(spd) < thresh

# Sidereal Moon longitude → nakshatra/pada (Lahiri)
NAK_SIZE = 360.0 / 27.0          # 13°20'
PADA_SIZE = NAK_SIZE / 4.0       # 3°20'
NAK_NAMES = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu","Pushya","Ashlesha",
    "Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha",
    "Mula","Purva Ashadha","Uttara Ashadha","Shravana","Dhanishtha","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"
]

def moon_sidereal_lon(t_utc: dt.datetime, flags: int) -> float:
    jdu = jd_from_dt_utc(t_utc)
    lon_moon = swe.calc_ut(jdu, swe.MOON, flags)[0]
    ayan = swe.get_ayanamsa_ut(jdu)
    return wrap_deg(lon_moon - ayan)

# =========================================
# CACHES
# =========================================

@st.cache_data(show_spinner=False)
def cached_positions(times_utc: List[str], helio_framework: bool, flags: int):
    times = [dt.datetime.fromisoformat(t) for t in times_utc]
    lon_map, dec_map = {}, {}
    for p in PLANET_ORDER:
        helio_p = helio_framework and p in ("Jupiter","Saturn")
        lon_map[p] = np.fromiter((planet_lon(t, p, flags, helio_p) for t in times), dtype=float)
        dec_map[p] = np.fromiter((planet_dec(t, p, flags, helio_p) for t in times), dtype=float)
    moon_sid = np.fromiter((moon_sidereal_lon(t, flags) for t in times), dtype=float)
    station_map = {p: np.fromiter((near_station(t, p, flags, helio_framework and p in ("Jupiter","Saturn")) for t in times), dtype=bool)
                   for p in PLANET_ORDER}
    phase_arr = np.fromiter((moon_phase_deg(t, flags) for t in times), dtype=float)
    return lon_map, dec_map, moon_sid, station_map, phase_arr

# =========================================
# SIDEBAR INPUTS
# =========================================

with st.sidebar:
    st.header("1) Swings / Anchor")
    swing_low_price  = st.number_input("Swing LOW price", value=43335.46, format="%.2f")
    swing_high_price = st.number_input("Swing HIGH price", value=45761.88, format="%.2f")
    anchor_price     = st.number_input("Anchor price (pivot)", value=43335.46, format="%.2f")
    bars_between     = st.number_input("Bars between Low↔High", value=506, step=1, min_value=1)

    st.header("2) Projection")
    anchor_from = st.radio("Anchor to project from", ["Low","High"], index=1, horizontal=True)
    bar_minutes = st.number_input("Bar interval (minutes)", value=60, step=1, min_value=1)
    horizon_hours = st.slider("Scan horizon (hours from anchor)", 6, 240, 144)

    st.header("3) Location")
    lat = st.number_input("Latitude (deg)", value=38.84)
    lon_west = st.number_input("Longitude West (deg, positive=West)", value=106.13)
    lon_east = -float(lon_west)

    st.header("4) Timezone & Anchor Timestamp")
    tz_name = st.selectbox("Timezone", ["America/Denver","UTC","America/New_York","Europe/London","Asia/Kolkata"], index=0)
    tz_loc  = pytz.timezone(tz_name)
    now_local = dt.datetime.now(tz_loc)
    anchor_date = st.date_input("Anchor DATE (pivot timestamp)", value=now_local.date())
    anchor_time = st.time_input("Anchor TIME (local tz)", value=now_local.time().replace(second=0, microsecond=0))
    anchor_local_dt = tz_loc.localize(dt.datetime.combine(anchor_date, anchor_time))
    anchor_utc_dt   = anchor_local_dt.astimezone(pytz.utc)

    st.header("5) Options")
    helio_framework = st.checkbox("Use Heliocentric for Jupiter/Saturn (framework)", value=False)
    include_aspects = st.checkbox("Show Aspects Explorer", value=True)
    show_decl = st.checkbox("Add Declination Parallels/Contra", value=True)
    show_station = st.checkbox("Add Station badges", value=True)
    show_phase = st.checkbox("Add Phase & Nakshatra/Pada", value=True)

# year guardrail
today = dt.date.today()
if not (VALID_YEAR_RANGE[0] <= today.year <= VALID_YEAR_RANGE[1]):
    st.error("Year out of supported range.")
    st.stop()

# swing meta
swing_range = abs(swing_high_price - swing_low_price)
direction = 1 if anchor_from == "Low" else -1

# numerology
p_price = numerology_planet(anchor_price)
p_range = numerology_planet(swing_range)
p_time  = numerology_planet(bars_between)

with st.container(border=True):
    st.subheader("🔢 Numerology")
    st.write(f"Price → **{p_price}**, Range → **{p_range}**, Time → **{p_time}**")

# =========================================
# HARMONIC PRICE ENGINE
# =========================================

deg_candidates = [0,45,60,90,120,135,180,225,240,270,300,315,330,360]
sq9_targets = square_of_nine_prices(anchor_price)

best_angle = None
best_score = -1e9
best_prices = None

for deg in deg_candidates:
    p_sincos = sincos_projection(anchor_price, direction, deg, swing_range)
    p_spiral = spiral_projection(anchor_price, direction, deg, swing_range)
    agree = abs(p_sincos - p_spiral) < max(0.001*anchor_price, 1.0)
    p_mid = (p_sincos + p_spiral)/2.0
    near_sq9 = any(abs(p_mid - x) <= max(0.0008*anchor_price, 2.0) for x in sq9_targets)

    score = 0
    score += 3 if agree else 1
    score += 2 if near_sq9 else 0
    # numerology bias
    bias = 0
    for tag in (p_price, p_range, p_time):
        if tag in ("Jupiter","Saturn"): bias += 2
        elif tag in ("Sun","Moon","Mercury","Venus","Mars"): bias += 1
    score += bias

    if score > best_score:
        best_score, best_angle, best_prices = score, deg, (p_sincos, p_spiral, p_mid, agree, near_sq9)

with st.container(border=True):
    st.subheader("🎯 Final price projection (harmonic)")
    if best_prices:
        p_sincos, p_spiral, p_mid, agree, near_sq9 = best_prices
        st.markdown(
            f"""**Best angle:** `{best_angle}°`  
**Price (sin/cos):** `{p_sincos:,.2f}` — **Price (spiral):** `{p_spiral:,.2f}`  
**Final price (midpoint):** **`{p_mid:,.2f}`**  
Confluence: {"sin≈cos ✓" if agree else "sin≠cos —"}, {"Square-of-Nine ✓" if near_sq9 else "Square-of-Nine —"}  
**Score:** `{best_score}`"""
        )

# =========================================
# ASCENDANT → MOON TRIGGER LADDER
# =========================================

st.subheader("⏱ Ascendant → 🌙 Moon Trigger Ladder")

def ascendant_hit_times(start_utc: dt.datetime, end_utc: dt.datetime,
                        lat: float, lon_east: float, target_deg: float,
                        flags: int, step_min: int = 5, tol_deg: float = 1.0):
    """Scan Asc for crossings; refine by bisection."""
    hits = []
    t = start_utc
    step = dt.timedelta(minutes=step_min)

    def wrapdiff(a,b): return ((a-b+180)%360)-180
    def asc(tu): return ascendant_deg(tu, lat, lon_east, flags)

    prev = wrapdiff(asc(t), target_deg)
    while t <= end_utc:
        t2 = t + step
        cur = wrapdiff(asc(t2), target_deg)
        if prev * cur <= 0:  # crossed
            a, b = t, t2
            for _ in range(12):
                m = a + (b-a)/2
                dm = wrapdiff(asc(m), target_deg)
                if abs(dm) <= tol_deg:
                    hits.append(m); break
                da = wrapdiff(asc(a), target_deg)
                if da * dm <= 0: b = m
                else:            a = m
        t, prev = t2, cur
    return hits

def moon_trigger_time(center_utc: dt.datetime, target_deg: float, flags: int,
                      search_min: int = 90, step_min: int = 5, tol_deg: float = 1.0):
    """Search around Asc hit for Moon on target degree; return (trigger_time_utc or None, within_tol)."""
    def wrapdiff(a,b): return ((a-b+180)%360)-180
    def moonlon(tu):  return wrap_deg(swe.calc_ut(jd_from_dt_utc(tu), swe.MOON, flags)[0])

    start = center_utc - dt.timedelta(minutes=search_min)
    end   = center_utc + dt.timedelta(minutes=search_min)
    step  = dt.timedelta(minutes=step_min)

    prev_t = start
    prev_d = wrapdiff(moonlon(prev_t), target_deg)
    t = start + step
    while t <= end:
        d = wrapdiff(moonlon(t), target_deg)
        if prev_d * d <= 0:
            # refine
            a, b = prev_t, t
            for _ in range(12):
                m = a + (b-a)/2
                dm = wrapdiff(moonlon(m), target_deg)
                if abs(dm) <= tol_deg:
                    return (m, True)
                da = wrapdiff(moonlon(a), target_deg)
                if da * dm <= 0: b = m
                else:            a = m
            return (t, abs(d) <= tol_deg)
        prev_t, prev_d = t, d
        t += step
    # fallback: soft check at center
    d0 = abs(wrapdiff(moonlon(center_utc), target_deg))
    return (center_utc if d0 <= tol_deg else None, d0 <= tol_deg)

# Build targets for time: framework (Jup/Sat) + harmonic best θ & θ+180
framework_targets = []
try:
    jup_deg = planet_lon(anchor_utc_dt, "Jupiter", EPH_FLAGS, helio_framework)
    sat_deg = planet_lon(anchor_utc_dt, "Saturn",  EPH_FLAGS, helio_framework)
    framework_targets += [("Jupiter", jup_deg, 3), ("Saturn", sat_deg, 3)]
except Exception:
    pass

harmonic_targets = []
if best_angle is not None:
    theta = float(best_angle) % 360.0
    harmonic_targets = [(f"θ={theta:.0f}°", theta, 2),
                        (f"θ+180={(theta+180)%360:.0f}°", (theta+180)%360.0, 2)]

targets_for_time = framework_targets + harmonic_targets

start_utc = anchor_utc_dt
end_utc   = anchor_utc_dt + dt.timedelta(hours=horizon_hours)

ladder_rows = []  # (score, local_time, label, deg, bars_from_anchor, moon_time_local or None, flags_str)

ASC_STEP_MIN    = 5
ASC_TOL_DEG     = 1.0
MOON_SEARCH_MIN = 90
MOON_STEP_MIN   = 5

final_price_projection = None
if best_prices:
    _, _, final_price_projection, _, _ = best_prices

for label, deg, w in targets_for_time:
    asc_hits = ascendant_hit_times(start_utc, end_utc, lat, lon_east, deg, EPH_FLAGS,
                                   step_min=ASC_STEP_MIN, tol_deg=ASC_TOL_DEG)
    for hit in asc_hits:
        bars = max(1, round((hit - anchor_utc_dt).total_seconds() / 60 / bar_minutes))
        t_moon, moon_ok = moon_trigger_time(hit, deg, EPH_FLAGS,
                                            search_min=MOON_SEARCH_MIN, step_min=MOON_STEP_MIN, tol_deg=ASC_TOL_DEG)
        score = 0
        score += 2 * w
        if moon_ok: score += w
        score += max(0, 6 - int(bars // 50))  # mild recency preference
        flags = []
        if label in ("Jupiter","Saturn"): flags.append("Framework")
        if moon_ok: flags.append("Moon✓")
        if label.startswith("θ"): flags.append("Harmonic"); score += 1

        ladder_rows.append((
            score,
            hit.astimezone(tz_loc),
            label,
            deg,
            bars,
            (t_moon.astimezone(tz_loc) if (t_moon and moon_ok) else None),
            " · ".join(flags)
        ))

ladder_rows.sort(key=lambda r: (-r[0], r[1]))

if not ladder_rows:
    st.info("No Asc hits found in the horizon. Try widening tolerance or extending hours.")
else:
    for i, (score, tloc, lbl, deg, bars, tmoon, fl) in enumerate(ladder_rows[:8], start=1):
        moon_txt = f" → Moon {tmoon.strftime('%a %b %d, %H:%M %Z')}" if tmoon else ""
        st.write(f"{i}. **{tloc.strftime('%a %b %d, %H:%M %Z')}** — ASC≈**{lbl}** ({deg:.2f}°)"
                 f" · bars **{bars}** · score **{score}** {moon_txt} {(' · '+fl) if fl else ''}")

st.markdown("### ✅ Final Unified Prediction")
if ladder_rows and final_price_projection is not None:
    score, tloc, lbl, deg, bars, tmoon, fl = ladder_rows[0]
    when_str = (tmoon.strftime('%A %b %d, %H:%M %Z') if tmoon else tloc.strftime('%A %b %d, %H:%M %Z'))
    st.markdown(
        f"**Time:** {when_str}  \n"
        f"**Price:** **{final_price_projection:,.2f}**  \n"
        f"Target: **{lbl}** ({deg:.2f}°) · Bars: **{bars}** · {fl or ''}"
    )
else:
    st.write("No unified call yet. Ensure a price projection exists and at least one Asc→Moon event is in range.")

# =========================================
# ASPECTS EXPLORER (with stations, declination, phase, nakshatra)
# =========================================

if include_aspects:
    st.subheader("🜁 Aspects Explorer")

    colA, colB, colC, colD = st.columns(4)
    with colA:
        window_days = st.number_input("Window (± days from now)", value=2, min_value=1, max_value=MAX_WINDOW_DAYS)
    with colB:
        step_min = st.number_input("Step (minutes)", value=60, min_value=5, max_value=240)
    with colC:
        orb_override = st.number_input("Orb (deg, 0 = defaults)", value=0.0, step=0.1, format="%.1f")
    with colD:
        dec_tol = st.number_input("Declination tol (°)", value=DEC_TOL, step=0.05, format="%.2f")

    start_scan = dt.datetime.utcnow() - dt.timedelta(days=window_days)
    end_scan   = dt.datetime.utcnow() + dt.timedelta(days=window_days)
    total_minutes = int((end_scan - start_scan).total_seconds() / 60)
    n_points = 1 + total_minutes // int(step_min)
    if n_points > MAX_SCAN_POINTS:
        st.warning(f"Limiting to {MAX_SCAN_POINTS} samples (requested {n_points}). Increase step or reduce window.")
        n_points = MAX_SCAN_POINTS

    times = [start_scan + dt.timedelta(minutes=i*step_min) for i in range(n_points)]
    times_iso = [t.replace(microsecond=0).isoformat() for t in times]

    with st.spinner("Computing planetary positions…"):
        lon_map, dec_map, moon_sid_arr, station_map, phase_arr = cached_positions(times_iso, helio_framework, EPH_FLAGS)

    asp_orbs = {a:(orb_override if orb_override>0 else ASPECTS[a]) for a in ASPECTS}
    rows = []
    for idx, t in enumerate(times):
        moon_dec = dec_map["Moon"][idx]
        phase = phase_arr[idx]
        phase_gate = any(abs(phase - q) <= PHASE_TOL for q in (0,90,180,270))

        # nakshatra/pada from cached sidereal Moon
        s_lon = moon_sid_arr[idx]
        nidx = int(s_lon // (360/27))
        rem = s_lon - nidx*(360/27)
        pada = int(rem // ((360/27)/4)) + 1
        rem_in_pada = rem % ((360/27)/4)
        pada_gate = (rem_in_pada <= PADA_GATE_TOL) or (((360/27)/4) - rem_in_pada <= PADA_GATE_TOL)
        nak_name = NAK_NAMES[nidx]
        moon_sid_deg = round(s_lon, 2)

        for i in range(len(PLANET_ORDER)):
            for j in range(i+1, len(PLANET_ORDER)):
                p1, p2 = PLANET_ORDER[i], PLANET_ORDER[j]
                lon1 = lon_map[p1][idx]
                lon2 = lon_map[p2][idx]
                sep = dmin(lon1, lon2)

                for a in asp_orbs:
                    if abs(sep - a) <= asp_orbs[a]:
                        row = {
                            "UTC": t.replace(microsecond=0),
                            "Pair": f"{p1}-{p2}",
                            "Aspect": a,
                            "Orb": round(sep - a, 2),
                            "Lon1": round(lon1,2),
                            "Lon2": round(lon2,2)
                        }
                        if show_station:
                            row["Station"] = "".join([
                                ("Ⓢ" if station_map[p1][idx] else ""),
                                ("Ⓢ" if station_map[p2][idx] else "")
                            ])
                        if show_decl and ("Moon" in (p1, p2)):
                            other = p2 if p1=="Moon" else p1
                            od = dec_map[other][idx]
                            par = abs(moon_dec - od) <= dec_tol
                            contra = abs(moon_dec + od) <= dec_tol
                            row["DecPar"] = "✓" if par else ""
                            row["DecContra"] = "✓" if contra else ""
                        if show_phase:
                            row["Phase°"] = round(phase,2)
                            row["PhaseGate"] = "✓" if phase_gate else ""
                            row["Nak"] = f"{nak_name}-p{pada}"
                            row["PadaGate"] = "✓" if pada_gate else ""
                            row["MoonSid°"] = moon_sid_deg
                        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No aspects in range with current filters.")
    else:
        preferred = ["UTC","Pair","Aspect","Orb","Lon1","Lon2","Station","DecPar","DecContra","Phase°","PhaseGate","Nak","PadaGate","MoonSid°"]
        cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
        df = df[cols]
        page_size = 200
        page = st.number_input("Page", value=1, min_value=1, max_value=max(1, (len(df)+page_size-1)//page_size))
        lo, hi = (page-1)*page_size, min(page*page_size, len(df))
        st.caption(f"Showing {lo+1}–{hi} of {len(df)} matches")
        st.dataframe(df.iloc[lo:hi], use_container_width=True)

# =========================================
# FOOTER
# =========================================

st.caption(
    "Foundation: Framework planets (Jupiter/Saturn) → Ascendant phase → Moon trigger. "
    "Price: √-spiral + sin/cos + Square-of-Nine with numerology bias. "
    "Aspects: cached ephemerides, stations, declination, lunar phase, nakshatra/pada, paginated results. "
    "Heliocentric framework optional for Jupiter/Saturn."
)
