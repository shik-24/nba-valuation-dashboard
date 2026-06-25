"""Player explorer — the four value lines vs the max across a player's career, plus comps."""
import altair as alt
import pandas as pd
import streamlit as st

import lib

st.set_page_config(page_title="Player Explorer", page_icon="🏀", layout="wide")
st.title("Player Explorer")
lib.require_data()

val = lib.load_valuations()
names = sorted(val["PLAYER_NAME"].unique())
default = names.index("Nikola Jokić") if "Nikola Jokić" in names else 0
player = st.selectbox("Player", names, index=default)

pdf = val[val["PLAYER_NAME"] == player].sort_values("SEASON")
pid = pdf["PLAYER_ID"].iloc[0]
season = lib.latest_season(pdf)
row = pdf[pdf["SEASON"] == season].iloc[0]

# ── current-season headline ──
st.subheader(f"{player} — {season}  ·  {row['ARCHETYPE_NAME']}  ·  age {row['AGE']:.0f}")
cols = st.columns(5)
cards = [("Actual", "ACTUAL_PCT_CAP"), ("Market", "MARKET_PCT_CAP"), ("Comps", "TRUE_PCT_CAP"),
         ("Production value", "PRODUCTION_VALUE_PCT_CAP"), ("Max line", "MAX_PCT_CAP")]
for col, (label, c) in zip(cols, cards):
    dollars = lib.pct_to_millions(row[c], season)
    col.metric(label, f"{row[c]:.1%}", f"${dollars}M" if dollars is not None else None,
               delta_color="off")

v_mkt, v_val = lib.verdict(row["SURPLUS_MARKET"]), lib.verdict(row["SURPLUS_VALUE"])
badge = "  ·  ⭐ **Max player** (worth ≥ his max)" if row["IS_MAX_PLAYER"] == 1 else ""
st.markdown(
    f"**vs market:** {v_mkt} ({row['SURPLUS_MARKET']:+.1%} cap)  ·  "
    f"**vs production value:** {v_val} ({row['SURPLUS_VALUE']:+.1%} cap){badge}"
)

# ── value lines across seasons ──
st.subheader("Value across seasons")
long = pdf.melt(id_vars="SEASON", value_vars=list(lib.VALUE_COLS),
                var_name="metric", value_name="pct_cap")
long["metric"] = long["metric"].map(lib.VALUE_COLS)
chart = (
    alt.Chart(long).mark_line(point=True).encode(
        x=alt.X("SEASON:N", title=None),
        y=alt.Y("pct_cap:Q", title="% of cap", axis=alt.Axis(format="%")),
        color=alt.Color("metric:N", title=None,
                        sort=list(lib.VALUE_COLS.values())),
        strokeDash=alt.condition(alt.datum.metric == "Max line", alt.value([4, 4]), alt.value([0])),
        tooltip=["SEASON", "metric", alt.Tooltip("pct_cap:Q", format=".1%")],
    ).properties(height=380)
)
st.altair_chart(chart, width="stretch")
st.caption("Where **production value** rises above the **max line**, the player is worth more than "
           "the CBA lets a team pay — i.e. underpaid even at a max.")

# ── comps ──
st.subheader(f"Closest comparables · {season}")
comps = lib.find_comps(val, pid, season, k=8)
if comps.empty:
    st.info("No same-archetype comparables in this season.")
else:
    show = comps[["PLAYER_NAME", "AGE", "TRAILING_vorp_3Y", "ACTUAL_PCT_CAP",
                  "MARKET_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP"]].copy()
    st.dataframe(show, hide_index=True, width="stretch")

with st.expander("Season-by-season table"):
    st.dataframe(pdf[["SEASON", "AGE", "ARCHETYPE_NAME", "TRAILING_vorp_3Y", "ACTUAL_PCT_CAP",
                      "MARKET_PCT_CAP", "TRUE_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP",
                      "MAX_PCT_CAP", "SURPLUS_MARKET", "SURPLUS_VALUE"]],
                 hide_index=True, width="stretch")
