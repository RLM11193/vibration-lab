# Vibration Lab — Law of Vibration (Sidereal/Lahiri)
# UI revamp: high-contrast, large text, light/dark toggle, bigger controls.

import math
from datetime import datetime, timedelta
import pytz
import streamlit as st

# ----- Ephemeris -----
try:
    import swisseph as swe
except Exception as e:
    raise SystemExit("pyswisseph must be installed (see requirements.txt).") from e

# Sidereal/Lahiri
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
EPH_FLAGS = swe.FLG_SIDEREAL | swe.FLG_MOSEPH  # fast, no external files

PLANETS = {
    "Saturn":  swe.SATURN,
    "Jupiter": swe.JUPITER,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Rahu":    swe.MEAN_NODE,
    "Ketu":    swe.TRUE_NODE,
}

# ===== Helpers =====
def jd_ut(dt_utc: datetime) -> float:
    y, m, d = dt_utc.year, dt_utc.month, dt_utc.day
    h = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(y, m, d, h, swe.GREG_CAL)

def planet_lon(dt_utc: datetime, name: str) -> float:
    pos, _ = swe.calc_ut(jd_ut(dt_utc), PLANETS[name], EPH_FLAGS)
    return float(pos[0]) % 360.0

def ascendant(dt_utc: datetime, lat: float, lon_east: float) -> float:
    # Robust asc using houses() (no flags)
    _, ascmc = swe.houses(jd_ut(dt_utc), lat, lon_east)
    return float(ascmc[0]) % 360.0

def wrap_diff(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0

HARMONICS = [0, 30, 45, 60, 90, 120, 135, 180, 225, 240, 270, 315, 360]

def price_angle(P: float) -> float:
    r = math.sqrt(max(P, 0.0))
    return (360.0 * (r - math.floor(r))) % 360.0

def time_echo_bars(theta_target: float, max_bars: int):
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
    hits = []
    t = start_utc
    step = timedelta(minutes=step_min)
    prev = wrap_diff(ascendant(t, lat, lon_east), target_deg)

    while t <= end_utc:
        t2 = t + step
        cur = wrap_diff(ascendant(t2, lat, lon_east), target_deg)
        if prev * cur <= 0:  # crossed target
            a, b = t, t2
            for _ in range(12):  # bisection refine
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

# ===== UI THEME =====
st.set_page_config(page_title="Vibration Lab", page_icon="✨", layout="centered")

def inject_css(theme: str = "dark", font_scale: float = 1.12, compact: bool = False):
    # Palette
    if theme == "dark":
        bg = "#0c0f14"
        card = "#151a21"
        text = "#f2f5f8"
        sub = "#a9b3bf"
        accent = "#08e0d1"
        border = "#262e39"
        shadow = "0 10px 28px rgba(0,0,0,.45)"
    else:  # light
        bg = "#f7f9fc"
        card = "#ffffff"
        text = "#0e1116"
        sub = "#5d6b7b"
        accent = "#0aa3ff"
        border = "#e7eef6"
        shadow = "0 8px 22px rgba(2,18,51,.08)"

    fs = f"{font_scale}rem"
    line = "1.65" if not compact else "1.45"
    pad = "18px" if not compact else "12px"
    gap = "16px" if not compact else "10px"
    inp = "52px" if not compact else "44px"
    btn = "54px" if not compact else "46px"

    css = f"""
    <style>
    .stApp {{ background:{bg}; color:{text}; }}
    div.block-container {{ max-width: 900px; padding-top: 10px; }}
    html, body, [class^="css"] {{ font-size:{fs}; line-height:{line}; }}
    .card {{ background:{card}; border:1px solid {border}; border-radius:18px; padding:{pad}; box-shadow:{shadow}; }}
    .card + .card {{ margin-top:{gap}; }}
    .accent {{ color:{accent}; }}
    .muted {{ color:{sub}; }}
    .pill {{ display:inline-block; padding:6px 12px; border-radius:999px; background:rgba(100,100,100,.12); margin:6px 8px 0 0; }}
    .bigbtn button {{ height:{btn}; font-weight:700; font-size:1.05rem; }}
    .stButton>button {{ border-radius:12px; }}
    .stSelectbox>div>div, .stTextInput>div>div>input, .stNumberInput>div>div>input, .stTimeInput>div>div>input,
    .stDateInput>div>div>input {{ height:{inp}; font-size:1.02rem; }}
    .stSlider [data-baseweb="slider"] {{ margin-top:4px; }}
    hr.sep {{ border:none; border-top:1px solid {border}; margin: 12px 0; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# Sidebar controls for visual tuning
with st.sidebar:
    st.markdown("### Display")
    theme = st.radio("Theme", ["Dark", "Light"], index=0, horizontal=True)
    size = st.radio("Text size", ["Large", "Normal"], index=0, horizontal=True)
    density = st.radio("Density", ["Comfortable", "Compact"], index=0, horizontal=True)

inject_css(
    theme.lower(),
    font_scale=1.18 if size == "Large" else 1.0,
    compact=True if density == "Compact" else False
)

st.markdown("<h2 class='accent'>Vibration Lab — Law of Vibration (Sidereal/Lahiri)</h2>", unsafe_allow_html=True)

# ===== INPUTS =====
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
    lonE  = -abs(lonW)  # East-positive for Swiss Ephemeris
    tol   = st.slider("Angular tolerance (±°)", 0.2, 2.0, 1.0, 0.1)
    mobile = st.toggle("Mobile mode (optimize speed)", value=True)

with st.expander("Optional numerology (for notes)"):
    user_bars  = st.text_input("Bar count (optional)", "")
    user_range = st.text_input("Price move (optional)", "")

st.markdown("</div>", unsafe_allow_html=True)

# Run button
st.markdown("<div class='bigbtn'>", unsafe_allow_html=True)
run = st.button("Run / Recompute", type="primary", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)
if not run:
    st.stop()

# ===== COMPUTE =====
anchor_local = tzloc.localize(datetime.combine(d_local, t_local))
anchor_utc   = anchor_local.astimezone(pytz.utc)
theta_p = price_angle(price)

targets = [
    ("Saturn",  planet_lon(anchor_utc, "Saturn"),  3),
    ("Jupiter", planet_lon(anchor_utc, "Jupiter"), 3),
    (f"θP({theta_p:.2f}°)", theta_p, 2),
    (f"θP+180({(theta_p+180)%360:.2f}°)", (theta_p + 180) % 360, 2),
]
if not mobile:
    targets += [
        (f"θP+90({(theta_p+90)%360:.2f}°)",  (theta_p + 90) % 360,  1),
        (f"θP+120({(theta_p+120)%360:.2f}°)", (theta_p + 120) % 360, 1),
        ("Mercury", planet_lon(anchor_utc, "Mercury"), 2),
        ("Venus",   planet_lon(anchor_utc, "Venus"),   1),
        ("Mars",    planet_lon(anchor_utc, "Mars"),    1),
    ]

max_bars = int((horizon * 60) // barmin)
echo_rows = []
for label, deg, _w in targets:
    for n in time_echo_bars(deg, max_bars=max_bars):
        echo_rows.append((label, deg, n, anchor_local + timedelta(minutes=barmin * n)))
echo_rows.sort(key=lambda r: r[3])

start_utc = anchor_utc
end_utc   = anchor_utc + timedelta(hours=horizon)
hits = []
for label, deg, weight in targets:
    for hit in find_asc_hits(start_utc, end_utc, lat, lonE, deg, tol, step_min=5):
        moon_deg = planet_lon(hit, "Moon")
        moon_ok  = abs(wrap_diff(moon_deg, deg)) <= tol
        score    = 2 * weight + (weight if moon_ok else 0)
        hits.append((hit.astimezone(tzloc), label, deg, moon_ok, score))
hits.sort(key=lambda r: (r[0], -r[4]))

# ===== OUTPUT =====
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown(f"### Vibration Angle θP: <span class='accent'>{theta_p:.2f}°</span>", unsafe_allow_html=True)
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
st.markdown("<hr class='sep'/>", unsafe_allow_html=True)
if not hits:
    st.write("No Asc hits in range. Try ±1.5° tolerance or extend horizon.")
else:
    strong = [h for h in hits if h[4] >= 6][:8]
    medium = [h for h in hits if 4 <= h[4] < 6][:8]
    if strong:
        st.markdown("**Strong**")
        for T, lbl, deg, moon, score in strong:
            st.write(
                f"🟢 **{T.strftime('%a %b %d, %H:%M %Z')}** — ASC ≈ **{lbl}** ({deg:.2f}°)"
                f"{' · **+ Moon**' if moon else ''} · Score **{score}**"
            )
        st.markdown("<hr class='sep'/>", unsafe_allow_html=True)
    if medium:
        st.markdown("**Medium**")
        for T, lbl, deg, moon, score in medium:
            st.write(
                f"🟡 **{T.strftime('%a %b %d, %H:%M %Z')}** — ASC ≈ **{lbl}** ({deg:.2f}°)"
                f"{' · + Moon' if moon else ''} · Score {score}"
            )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Time-Echo Bars → Clock Times")
st.markdown("<hr class='sep'/>", unsafe_allow_html=True)
for label, deg, n, tloc in echo_rows[:80]:
    st.write(f"- **N={n:>3}** → **{tloc.strftime('%a %b %d, %H:%M %Z')}** · target **{label}** ({deg:.2f}°)")
st.markdown("</div>", unsafe_allow_html=True)

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
    st.markdown("<hr class='sep'/>", unsafe_allow_html=True)
    if notes:
        for line in notes: st.write("• " + line)
    else:
        st.write("Enter a bar count or price move to see quick numerology.")
    st.markdown("</div>", unsafe_allow_html=True)

st.caption("Intraday = Asc timer · Swing = Moon confirm · Framework = Saturn/Jupiter · Sidereal (Lahiri).")
