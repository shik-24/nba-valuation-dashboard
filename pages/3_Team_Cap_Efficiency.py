"""Team cap efficiency — roster value vs pay, total surplus, bargains & worst contracts."""
import streamlit as st

import lib

st.set_page_config(page_title="Team Cap Efficiency", page_icon="🏀", layout="wide")
st.title("Team Cap Efficiency")
lib.require_data()

unit = lib.unit_toggle()
val = lib.load_valuations()
teams = lib.load_team_lookup()
vt = lib.with_team(val, teams)

c1, c2 = st.columns(2)
season = c1.selectbox("Season", sorted(vt["SEASON"].unique(), reverse=True), help=lib.HELP["season"])
team_opts = sorted(vt.loc[(vt["SEASON"] == season) & vt["TEAM"].notna(), "TEAM"].unique())
team = c2.selectbox("Team", team_opts, help=lib.HELP["team"])

roster = vt[(vt["SEASON"] == season) & (vt["TEAM"] == team)].copy()
if roster.empty:
    st.info("No roster rows for this team/season.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Players", len(roster), help="Roster players with enough recent history to value.")
m2.metric("Payroll (% cap)", f"{roster['ACTUAL_PCT_CAP'].sum():.0%}", help=lib.HELP["payroll"])
m3.metric("Surplus vs fair", f"{(-roster['SURPLUS_FAIR'].sum()):+.0%}", help=lib.HELP["team_surplus"])
m4.metric("Surplus vs production value", f"{(-roster['SURPLUS_VALUE'].sum()):+.0%}",
          help="Roster's uncapped production worth minus pay. Positive = paid below what it's worth on the floor.")

st.caption("Note: one team per player-season (traded players attributed to their last-listed team), "
           "and only players with enough trailing history are valued — so payroll is approximate.")

cols = ["PLAYER_NAME", "ARCHETYPE_NAME", "AGE", "ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP",
        "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_FAIR"]
vcols = ["ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_FAIR"]

st.subheader("Roster")
disp, cfg = lib.value_table(roster.sort_values("ACTUAL_PCT_CAP", ascending=False)[cols],
                            vcols, unit, fixed_season=season)
st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)

gated = roster[roster["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]
left, right = st.columns(2)
with left:
    st.subheader("Best bargains")
    disp, cfg = lib.value_table(gated.nsmallest(5, "SURPLUS_FAIR")[cols], vcols, unit, fixed_season=season)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
with right:
    st.subheader("Worst contracts")
    disp, cfg = lib.value_table(gated.nlargest(5, "SURPLUS_FAIR")[cols], vcols, unit, fixed_season=season)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
