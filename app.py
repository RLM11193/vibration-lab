# Vibration Lab — Full Harmonic Wave (Sidereal/Lahiri)
# From any Low/High: compute harmonic price/time, scan Asc hits, score confluence,
# and output ONE best (time, price) prediction. High-contrast UI, phone-friendly.

import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import streamlit as st

# ---------- Swiss Ephemeris ----------
try:
    import swisseph as swe
except Exception as e:
    raise SystemExit("pyswisseph must be installed (see requirements.txt).") from e

# Sidereal / Lahiri (as we tested)
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

# ---------- helpers ----------
def jd_ut(dt_utc: datetime) -> float:
    y, m, d = dt_utc.year, dt_utc.month, dt_utc.day
    h = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600
    return swe.julday(y, m, d, h, swe.GREG_CAL)

def planet_lon(dt_utc: datetime, name: str) -> float:
    pos, _ = swe.calc_ut(jd_ut(dt_utc), PLANETS[name], EPH_FLAGS)
    return float(pos[0]) % 360.0

def ascendant(dt_utc: datetime, lat: float, lon_east: float) -> float:
    # Robust: houses() -> ascmc[0] = Asc
    _, ascmc = swe.houses(jd_ut(dt_utc), lat, lon_east)
    return float(ascmc[0]) % 360.0

def wrap_diff(a: float, b: float) -> float:
    """Signed minimal angular difference in (-180, 180]."""
    return ((a - b + 180.0) % 360.0) - 180.0

def price_angle_sqrt(P: float) -> float:
    # θP from square-root spiral (fractional part × 360)
    r = math.sqrt(max(P, 0.0))
    return (360.0 * (r - math.floor(r))) % 360.0

def price_angle_cuberoot(P: float) -> float:
    # optional cube-root field (kept for display; lower weight)
    r = max(P, 0.0) ** (1/3)
    return (360.0 * (r - math.floor(r))) % 360.0

def time_angle_sqrt(nbars: float) -> float:
    r = math.sqrt(max(nbars, 0.0))
    return (360.0 * (r - math.floor(r))) % 360.0

def time_angle_cuberoot(nbars: float) -> float:
    r = max(nbars, 0.0) ** (1/3)
    return (360.0 * (r - math.floor(r))) % 360.0

def time_echo_bars(theta: float, max_bars: int):
    """
    Echo rule we used: n ≈ round((theta/180 + 2k)^2), k=1,2,... <= max_bars
    """
    s0 = theta / 180.0
    out, k = [], 1
    while True:
        n = round((s0 + 2*k) ** 2)
        if n < 1:
            k += 1
            continue
        if n > max_bars:
            break
        if n not in out:
            out.append(int(n))
        k += 1
    return out

def nearest_price_from_angle(anchor_price: float, degree: float, direction: int) -> float:
    """
    Map harmonic degree -> price via inverse of θP.
    degree in [0,360). Choose nearest in the given direction:
      direction=+1 (from Low -> up)  or  -1 (from High -> down).
    """
    frac = (degree % 360.0) / 360.0
    base = int(math.floor(math.sqrt(max(anchor_price, 0.0))))
    candidates = []
    # search a few adjacent spirals
    for k in range(base-4, base+8):
        r = k + frac
        p = r*r
        d = p - anchor_price
        if direction > 0 and d <= 0:   # want up from low
            continue
        if direction < 0 and d >= 0:   # want down from high
            continue
        candidates.append((abs(d), p))
    if not candidates:  # fallback: ignore direction, pick nearest
        for k in range(base-4, base+8):
            r = k + frac
            p = r*r
            candidates.append((abs(p - anchor_price), p))
    return min(candidates, key=lambda x: x[0])[1]

def find_asc_hits(start_utc: datetime, end_utc: datetime,
                  lat: float, lon_east: float, target_deg: float,
                  tol: float = 1.0, step_min: int = 5):
    """
    Scan over [start,end], detect when Asc crosses target_deg, refine by bisection.
    Returns list[datetime UTC] of hits.
    """
    hits = []
    t = start_utc
    step = timedelta(minutes=step_min)
    prev = wrap_diff(ascendant(t, lat, lon_east), target_deg)
    while t <= end_utc:
        t2 = t + step
        cur = wrap_diff(ascendant(t2, lat, lon_east), target_deg)
        if prev * cur <= 0:  # crossed
            a, b = t, t2
            for _ in range(12):
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

# ---------- UI theme ----------
st.set_page_config(page_title="Vibration Lab", page_icon="✨", layout="centered")
def css(theme="dark"):
    if theme == "dark":
        bg, card, text, sub, acc, brd = "#0c0f14", "#151a21", "#f2f5f8", "#a9b3bf", "#08e0d1", "#26303a"
        sh = "0 10px 28px rgba(0,0,0,.45)"
    else:
        bg, card, text, sub, acc, brd = "#f7f9fc", "#ffffff", "#0e1116", "#5d6b7b", "#0aa3ff", "#e7eef6"
        sh = "0 8px 22px rgba(2,18,51,.08)"
    st.markdown(f"""
    <style>
      .stApp{{background:{bg};color:{text}}}
      div.block-container{{max-width:920px;padding-top:10px}}
      .card{{background:{card};border:1px solid {brd};border-radius:18px;padding:18px;box-shadow:{sh}}}
      .card + .card{{margin-top:16px}}
      .accent{{color:{acc}}}
      .pill{{display:inline-block;padding:6px 12px;border-radius:999px;background:rgba(120,120,120,.12);margin:6px 8px 0 0}}
      .bigbtn button{{height:54px;font-weight:700;font-size:1.05rem;border-radius:12px}}
      .stSelectbox>div>div, .stNumberInput input, .stTextInput input,
      .stTimeInput input, .stDateInput input{{height:52px;font-size:1.02rem}}
      hr.sep{{border:none;border-top:1px solid {brd};margin:12px 0}}
    </style>
    """, unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### Display")
    theme = st.radio("Theme", ["Dark","Light"], index=0, horizontal=True)
css(theme.lower())
st.markdown("<h2 class='accent'>Vibration Lab — Full Harmonic Wave</h2>", unsafe_allow_html=True)

# ---------- INPUTS ----------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown("**1) Swing points** (use exact timestamps)")
c1, c2 = st.columns(2)
with c1:
    low_price = st.number_input("Swing LOW price", min_value=0.0, value=3267.89, step=0.01)
    low_date  = st.date_input("LOW date", value=datetime(2025,7,30).date())
    low_time  = st.time_input("LOW time", value=datetime(2025,7,30,13,0).time())
with c2:
    high_price = st.number_input("Swing HIGH price", min_value=0.0, value=3407.35, step=0.01)
    high_date  = st.date_input("HIGH date", value=datetime(2025,8,7).date())
    high_time  = st.time_input("HIGH time", value=datetime(2025,8,7,16,0).time())

st.markdown("**2) Projection**")
c3, c4 = st.columns(2)
with c3:
    project_from = st.radio("Anchor to project from", ["Low","High"], index=1, horizontal=True)
    direction = 1 if project_from=="Low" else -1  # up from low, down from high
    barmin = st.number_input("Bar interval (minutes)", min_value=1, value=60, step=1)
    horizon_h = st.slider("Scan horizon (hours from anchor)", 6, 144, 72, step=6)
with c4:
    tzname = st.selectbox("Timezone", ["America/Denver","America/New_York","UTC"], index=0)
    tzloc  = pytz.timezone(tzname)
    lat    = st.number_input("Latitude (deg)", value=38.84, step=0.01)
    lonW   = st.number_input("Longitude West (deg, positive=West)", value=106.13, step=0.01)
    lonE   = -abs(lonW)  # East-positive for Swiss Ephemeris
    tol    = st.slider("Angular tolerance (±°)", 0.2, 2.0, 1.0, 0.1)

with st.expander("Options"):
    mobile = st.toggle("Mobile mode (fewer targets, faster)", value=True)
    extra_targets = st.toggle("Add inner-planet & harmonic (+90/+120) targets", value=not mobile)

st.markdown("</div>", unsafe_allow_html=True)

# Run
st.markdown("<div class='bigbtn'>", unsafe_allow_html=True)
if not st.button("Run / Recompute", type="primary", use_container_width=True):
    st.stop()
st.markdown("</div>", unsafe_allow_html=True)

# ---------- build anchor & swing ----------
low_local  = tzloc.localize(datetime.combine(low_date, low_time))
high_local = tzloc.localize(datetime.combine(high_date, high_time))
low_utc, high_utc = low_local.astimezone(pytz.utc), high_local.astimezone(pytz.utc)

if project_from == "Low":
    anchor_price, anchor_local, anchor_utc = low_price, low_local, low_utc
    other_price, other_local = high_price, high_local
else:
    anchor_price, anchor_local, anchor_utc = high_price, high_local, high_utc
    other_price, other_local = low_price, low_local

swing_minutes = abs(int((high_local - low_local).total_seconds() // 60))
swing_bars = max(1, round(swing_minutes / barmin))

# ---------- harmonic angles ----------
thetaP_sqrt = price_angle_sqrt(anchor_price)
thetaP_cube = price_angle_cuberoot(anchor_price)
thetaT_sqrt = time_angle_sqrt(swing_bars)
thetaT_cube = time_angle_cuberoot(swing_bars)

# Base targets
targets = [
    ("Saturn",  planet_lon(anchor_utc, "Saturn"),  3),
    ("Jupiter", planet_lon(anchor_utc, "Jupiter"), 3),
    (f"θP({thetaP_sqrt:.2f}°)", thetaP_sqrt, 2),
    (f"θP+180({(thetaP_sqrt+180)%360:.2f}°)", (thetaP_sqrt+180)%360, 2),
]
# Optional enrichments
if extra_targets:
    targets += [
        (f"θP+90({(thetaP_sqrt+90)%360:.2f}°)",  (thetaP_sqrt+90)%360, 1),
        (f"θP+120({(thetaP_sqrt+120)%360:.2f}°)", (thetaP_sqrt+120)%360,1),
        ("Mercury", planet_lon(anchor_utc, "Mercury"), 2),
        ("Venus",   planet_lon(anchor_utc, "Venus"),   1),
        ("Mars",    planet_lon(anchor_utc, "Mars"),    1),
    ]

# ---------- time echoes ----------
max_bars = int((horizon_h * 60) // barmin)
echo_from_thetaP = time_echo_bars(thetaP_sqrt, max_bars)
echo_from_thetaT = time_echo_bars(thetaT_sqrt, max_bars)

# ---------- scan Asc hits & score ----------
start_utc = anchor_utc
end_utc   = anchor_utc + timedelta(hours=horizon_h)

candidates = []  # (score, T_local, target_label, target_deg, n_bars, price_est, diagnostics)

for label, deg, weight in targets:
    hits = find_asc_hits(start_utc, end_utc, lat, lonE, deg, tol, step_min=5)
    for hit_utc in hits:
        hit_local = hit_utc.astimezone(tzloc)
        # bar count from anchor
        n_bars = max(1, round((hit_local - anchor_local).total_seconds() / 60 / barmin))
        # Moon confirm near same degree at the hit time
        moon_deg = planet_lon(hit_utc, "Moon")
        moon_ok = abs(wrap_diff(moon_deg, deg)) <= tol
        # echo scores
        echo_okP = n_bars in echo_from_thetaP
        echo_okT = n_bars in echo_from_thetaT
        # price projection from harmonic degree
        price_est = nearest_price_from_angle(anchor_price, deg, direction)
        # score
        score = 0
        score += 2 * weight                     # base weight of target
        if moon_ok: score += weight             # moon confirm
        if echo_okP: score += 2
        if echo_okT: score += 2
        # prefer closer-in solutions slightly
        score += max(0, 6 - int(n_bars // 50))
        diag = {
            "moon_ok": moon_ok,
            "echoP": echo_okP,
            "echoT": echo_okT,
            "θP": thetaP_sqrt, "θT": thetaT_sqrt,
        }
        candidates.append((score, hit_local, label, deg, n_bars, price_est, diag))

# choose best
candidates.sort(key=lambda x: (-x[0], x[1]))
final = candidates[0] if candidates else None

# ---------- OUTPUT ----------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Harmonic summary (at anchor)")
st.write(
    f"• Price √ angle θP = **{thetaP_sqrt:.2f}°**"
    f"   · Price ³√ angle = **{thetaP_cube:.2f}°**"
)
st.write(
    f"• Time √ angle θT (between Low↔High over {swing_bars} bars) = **{thetaT_sqrt:.2f}°**"
    f"   · Time ³√ angle = **{thetaT_cube:.2f}°**"
)
st.write(
    f"• Echo bars from θP: {echo_from_thetaP[:10]}{' …' if len(echo_from_thetaP)>10 else ''}"
)
st.write(
    f"• Echo bars from θT: {echo_from_thetaT[:10]}{' …' if len(echo_from_thetaT)>10 else ''}"
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Top resonance candidates")
if not candidates:
    st.write("No confluence found in horizon. Try a wider tolerance or extend horizon.")
else:
    for i, (score, Tloc, lbl, deg, n, p, diag) in enumerate(candidates[:8], start=1):
        flags = []
        if diag["moon_ok"]: flags.append("Moon✓")
        if diag["echoP"]:   flags.append("EchoθP✓")
        if diag["echoT"]:   flags.append("EchoθT✓")
        flag_txt = (" · " + " · ".join(flags)) if flags else ""
        st.write(
            f"{i}. **{Tloc.strftime('%a %b %d, %H:%M %Z')}**"
            f" — ASC ≈ **{lbl}** ({deg:.2f}°)"
            f" · bars **{n}** · est. price **{p:.2f}**"
            f" · score **{score}**{flag_txt}"
        )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("FINAL prediction (single time & price)")
if final is None:
    st.write("No candidate passed the filters. Increase horizon or tolerance.")
else:
    score, Tloc, lbl, deg, n, p, diag = final
    st.markdown(
        f"### ⏱ {Tloc.strftime('%A %b %d, %H:%M %Z')}  ·  💵 {p:.2f}\n"
        f"- Target: **{lbl}** ({deg:.2f}°)\n"
        f"- Bars from anchor: **{n}**\n"
        f"- Confluence: {'Moon✓ ' if diag['moon_ok'] else ''}"
        f"{'EchoθP✓ ' if diag['echoP'] else ''}"
        f"{'EchoθT✓ ' if diag['echoT'] else ''}"
        f"- Score: **{score}**"
    )
st.markdown("</div>", unsafe_allow_html=True)

st.caption("Intraday timing = Ascendant hits · Swing confirmation = Moon · Framework = Saturn/Jupiter · Sidereal (Lahiri).")
