"""League leaderboards — sortable bargains/overpays vs fair / market / production value."""
import streamlit as st

import lib

st.set_page_config(page_title="League Leaderboards", page_icon="🏀", layout="wide")
st.title("League Leaderboards")
lib.require_data()

unit = lib.unit_toggle()
val = lib.load_valuations()

REF = {
    "Fair (cap-aware)": ("SURPLUS_FAIR", "MARKET_FAIR_PCT_CAP"),
    "Market (model)": ("SURPLUS_MARKET", "MARKET_PCT_CAP"),
    "Production value": ("SURPLUS_VALUE", "PRODUCTION_VALUE_PCT_CAP"),
}

c1, c2, c3 = st.columns(3)
season = c1.selectbox("Season", ["All"] + sorted(val["SEASON"].unique(), reverse=True), help=lib.HELP["season"])
arch = c2.selectbox("Archetype", ["All"] + sorted(val["ARCHETYPE_NAME"].unique()), help=lib.HELP["archetype"])
ref = c3.radio("Value reference", list(REF), horizontal=True, help=lib.HELP["value_reference"])
surplus_col, fair_col = REF[ref]

d = val.copy()
if season != "All":
    d = d[d["SEASON"] == season]
if arch != "All":
    d = d[d["ARCHETYPE_NAME"] == arch]
d = d[d["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]      # drop prorated artifacts

cols = ["PLAYER_NAME", "SEASON", "ARCHETYPE_NAME", "AGE", "ACTUAL_PCT_CAP", fair_col, surplus_col]
st.caption(f"Surplus = actual − {ref.lower()}. Negative = underpaid (bargain). "
           f"Rows below {lib.ACTUAL_FLOOR:.0%} of cap filtered out. {len(d):,} player-seasons.")

left, right = st.columns(2)
with left:
    st.subheader("Biggest bargains")
    disp, cfg = lib.value_table(d.nsmallest(25, surplus_col)[cols], [fair_col, surplus_col, "ACTUAL_PCT_CAP"], unit)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
with right:
    st.subheader("Biggest overpays")
    disp, cfg = lib.value_table(d.nlargest(25, surplus_col)[cols], [fair_col, surplus_col, "ACTUAL_PCT_CAP"], unit)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)

st.divider()
st.subheader("Over/underpay by archetype")
st.caption("Positive = market overpays the role. (Veteran-style premium shows here; rookie-scale "
           "seasons drag young-star archetypes negative — see the project notes.)")
st.dataframe(lib.archetype_surplus(val, None if season == "All" else season), width="stretch")
