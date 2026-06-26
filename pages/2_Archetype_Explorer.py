"""Archetype explorer — over/underpay, the Stage 4 aging + survival curves, members."""
import altair as alt
import streamlit as st

import lib

st.set_page_config(page_title="Archetype Explorer", page_icon="🏀", layout="wide")
st.title("Archetype Explorer")
lib.require_data()

unit = lib.unit_toggle()
val = lib.load_valuations()
aging = lib.load_aging()
retention = lib.load_retention()

c1, c2 = st.columns([3, 1])
arch = c1.selectbox("Archetype", sorted(val["ARCHETYPE_NAME"].unique()), help=lib.HELP["archetype"])
season = c2.selectbox("Season", sorted(val["SEASON"].unique(), reverse=True), help=lib.HELP["season"])

members = val[(val["ARCHETYPE_NAME"] == arch) & (val["SEASON"] == season)]

m1, m2, m3, m4 = st.columns(4)
m1.metric(f"Members ({season})", len(members), help="Players in this role this season.")
if members.empty:
    m2.metric("Mean surplus vs fair", "—")
    m3.metric("Mean surplus vs value", "—")
    m4.metric("% underpaid", "—")
else:
    m2.metric("Mean surplus vs fair", f"{members['SURPLUS_FAIR'].mean():+.1%}",
              help=f"Average fair value − pay for this role in {season}. Positive = the market "
                   "underpays this role; negative = it pays a premium (overpays).")
    m3.metric("Mean surplus vs value", f"{members['SURPLUS_VALUE'].mean():+.1%}",
              help=f"Average uncapped production worth − pay for this role in {season}. "
                   "Positive = paid below production worth.")
    m4.metric("% underpaid", f"{(members['SURPLUS_FAIR'] > 0).mean():.0%}",
              help=f"Share of this role paid below fair value (a bargain) in {season}.")

left, right = st.columns(2)
with left:
    st.subheader("Aging curve")
    a = aging[aging["ARCHETYPE_NAME"] == arch].copy()
    if a.empty:
        st.info("No aging curve for this archetype.")
    else:
        # The drawn line is the washout-blended BPM_COMBINED, so the band must wrap THAT curve, not
        # the conditional one. Push the conditional CI through the same blend (combined =
        # cond·P_active + replacement·(1−P_active)) so the line always sits inside the band.
        p = a["P_ACTIVE"]
        a["COMB_LO"] = a["BPM_COND_LO"] * p + lib.REPLACEMENT_BPM * (1 - p)
        a["COMB_HI"] = a["BPM_COND_HI"] * p + lib.REPLACEMENT_BPM * (1 - p)
        band = alt.Chart(a).mark_area(opacity=0.18).encode(
            x=alt.X("AGE:Q", title="Age"), y=alt.Y("COMB_LO:Q", title="BPM"), y2="COMB_HI:Q")
        line = alt.Chart(a).mark_line(point=True, color="#1f77b4").encode(
            x="AGE:Q", y=alt.Y("BPM_COMBINED:Q", title="BPM"),
            tooltip=[alt.Tooltip("AGE:Q", title="Age"), alt.Tooltip("BPM_COMBINED:Q", title="BPM", format=".2f")])
        st.altair_chart(band + line, width="stretch")

with right:
    st.subheader("Career survival")
    r = retention[retention["ARCHETYPE_NAME"] == arch]
    if r.empty:
        st.info("No retention curve for this archetype.")
    else:
        surv = alt.Chart(r).mark_line(point=True, color="#2e9e3f").encode(
            x=alt.X("AGE:Q", title="Age"),
            y=alt.Y("SURVIVAL:Q", title="P(still in league)", axis=alt.Axis(format="%")),
            tooltip=[alt.Tooltip("AGE:Q", title="Age"), alt.Tooltip("SURVIVAL:Q", title="still active", format=".0%")])
        st.altair_chart(surv, width="stretch")

with st.expander("ℹ️ How to read the aging curve"):
    pk = None
    if not a.empty:
        pk = int(a.loc[a["BPM_COMBINED"].idxmax(), "AGE"])
    st.markdown(
        "The **aging curve** is the average production path for this role by age, in **BPM** "
        "(Box Plus/Minus — points per 100 possessions above an average player; 0 = average, +5 = "
        "All-NBA, −2 = replacement). It's `performance while playing × the chance he's still in the "
        "league`, so it already bakes in players washing out.\n\n"
        f"- **Peak** is around age **{pk}** for {arch}" + (".\n" if pk else " (n/a).\n") +
        "- The **shaded band** is the uncertainty around the curve — wider where there are fewer players.\n"
        "- The **survival** chart (right) is the share of this role still in the league by age — how "
        "quickly the role washes out.\n\n"
        "*Example:* if the line peaks near 27–29 then slopes down, a 4-year deal signed at 30 is "
        "buying mostly the **decline** — useful when you weigh a contract's later years."
    )

st.subheader(f"Members · {season}")
cols = ["PLAYER_NAME", "AGE", "TRAILING_vorp_3Y", "ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP",
        "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_FAIR"]
vcols = ["ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_FAIR"]
disp, cfg = lib.value_table(members.sort_values("PRODUCTION_VALUE_PCT_CAP", ascending=False)[cols],
                            vcols, unit, fixed_season=season)
st.dataframe(lib.color_surplus(disp, ["SURPLUS_FAIR"]), hide_index=True, width="stretch", column_config=cfg)
