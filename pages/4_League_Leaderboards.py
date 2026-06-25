"""League leaderboards — sortable, filterable bargains / overpays vs market or production value."""
import streamlit as st

import lib

st.set_page_config(page_title="League Leaderboards", page_icon="🏀", layout="wide")
st.title("League Leaderboards")
lib.require_data()

val = lib.load_valuations()

c1, c2, c3 = st.columns(3)
season = c1.selectbox("Season", ["All"] + sorted(val["SEASON"].unique(), reverse=True))
arch = c2.selectbox("Archetype", ["All"] + sorted(val["ARCHETYPE_NAME"].unique()))
ref = c3.radio("Value reference", ["Market", "Production value"], horizontal=True)

surplus_col = "SURPLUS_MARKET" if ref == "Market" else "SURPLUS_VALUE"
fair_col = "MARKET_PCT_CAP" if ref == "Market" else "PRODUCTION_VALUE_PCT_CAP"

d = val.copy()
if season != "All":
    d = d[d["SEASON"] == season]
if arch != "All":
    d = d[d["ARCHETYPE_NAME"] == arch]
d = d[d["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]    # drop prorated artifacts

cols = ["PLAYER_NAME", "SEASON", "ARCHETYPE_NAME", "AGE", "ACTUAL_PCT_CAP", fair_col, surplus_col]
st.caption(f"Surplus = actual − {ref.lower()} value. Negative = underpaid (bargain). "
           f"Rows below {lib.ACTUAL_FLOOR:.0%} of cap filtered out. {len(d):,} player-seasons.")

left, right = st.columns(2)
with left:
    st.subheader("Biggest bargains")
    st.dataframe(d.nsmallest(25, surplus_col)[cols], hide_index=True, width="stretch")
with right:
    st.subheader("Biggest overpays")
    st.dataframe(d.nlargest(25, surplus_col)[cols], hide_index=True, width="stretch")

st.divider()
st.subheader("Over/underpay by archetype")
st.caption("Positive = market overpays the role. (Veteran-style premium shows here; rookie-scale "
           "seasons drag young-star archetypes negative — see the project notes.)")
st.dataframe(lib.archetype_surplus(val, None if season == "All" else season),
             width="stretch")
