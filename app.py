"""NBA Player Valuation dashboard — home / overview.

Run locally:  cd dashboard && streamlit run app.py
The sidebar exposes the four explorer pages (player / archetype / team / leaderboards).
"""
import streamlit as st

import lib

st.set_page_config(page_title="NBA Valuation", page_icon="🏀", layout="wide")

st.title("🏀 NBA Player Valuation & Contract Efficiency")
st.caption(
    "Three valuations of every player-season (all in % of the salary cap): a **market** price "
    "(what the market pays), a **comps** value (what similar players earn), and an uncapped "
    "**production value** (what they're worth — can exceed the max). Surplus = actual − fair."
)

lib.require_data()
unit = lib.unit_toggle()
val = lib.load_valuations()
season = lib.latest_season(val)
cur = val[val["SEASON"] == season]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Player-seasons", f"{len(val):,}", help="Every player-season we have enough history to value.")
c2.metric("Players", f"{val['PLAYER_ID'].nunique():,}", help="Distinct players across all seasons.")
c3.metric(f"Max players ({season})", int(cur["IS_MAX_PLAYER"].sum()), help=lib.HELP["is_max_player"])
c4.metric("Seasons", f"{val['SEASON'].min()} – {val['SEASON'].max()}", help="Range of seasons covered.")

st.markdown(
    "**Models:** XGBoost market model (grouped-CV R² 0.70) · kNN comps · Tobit censored "
    "production-value model (uncensored-CV R² 0.50, can exceed the max). "
    "Use the **pages in the sidebar** to explore by player, archetype, team, or leaguewide."
)

st.divider()
gated = cur[cur["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]
left, right = st.columns(2)
show = ["PLAYER_NAME", "ARCHETYPE_NAME", "ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP", "SURPLUS_FAIR"]
vcols = ["ACTUAL_PCT_CAP", "MARKET_FAIR_PCT_CAP", "SURPLUS_FAIR"]
with left:
    st.subheader(f"Biggest bargains · {season}")
    disp, cfg = lib.value_table(gated.nsmallest(10, "SURPLUS_FAIR")[show], vcols, unit, fixed_season=season)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
with right:
    st.subheader(f"Biggest overpays · {season}")
    disp, cfg = lib.value_table(gated.nlargest(10, "SURPLUS_FAIR")[show], vcols, unit, fixed_season=season)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)

st.caption("Surplus vs the **cap-aware fair value** (the market pays the lesser of worth and the max). "
           "Negative = underpaid (bargain), positive = overpaid. "
           f"Rows below {lib.ACTUAL_FLOOR:.0%} of cap (prorated/10-day deals) are filtered out.")
