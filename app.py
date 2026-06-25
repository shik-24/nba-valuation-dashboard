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
val = lib.load_valuations()
season = lib.latest_season(val)
cur = val[val["SEASON"] == season]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Player-seasons", f"{len(val):,}")
c2.metric("Players", f"{val['PLAYER_ID'].nunique():,}")
c3.metric(f"Max players ({season})", int(cur["IS_MAX_PLAYER"].sum()),
          help="Production value ≥ the player's experience-based max (25/30/35% of cap).")
c4.metric("Seasons", f"{val['SEASON'].min()} – {val['SEASON'].max()}")

st.markdown(
    "**Models:** XGBoost market model (grouped-CV R² 0.70) · kNN comps · Tobit censored "
    "production-value model (uncensored-CV R² 0.50, can exceed the max). "
    "Use the **pages in the sidebar** to explore by player, archetype, team, or leaguewide."
)

st.divider()
gated = cur[cur["ACTUAL_PCT_CAP"] >= lib.ACTUAL_FLOOR]
left, right = st.columns(2)
show = ["PLAYER_NAME", "ARCHETYPE_NAME", "ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "SURPLUS_MARKET"]
with left:
    st.subheader(f"Biggest bargains · {season}")
    st.dataframe(gated.nsmallest(10, "SURPLUS_MARKET")[show], hide_index=True, width="stretch")
with right:
    st.subheader(f"Biggest overpays · {season}")
    st.dataframe(gated.nlargest(10, "SURPLUS_MARKET")[show], hide_index=True, width="stretch")

st.caption("Surplus vs the market model (XGB). Negative = underpaid (bargain), positive = overpaid. "
           f"Rows below {lib.ACTUAL_FLOOR:.0%} of cap (prorated/10-day deals) are filtered out.")
