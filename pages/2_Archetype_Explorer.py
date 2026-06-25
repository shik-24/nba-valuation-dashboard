"""Archetype explorer — over/underpay, the Stage 4 aging curve, and current members."""
import altair as alt
import streamlit as st

import lib

st.set_page_config(page_title="Archetype Explorer", page_icon="🏀", layout="wide")
st.title("Archetype Explorer")
lib.require_data()

val = lib.load_valuations()
aging = lib.load_aging()
retention = lib.load_retention()

archetypes = sorted(val["ARCHETYPE_NAME"].unique())
arch = st.selectbox("Archetype", archetypes)
season = lib.latest_season(val)

members = val[(val["ARCHETYPE_NAME"] == arch) & (val["SEASON"] == season)]
all_seasons = val[val["ARCHETYPE_NAME"] == arch]

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Members ({season})", len(members))
c2.metric("Mean surplus vs market", f"{all_seasons['SURPLUS_MARKET'].mean():+.1%}",
          help="Across all seasons. Positive = market overpays this role.")
c3.metric("Mean surplus vs value", f"{all_seasons['SURPLUS_VALUE'].mean():+.1%}")
c4.metric("% overpaid (vs market)", f"{(all_seasons['SURPLUS_MARKET'] > 0).mean():.0%}")

left, right = st.columns(2)

# ── aging curve (BPM trajectory with CI) ──
with left:
    st.subheader("Aging curve")
    a = aging[aging["ARCHETYPE_NAME"] == arch]
    if a.empty:
        st.info("No aging curve for this archetype.")
    else:
        band = alt.Chart(a).mark_area(opacity=0.2).encode(
            x=alt.X("AGE:Q", title="Age"),
            y=alt.Y("BPM_COND_LO:Q", title="BPM"), y2="BPM_COND_HI:Q")
        line = alt.Chart(a).mark_line(point=True).encode(
            x="AGE:Q", y=alt.Y("BPM_COMBINED:Q", title="BPM"),
            tooltip=["AGE", alt.Tooltip("BPM_COMBINED:Q", format=".2f")])
        st.altair_chart(band + line, width="stretch")
        st.caption("BPM_COMBINED = conditional performance × P(still active). Band = CI on the "
                   "conditional curve.")

# ── retention / survival ──
with right:
    st.subheader("Career survival")
    r = retention[retention["ARCHETYPE_NAME"] == arch]
    if r.empty:
        st.info("No retention curve for this archetype.")
    else:
        surv = alt.Chart(r).mark_line(point=True).encode(
            x=alt.X("AGE:Q", title="Age"),
            y=alt.Y("SURVIVAL:Q", title="P(still in league)", axis=alt.Axis(format="%")),
            tooltip=["AGE", alt.Tooltip("SURVIVAL:Q", format=".0%")])
        st.altair_chart(surv, width="stretch")
        st.caption("Share of the archetype still active by age (Stage 4 retention model).")

st.subheader(f"Members · {season}")
show = members.sort_values("PRODUCTION_VALUE_PCT_CAP", ascending=False)[
    ["PLAYER_NAME", "AGE", "TRAILING_vorp_3Y", "ACTUAL_PCT_CAP", "MARKET_PCT_CAP",
     "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_MARKET"]]
st.dataframe(show, hide_index=True, width="stretch")
