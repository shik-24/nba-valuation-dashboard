"""Team cap efficiency — roster value vs pay, surplus over time, bargains & worst contracts."""
import altair as alt
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

# league-relative context (#11): production/fair surplus is biased "underpaid" leaguewide, so
# the meaningful read is THIS team vs the average team, not the absolute sign.
team_tot = vt[vt["SEASON"] == season].groupby("TEAM")["SURPLUS_FAIR"].sum()
lg_avg = team_tot.mean()
this_tot = float(team_tot[team])
rank = int((team_tot > this_tot).sum()) + 1

m1, m2, m3, m4 = st.columns(4)
m1.metric("Players valued", len(roster), help="Roster players with enough recent history to value.")
m2.metric("Payroll (% cap)", f"{roster['ACTUAL_PCT_CAP'].sum():.0%}", help=lib.HELP["payroll"])
s_fair = roster["SURPLUS_FAIR"].sum()
m3.metric("Surplus vs fair", "Underpaid" if s_fair > 0 else "Overpaid", delta=f"{s_fair:+.0%} cap",
          help=lib.HELP["team_surplus"])
m4.metric("Rank vs league", f"#{rank} / {len(team_tot)}", delta=f"{this_tot - lg_avg:+.0%} vs avg team",
          help="Where this roster's total fair-surplus ranks leaguewide. Leaguewide everyone reads "
               "'underpaid' vs uncapped value, so rank/vs-average is the honest signal, not the raw sign.")

st.caption("One team per player-season (traded players go to their last team); only players with "
           "enough trailing history are valued, so payroll is approximate.")

# ── surplus over time (#12): is this front office consistently good/bad at deals? ──
st.subheader("Roster surplus over time")
ts = (vt[vt["TEAM"] == team].groupby("SEASON")["SURPLUS_FAIR"].sum().rename("team").reset_index())
lg = (vt.groupby(["SEASON", "TEAM"])["SURPLUS_FAIR"].sum().groupby("SEASON").mean().rename("league").reset_index())
ts = ts.merge(lg, on="SEASON")
band = ts.melt("SEASON", ["team", "league"], var_name="series", value_name="surplus")
band["series"] = band["series"].map({"team": team, "league": "league avg"})
chart = alt.Chart(band).mark_line(point=True).encode(
    x=alt.X("SEASON:N", title=None),
    y=alt.Y("surplus:Q", title="total fair surplus (% cap)", axis=alt.Axis(format="%")),
    color=alt.Color("series:N", title=None,
                    scale=alt.Scale(domain=[team, "league avg"], range=["#1f77b4", "#999999"])),
    strokeDash=alt.condition(alt.datum.series == "league avg", alt.value([4, 4]), alt.value([0])),
    tooltip=["SEASON", "series", alt.Tooltip("surplus:Q", format="+.1%")],
).properties(height=300)
st.altair_chart(chart, width="stretch")
st.caption("Above the dashed league line = the team is getting more roster value-for-money than "
           "average that season. A team consistently above is drafting/signing well.")

cols = ["PLAYER_NAME", "ARCHETYPE_NAME", "AGE", "ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP",
        "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_FAIR"]
vcols = ["ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP", "SURPLUS_FAIR"]

st.subheader("Roster")
disp, cfg = lib.value_table(roster.sort_values("ACTUAL_PCT_CAP", ascending=False)[cols],
                            vcols, unit, fixed_season=season)
st.dataframe(lib.color_surplus(disp, ["SURPLUS_FAIR"]), hide_index=True, width="stretch", column_config=cfg)

gated = roster[roster["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]
left, right = st.columns(2)
with left:
    st.subheader("Best bargains")
    disp, cfg = lib.value_table(gated.nlargest(5, "SURPLUS_FAIR")[cols], vcols, unit, fixed_season=season)
    st.dataframe(lib.color_surplus(disp, ["SURPLUS_FAIR"]), hide_index=True, width="stretch", column_config=cfg)
with right:
    st.subheader("Worst contracts")
    disp, cfg = lib.value_table(gated.nsmallest(5, "SURPLUS_FAIR")[cols], vcols, unit, fixed_season=season)
    st.dataframe(lib.color_surplus(disp, ["SURPLUS_FAIR"]), hide_index=True, width="stretch", column_config=cfg)
