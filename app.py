# Vibration Lab — clean, mobile-first MVP (Streamlit)
# Ascendant timer (intraday), Moon confirmation (swing), sidereal/Lahiri

import math
from datetime import datetime, timedelta
import pytz, streamlit as st

try:
    import swisseph as swe
except Exception as e:
    raise SystemExit("pyswisseph required. It will install from requirements.txt.") from e

# ---------- Swiss Ephemeris (sidereal/Lahiri) ----------
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
EPH_FLAGS = swe.FLG_SIDEREAL | swe.FLG_MOSEPH  # runs without external ephemeris files

PLANETS = {
    "Saturn": swe.SATURN, "Jupiter": swe.JUPITER, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Sun": swe.SUN, "Moon": swe.MOON,
    "Rahu": swe.MEAN_NODE, "Ketu": swe.TRUE_NODE
}

def jd_ut(dt_utc: datetime) -> float:
    y,m,d = dt_utc.year, dt_utc.month, dt_utc.day
    h = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600
    return swe.julday(y,m,d,h, swe.GREG_CAL)

def planet_lon(dt_utc: datetime, name: str) -> float:
    lon, *_ = swe.calc_ut(jd_ut(dt_utc), PLANETS[name], EPH_FLAGS)
    return lon % 360.0

def ascendant(dt_utc: datetime, lat: float, lon_east: float) -> float:
    _, ascmc = swe.houses_ex(jd_ut(dt_utc), EPH_FLAGS, lat, lon_east, b'P')
    return ascmc[0] % 360.0

def wrap_diff(a,b):  # signed minimal diff in (-180, 180]
    return ((a - b + 180) % 360) - 180

# ---------- Vibration math ----------
HARMONICS = [0,30,45,60,90,120,135,180,225,240,270,315,360]
def price_angle(P: float) -> float:
    r = math.sqrt(P); return (360.0 * (r - math.floor(r))) % 360.0
def echoes(theta: float): return [ (theta + h) % 360.0 for h in HARMONICS ]
def time_echo_bars(theta_target: float, max_bars: int):
    s0 = theta_target / 180.0; out = []; k = 1
    while True:
        n = round((s0 + 2*k)**2)
        if n < 1: k += 1; continue
        if n > max_bars: break
        if n not in out: out.append(int(n))
        k += 1
    return out

def find_asc_hits(start_utc, end_utc, lat, lon_east, target_deg, tol=1.0, step_min=5):
    hits, t, step = [], start_utc, timedelta(minutes=step_min)
    prev = wrap_diff(ascendant(t, lat, lon_east), target_deg)
    while t <= end_utc:
        t2 = t + step
        cur = wrap_diff(ascendant(t2, lat, lon_east), target_deg)
        if prev*cur <= 0:
            a,b = t,t2
            for _ in range(10):
                mid = a + (b-a)/2
                d = wrap_diff(ascendant(mid, lat, lon_east), target_deg)
                if abs(d) <= tol: hits.append(mid); break
                da = wrap_diff(ascendant(a, lat, lon_east), target_deg)
                if da*d <= 0: b = mid
                else: a = mid
        t, prev = t2, cur
    return hits

# ---------- UI ----------
st.set_page_config(page_title="Vibration Lab", page_icon="✨", layout="centered")
st.markdown("""
<style>
.stApp{background:#0E0F12;color:#EAECEE}
div.block-container{max-width:860px;padding-top:1rem}
.card{background:#1A1C20;border-radius:18px;padding:16px 18px;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.pill{display:inline-block;margin:4px 6px 0 0;padding:6px 10px;border-radius:999px;background:#23262B}
.accent{color:#00D6C8}
</style>
""", unsafe_allow_html=True)
st.markdown("<h2 class='accent'>Vibration Lab — Law of Vibration (Sidereal/Lahiri)</h2>", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    col1,col2=st.columns([3,2])
    with col1:
        symbol = st.text_input("Symbol", "NAS100")
        price  = st.number_input("Anchor Price (exact pivot price)", min_value=0.0, value=23984.9, step=0.1)
        tzname = st.selectbox("Timezone", ["America/Denver","America/New_York","UTC"], index=0)
        tzloc  = pytz.timezone(tzname)
        d      = st.date_input("Anchor Date (local)", value=datetime(2025,8,13).date())
        t      = st.time_input("Anchor Time (local)", value=datetime(2025,8,13,7,30).time())
        barmin = st.number_input("Bar Interval (minutes)", min_value=1, value=60, step=1)
        horizon= st.slider("Scan horizon (hours from anchor)", 6, 120, 48, step=6)
    with col2:
        st.caption("Use the exact minute of the pivot (event-time).")
        lat     = st.number_input("Latitude (deg)", value=38.84, step=0.01)
        lonW    = st.number_input("Longitude West (deg, positive=West)", value=106.13, step=0.01)
        lonE    = -abs(lonW)  # ephemeris uses East-positive
        tol     = st.slider("Angular tolerance (±°)", 0.2, 2.0, 1.0, 0.1)
        mobile  = st.toggle("Mobile mode (optimize speed)", value=True)
    st.markdown("</div>", unsafe_allow_html=True)

run = st.button("Run / Recompute", type="primary")
if not run: st.stop()

anchor_local = tzloc.localize(datetime.combine(d,t))
anchor_utc   = anchor_local.astimezone(pytz.utc)

theta_p = price_angle(price)
targets = [("Saturn", planet_lon(anchor_utc,"Saturn"),3),
           ("Jupiter", planet_lon(anchor_utc,"Jupiter"),3),
           (f"θP({theta_p:.2f}°)", theta_p,2),
           (f"θP+180({(theta_p+180)%360:.2f}°)", (theta_p+180)%360,2)]
if not mobile:
    targets += [(f"θP+90({(theta_p+90)%360:.2f}°)", (theta_p+90)%360,1),
                (f"θP+120({(theta_p+120)%360:.2f}°)", (theta_p+120)%360,1),
                ("Mercury", planet_lon(anchor_utc,"Mercury"),2),
                ("Venus",   planet_lon(anchor_utc,"Venus"),1),
                ("Mars",    planet_lon(anchor_utc,"Mars"),1)]

max_bars = int((horizon*60)//barmin)
echo_rows=[]
for label,deg,_w in targets:
    for n in time_echo_bars(deg, max_bars=max_bars):
        echo_rows.append((label,deg,n, anchor_local + timedelta(minutes=barmin*n)))
echo_rows.sort(key=lambda r:r[3])

start_utc, end_utc = anchor_utc, anchor_utc + timedelta(hours=horizon)
hits=[]
for label,deg,w in targets:
    for hit in find_asc_hits(start_utc,end_utc,lat,lonE,deg,tol,5):
        moon_deg = planet_lon(hit,"Moon")
        moon_ok  = abs(wrap_diff(moon_deg,deg)) <= tol
        score    = 2*w + (w if moon_ok else 0)
        hits.append((hit.astimezone(tzloc),label,deg,moon_ok,score))
hits.sort(key=lambda r:(r[0],-r[4]))

# ---- Render
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown(f"### Vibration Angle θP: <span class='accent'>{theta_p:.2f}°</span>", unsafe_allow_html=True)
st.markdown(" ".join([f"<span class='pill'>θP {theta_p:.2f}°</span>",
                      f"<span class='pill'>+90 {(theta_p+90)%360:.2f}°</span>",
                      f"<span class='pill'>+120 {(theta_p+120)%360:.2f}°</span>",
                      f"<span class='pill'>+180 {(theta_p+180)%360:.2f}°</span>"]),
            unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Next Resonance Windows (Ascendant hits)")
if not hits:
    st.write("No Asc hits in range. Try ±1.5° tolerance or extend horizon.")
else:
    strong=[h for h in hits if h[4] >= 6][:3]; med=[h for h in hits if 4<=h[4]<6][:3]
    if strong:
        st.markdown("**Strong**")
        for T,lbl,deg,moon,score in strong:
            st.write(f"🟢 {T.strftime('%a %b %d, %H:%M %Z')} — ASC≈{lbl} ({deg:.2f}°){' · + Moon' if moon else ''} · Score {score}")
    if med:
        st.markdown("**Medium**")
        for T,lbl,deg,moon,score in med:
            st.write(f"🟡 {T.strftime('%a %b %d, %H:%M %Z')} — ASC≈{lbl} ({deg:.2f}°){' · + Moon' if moon else ''} · Score {score}")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Time-Echo Bars → Clock Times")
for label,deg,n,tloc in echo_rows[:50]:
    st.write(f"- **N={n:>3}** → {tloc.strftime('%a %b %d, %H:%M %Z')} · target **{label}** ({deg:.2f}°)")
st.markdown("</div>", unsafe_allow_html=True)

st.caption("Intraday = Asc timer. Swing = Moon confirm. Framework = Saturn/Jupiter.")

