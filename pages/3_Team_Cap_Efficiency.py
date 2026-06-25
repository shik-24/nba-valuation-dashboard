"""Team cap efficiency — roster value vs pay, total surplus, bargains & worst contracts."""
import streamlit as st

import lib

st.set_page_config(page_title="Team Cap Efficiency", page_icon="🏀", layout="wide")
st.title("Team Cap Efficiency")
lib.require_data()

val = lib.load_valuations()
teams = lib.load_team_lookup()
vt = lib.with_team(val, teams)

c1, c2 = st.columns(2)
season = c1.selectbox("Season", sorted(vt["SEASON"].unique(), reverse=True))
team_opts = sorted(vt.loc[(vt["SEASON"] == season) & vt["TEAM"].notna(), "TEAM"].unique())
team = c2.selectbox("Team", team_opts)

roster = vt[(vt["SEASON"] == season) & (vt["TEAM"] == team)].copy()
if roster.empty:
    st.info("No roster rows for this team/season.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Players", len(roster))
m1.caption("with enough trailing history to value")
m2.metric("Payroll (% cap)", f"{roster['ACTUAL_PCT_CAP'].sum():.0%}")
m3.metric("Surplus vs market", f"{(-roster['SURPLUS_MARKET'].sum()):+.0%}",
          help="Sum of (fair − actual). Positive = roster is underpaid relative to market value.")
m4.metric("Surplus vs production value", f"{(-roster['SURPLUS_VALUE'].sum()):+.0%}")

st.caption("Note: one team per player-season (traded players attributed to their last-listed team), "
           "and only players with enough trailing history are valued — so payroll is approximate.")

cols = ["PLAYER_NAME", "ARCHETYPE_NAME", "AGE", "ACTUAL_PCT_CAP", "MARKET_PCT_CAP",
        "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_MARKET"]
st.subheader("Roster")
st.dataframe(roster.sort_values("ACTUAL_PCT_CAP", ascending=False)[cols],
             hide_index=True, width="stretch")

gated = roster[roster["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]
left, right = st.columns(2)
with left:
    st.subheader("Best bargains")
    st.dataframe(gated.nsmallest(5, "SURPLUS_MARKET")[cols], hide_index=True, width="stretch")
with right:
    st.subheader("Worst contracts")
    st.dataframe(gated.nlargest(5, "SURPLUS_MARKET")[cols], hide_index=True, width="stretch")
