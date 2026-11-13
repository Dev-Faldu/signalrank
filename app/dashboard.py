"""SignalRank - "What matters now" dashboard (Streamlit).

Talks to the FastAPI service only (no direct file access), so it works the same
locally and in Docker Compose.
"""
import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API = os.environ.get("SIGNALRANK_API", "http://localhost:8000")
CAMEO = {"01": "Public statement", "02": "Appeal", "03": "Express intent to cooperate", "04": "Consult",
         "05": "Diplomatic cooperation", "06": "Material cooperation", "07": "Provide aid", "08": "Yield",
         "09": "Investigate", "10": "Demand", "11": "Disapprove", "12": "Reject", "13": "Threaten",
         "14": "Protest", "15": "Show force", "16": "Reduce relations", "17": "Coerce", "18": "Assault",
         "19": "Fight", "20": "Mass violence"}
FIPS = {"US": "United States", "UK": "United Kingdom", "IN": "India", "CH": "China", "RS": "Russia",
        "IS": "Israel", "UP": "Ukraine", "IR": "Iran", "GM": "Germany", "FR": "France", "CA": "Canada",
        "AS": "Australia", "PK": "Pakistan", "NI": "Nigeria", "SF": "South Africa", "JA": "Japan",
        "BR": "Brazil", "MX": "Mexico", "TU": "Turkey", "SY": "Syria", "GZ": "Gaza Strip", "LE": "Lebanon"}

st.set_page_config(page_title="SignalRank", page_icon="📡", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.4rem;max-width:1250px}
div[data-testid=stMetric]{background:#f6f8fb;border:1px solid #e3e8ef;border-radius:12px;padding:12px 16px}
h1{letter-spacing:-.5px}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=10)
def get(path, **params):
    r = requests.get(f"{API}{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


try:
    health = get("/health")
except Exception as e:
    st.error(f"API not reachable at {API}: {e}")
    st.stop()

st.title("📡 SignalRank — what matters now")
st.caption("Predicts, from the first hour of news coverage, which GDELT events will be covered by "
           "many publishers over the next 48 hours.")

with st.sidebar:
    st.header("Filters")
    hours = st.slider("Look-back window (hours of data time)", 3, 72, 24)
    n = st.slider("Events to show", 5, 100, 25)
    only_flag = st.checkbox("Only events flagged as important", True)
    st.divider()
    st.caption(f"Model: **{health['model']}**  \nDecision threshold: {health['threshold']:.3f}  \n"
               f"Scored events in store: {health['scored_events_available']:,}")
    if st.button("Refresh"):
        st.cache_data.clear()

top = get("/top", n=500, hours=hours)
stats = get("/stats", hours=hours)
ev = pd.DataFrame(top["events"])
if ev.empty:
    st.warning("No scored events in this window yet.")
    st.stop()
ev["event_type"] = ev.cameo_root.map(CAMEO).fillna(ev.cameo_root)
ev["country"] = ev.geo_country.map(FIPS).fillna(ev.geo_country)
ev["domain"] = ev.source_url.str.extract(r"https?://(?:www\.)?([^/]+)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Events scored", f"{stats['n_events']:,}")
c2.metric("Flagged important", f"{stats['n_important']:,}", f"{stats['n_important']/max(stats['n_events'],1):.1%} of events")
c3.metric("Data as of (UTC)", top["as_of"][5:16])
c4.metric("Highest score", f"{ev.score.max():.2f}")

tab1, tab2, tab3, tab4 = st.tabs(["Ranked events", "Map", "Trends", "Try an event"])

with tab1:
    show = ev[ev.predicted_important == 1] if only_flag else ev
    show = show.head(n)[["score", "event_type", "country", "geo_name", "src_1h", "m_1h", "avg_tone",
                         "domain", "t0", "source_url"]]
    st.dataframe(show, hide_index=True, use_container_width=True, height=560, column_config={
        "score": st.column_config.ProgressColumn("Importance score", min_value=0, max_value=1, format="%.2f"),
        "event_type": "Event type", "country": "Country", "geo_name": "Location",
        "src_1h": st.column_config.NumberColumn("Publishers (1h)"),
        "m_1h": st.column_config.NumberColumn("Mentions (1h)"),
        "avg_tone": st.column_config.NumberColumn("Tone", format="%.1f"),
        "domain": "First source", "t0": st.column_config.DatetimeColumn("First seen", format="MMM D, HH:mm"),
        "source_url": st.column_config.LinkColumn("Link", display_text="open")})

with tab2:
    g = ev.dropna(subset=["lat", "lon"]).copy()
    g = g[g.predicted_important == 1] if only_flag else g
    g = g.head(300)
    fig = px.scatter_geo(g, lat="lat", lon="lon", size="score", color="score", hover_name="geo_name",
                         hover_data={"event_type": True, "src_1h": True, "score": ":.2f", "lat": False, "lon": False},
                         color_continuous_scale="YlOrRd", projection="natural earth", size_max=18)
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0), coloraxis_colorbar_title="Score",
                      geo=dict(bgcolor="rgba(0,0,0,0)", showland=True, landcolor="#eef1f5", showcountries=True))
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    h = pd.DataFrame(stats["hourly"])
    h["important"] = h.important.where(h.n > 0)
    h["n"] = h.n.where(h.n > 0)   # hours with no scored data show as gaps
    a, b = st.columns([3, 2])
    with a:
        f = go.Figure()
        f.add_bar(x=h.t0, y=h.important, name="Flagged important", marker_color="#e4572e")
        f.add_scatter(x=h.t0, y=h.n, name="All scored events", yaxis="y2", line=dict(color="#335c81"))
        f.update_layout(title="Important events per hour", height=380, margin=dict(l=0, r=0, t=40, b=0),
                        yaxis2=dict(overlaying="y", side="right", showgrid=False, rangemode="tozero"), legend=dict(orientation="h"))
        st.plotly_chart(f, use_container_width=True)
    with b:
        ct = pd.Series(stats["top_countries"]).rename(index=FIPS).sort_values()
        st.plotly_chart(px.bar(ct, orientation="h", title="Where important events happen",
                               color_discrete_sequence=["#335c81"]).update_layout(
            height=380, showlegend=False, margin=dict(l=0, r=0, t=40, b=0), xaxis_title="", yaxis_title=""),
            use_container_width=True)
    ty = pd.Series(stats["top_event_types"]).rename(index=CAMEO).sort_values()
    st.plotly_chart(px.bar(ty, orientation="h", title="What kind of events",
                           color_discrete_sequence=["#e4572e"]).update_layout(
        height=300, showlegend=False, margin=dict(l=0, r=0, t=40, b=0), xaxis_title="", yaxis_title=""),
        use_container_width=True)

with tab4:
    st.write("Enter what is known one hour after an event appears; the API returns the model's score.")
    a, b, c = st.columns(3)
    src = a.number_input("Distinct publishers in first hour", 0, 500, 3)
    mentions = a.number_input("Mentions in first hour", 0, 5000, 6)
    langs = a.number_input("Languages in first hour", 0, 30, 2)
    root = b.selectbox("Event type", list(CAMEO), format_func=lambda k: f"{k} - {CAMEO[k]}", index=13)
    ctry = b.selectbox("Country", list(FIPS), format_func=lambda k: FIPS[k])
    gold = b.slider("Goldstein scale (conflict ↔ cooperation)", -10.0, 10.0, -4.0)
    tone = c.slider("Average tone", -15.0, 15.0, -3.0)
    quad = c.selectbox("Quad class", [1, 2, 3, 4], index=3,
                       format_func=lambda k: {1: "1 verbal cooperation", 2: "2 material cooperation",
                                              3: "3 verbal conflict", 4: "4 material conflict"}[k])
    if st.button("Score this event", type="primary"):
        body = dict(m_1h=mentions, m_15m=max(1, mentions // 2), src_1h=src, lang_1h=langs, art_1h=mentions,
                    cameo_root=root, geo_country=ctry, goldstein=gold, avg_tone=tone, tone_mean_1h=tone,
                    quad_class=quad, num_mentions_export=mentions, num_sources_export=src, is_root_event=1,
                    geo_type=3, themes=[])
        r = requests.post(f"{API}/predict", json=body, timeout=120).json()
        st.metric("Importance score", f"{r['score']:.2f}", "likely to matter" if r["important"] else "likely minor")
        st.progress(min(1.0, r["score"]))
