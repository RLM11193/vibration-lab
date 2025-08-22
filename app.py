# Vibration Lab — Law of Vibration (Sidereal/Lahiri)
# Intraday timing = Ascendant hits; Swing confirmation = Moon near same target degree.
# Framework planets = Saturn/Jupiter; plus inner planets when Mobile mode is off.

import math
from datetime import datetime, timedelta
import pytz
import streamlit as st

# ----- Ephemeris -----
try:
    import swisseph as swe
except Exception as e:
    raise SystemExit(
        "pyswisseph is required and should install from requirements.txt"
    ) from e

# Sidereal/Lahiri as discussed
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
# Use Moshier model so it runs without downloading ephemeris files
EPH_FLAGS = swe.FLG_SIDEREAL | swe.FLG_MOSEPH

PLANETS = {
    "Saturn":  swe.SATURN,
    "Jupiter": swe.JUPITER,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Rahu":    swe.MEAN_NODE,  # Mean node, matches your Panchang screenshots
    "Ketu":    swe.TRUE_NODE,  # True node for the opposite point
}

# ----- Helpers -----
def jd_ut(dt_utc: datetime) -> float:
    y, m, d = dt_utc.year, dt_utc.month, dt_utc.day
    h = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(y, m, d, h, swe.GREG_CAL)

def planet_lon(dt_utc: datetime, name: str) -> float:
    # FIXED: correct unpack from swe.calc_ut
    pos, _ = swe.calc_ut(jd_ut(dt_utc), PLANETS[name], EPH_FLAGS)
    lon = pos[0]
    return lon % 360.0

def ascendant(dt_utc: datetime, lat: float, lon_east: float) -> float:
    # Placidus houses; ascmc[0] is Ascendant
    _, ascmc = swe.houses_ex(jd_ut(dt_utc), EPH_FLAGS, lat, lon_east, b'P')
    return ascmc[0] % 360.0

def wrap_diff(a: float, b: float) -> float:
    """Signed minimal angular difference in (-180, 180]."""
    return ((a - b + 180.0) % 360.0) - 180.0

# ----- Law of Vibration core -----
HARMONICS = [0, 30, 45, 60, 90, 120, 135, 180, 225, 240, 270, 315, 360]

def price_angle(P: float) -> float:
    """θP from √price (fractional part × 360)."""
    r = math.sqrt(max(P, 0.0))
    return (360.0 * (r - math.floor(r))) % 360.0

def time_echo_bars(theta_target: float, max_bars: int):
    """
    Simple 'echo' rule we’ve been using:
    n ≈ round((theta/180 + 2k)^2), k = 1,2,... up to max_bars
    (You can swap in any alternative mapping later.)
    """
    s0 = theta_target / 180.0
    out, k = [], 1
    while True:
        n = round((s0 + 2 * k) ** 2)
        if n < 1:
            k += 1
            continue
        if n > max_bars:
            break
        if n not in out:
            out.append(int(n))
        k += 1
    return out

def find_asc_hits(start_utc: datetime, end_utc: datetime,
                  lat: float, lon_east: float,
                  target_deg: float, tol: float = 1.0,
                  step_min: int = 5):
    """
    Scan forward, detect sign change around target, refine with bisection.
    Returns list of hit datetimes (UTC).
    """
    hits = []
    t = start_utc
    step = timedelta(minutes=step_min)

    prev = wrap_diff(ascendant(t, lat, lon_east), target_deg)

    while t <= end_utc:
        t2 = t + step
        cur = wrap_diff(ascendant(t2, lat, lon_east), target_deg)

        if prev * cur <= 0:  # crossed the target
            a, b = t, t2
            for _ in range(12):  # refine ~ 2^12 ≈ ~0.02 of step
                mid = a + (b - a) / 2
                dmid = wrap_diff(ascendant(mid, lat, lon_east), target_deg)
                if abs(dmid) <= tol:
                    hits.append(mid)
                    break
                da = wrap_diff(ascendant(a, lat, lon_east), target_deg)
                if da * dmid <= 0:
                    b = mid
                else:
                    a = mid
        t, prev = t2, cur
    return hits

# ----- UI -----
st.set_page_config(page_title="Vibration Lab", page_icon="✨", layout="centered")
st.markdown("""
<style>
.stApp{background:#0E0F12;color:#EAECEE}
div.block-container{max-width:860px;padding-top:1rem}
.card{background:#1A1C20;border-radius:18px;padding:16px 18px;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.pill{display:inline-block;margin:4px 6px 0 0;padding:6px 10px;border-radius:999px;background:#23262B}
.accent{color:#00D6C8}
.small{color:#9AA3AE;font-size:0.9em}
</style>
""", unsafe_allow_html=True)
st.markdown("<h2 class='accent'>Vibration Lab — Law of Vibration (Sidereal/Lahiri)</h2>", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 2])

    with col1:
        symbol  = st.text_input("Symbol", "NAS100")
        price   = st.number_input("Anchor Price (exact pivot price)", min_value=0.0, value=23984.9, step=0.1)
        tzname  = st.selectbox("Timezone", ["America/Denver", "America/New_York", "UTC"], index=0)
        tzloc   = pytz.timezone(tzname)
        d_local = st.date_input("Anchor Date (local)", value=datetime(2025, 8, 13).date())
        t_local = st.time_input("Anchor Time (local)", value=datetime(2025, 8, 13, 7, 30).time())
        barmin  = st.number_input("Bar Interval (minutes)", min_value=1, value=60, step=1)
        horizon = st.slider("Scan horizon (hours from anchor)", 6, 120, 48, step=6)

    with col2:
        st.caption("Use the exact minute of the pivot (event-time).")
        lat   = st.number_input("Latitude (deg)", value=38.84, step=0.01)
        lonW  = st.number_input("Longitude West (deg, positive=West)", value=106.13, step=0.01)
        lonE  = -abs(lonW)  # Swiss Ephemeris wants East-positive
        tol   = st.slider("Angular tolerance (±°)", 0.2, 2.0, 1.0, 0.1)
        mobile = st.toggle("Mobile mode (optimize speed)", value=True)

    with st.expander("Optional numerology (for notes)"):
        user_bars  = st.text_input("Bar count (optional)", "")
        user_range = st.text_input("Price move (optional)", "")

    st.markdown("</div>", unsafe_allow_html=True)

run = st.button("Run / Recompute", type="primary")
if not run:
    st.stop()

# ----- Anchor times -----
anchor_local = tzloc.localize(datetime.combine(d_local, t_local))
anchor_utc   = anchor_local.astimezone(pytz.utc)

# ----- Vibration Targets -----
theta_p = price_angle(price)

# Always include core: Saturn/Jupiter + θP and θP+180
targets = [
    ("Saturn", planet_lon(anchor_utc, "Saturn"), 3),
    ("Jupiter", planet_lon(anchor_utc, "Jupiter"), 3),
    (f"θP({theta_p:.2f}°)", theta_p, 2),
    (f"θP+180({(theta_p+180)%360:.2f}°)", (theta_p + 180) % 360, 2),
]

# Add more structure when not in mobile mode
if not mobile:
    targets += [
        (f"θP+90({(theta_p+90)%360:.2f}°)",  (theta_p + 90) % 360,  1),
        (f"θP+120({(theta_p+120)%360:.2f}°)", (theta_p + 120) % 360, 1),
        ("Mercury", planet_lon(anchor_utc, "Mercury"), 2),
        ("Venus",   planet_lon(anchor_utc, "Venus"),   1),
        ("Mars",    planet_lon(anchor_utc, "Mars"),    1),
    ]

# ----- Time Echoes -----
max_bars = int((horizon * 60) // barmin)
echo_rows = []
for label, deg, _w in targets:
    for n in time_echo_bars(deg, max_bars=max_bars):
        echo_rows.append((label, deg, n, anchor_local + timedelta(minutes=barmin * n)))
echo_rows.sort(key=lambda r: r[3])

# ----- Ascendant hits (intraday timer) with Moon confirmation (swing) -----
start_utc = anchor_utc
end_utc   = anchor_utc + timedelta(hours=horizon)
hits = []
for label, deg, weight in targets:
    for hit in find_asc_hits(start_utc, end_utc, lat, lonE, deg, tol, step_min=5):
        # Moon confirmation: same target ± tol
        moon_deg = planet_lon(hit, "Moon")
        moon_ok  = abs(wrap_diff(moon_deg, deg)) <= tol
        score    = 2 * weight + (weight if moon_ok else 0)
        hits.append((hit.astimezone(tzloc), label, deg, moon_ok, score))
hits.sort(key=lambda r: (r[0], -r[4]))

# ----- Render -----
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown(
    f"### Vibration Angle θP: <span class='accent'>{theta_p:.2f}°</span>",
    unsafe_allow_html=True,
)
st.markdown(
    " ".join([
        f"<span class='pill'>θP {theta_p:.2f}°</span>",
        f"<span class='pill'>+90 {(theta_p+90)%360:.2f}°</span>",
        f"<span class='pill'>+120 {(theta_p+120)%360:.2f}°</span>",
        f"<span class='pill'>+180 {(theta_p+180)%360:.2f}°</span>",
    ]),
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Next Resonance Windows (Ascendant hits)")
if not hits:
    st.write("No Asc hits in range. Try ±1.5° tolerance or extend horizon.")
else:
    strong = [h for h in hits if h[4] >= 6][:6]
    medium = [h for h in hits if 4 <= h[4] < 6][:6]
    if strong:
        st.markdown("**Strong**")
        for T, lbl, deg, moon, score in strong:
            st.write(
                f"🟢 {T.strftime('%a %b %d, %H:%M %Z')} — ASC ≈ {lbl} ({deg:.2f}°)"
                f"{' · + Moon' if moon else ''} · Score {score}"
            )
    if medium:
        st.markdown("**Medium**")
        for T, lbl, deg, moon, score in medium:
            st.write(
                f"🟡 {T.strftime('%a %b %d, %H:%M %Z')} — ASC ≈ {lbl} ({deg:.2f}°)"
                f"{' · + Moon' if moon else ''} · Score {score}"
            )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Time-Echo Bars → Clock Times")
for label, deg, n, tloc in echo_rows[:60]:
    st.write(f"- **N={n:>3}** → {tloc.strftime('%a %b %d, %H:%M %Z')} · target **{label}** ({deg:.2f}°)")
st.markdown("</div>", unsafe_allow_html=True)

# Optional: tiny numerology notes (if user provided)
if user_bars.strip() or user_range.strip():
    def digit_root(x: int) -> int:
        x = abs(int(x))
        return 9 if x % 9 == 0 and x != 0 else (x % 9)

    notes = []
    if user_bars.strip().isdigit():
        nb = int(user_bars.strip())
        notes.append(f"Bars: {nb} → digital root {digit_root(nb)}")
        notes.append(f"Bars mod 12 = {nb % 12}, mod 27 = {nb % 27}, mod 60 = {nb % 60}")
    try:
        pr = float(user_range.strip())
        cents = int(round(abs(pr) * 100))
        notes.append(f"Price move {pr} → scaled 100x = {cents}, digital root {digit_root(cents)}")
    except Exception:
        pass

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Numerology (notes)")
    if notes:
        for line in notes:
            st.write("• " + line)
    else:
        st.write("Enter a bar count or price move to see quick numerology.")
    st.markdown("</div>", unsafe_allow_html=True)

st.caption("Intraday = Asc timer · Swing = Moon confirm · Framework = Saturn/Jupiter · Sidereal (Lahiri).")
