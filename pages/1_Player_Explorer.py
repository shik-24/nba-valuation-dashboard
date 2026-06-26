"""Player explorer — value lines vs the max, cap-aware verdict, SHAP 'why', and comps."""
import altair as alt
import pandas as pd
import streamlit as st

import lib

st.set_page_config(page_title="Player Explorer", page_icon="🏀", layout="wide")
st.title("Player Explorer")
lib.require_data()

unit = lib.unit_toggle()
val = lib.load_valuations()
names = sorted(val["PLAYER_NAME"].unique())
default = names.index("Nikola Jokić") if "Nikola Jokić" in names else 0
player = st.selectbox("Player", names, index=default, help=lib.HELP["player"])

pdf = val[val["PLAYER_NAME"] == player].sort_values("SEASON")
pid = pdf["PLAYER_ID"].iloc[0]
season = lib.latest_season(pdf)
row = pdf[pdf["SEASON"] == season].iloc[0]


def fmt(pct: float) -> str:
    if unit == "$ millions":
        m = lib.pct_to_millions(pct, season)
        return f"${m}M" if m is not None else "—"
    return f"{pct:.1%}"


# ── current-season headline ──
st.subheader(f"{player} — {season}  ·  {row['ARCHETYPE_NAME']}  ·  age {row['AGE']:.0f}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Actual", fmt(row["ACTUAL_PCT_CAP"]), help=lib.HELP["actual"])
c2.metric("Fair (cap-aware)", fmt(row["MARKET_FAIR_PCT_CAP"]), help=lib.HELP["fair"])
c3.metric("Production value", fmt(row["PRODUCTION_VALUE_PCT_CAP"]), help=lib.HELP["production_value"])
c4.metric("Max line", fmt(row["MAX_PCT_CAP"]), help=lib.HELP["max"])

v_fair, v_val = lib.verdict(row["SURPLUS_FAIR"]), lib.verdict(row["SURPLUS_VALUE"])
badge = "  ·  ⭐ **Max player** (worth ≥ his max)" if row["IS_MAX_PLAYER"] == 1 else ""
st.markdown(
    f"**vs fair market:** {v_fair} ({row['SURPLUS_FAIR']:+.1%} cap)  ·  "
    f"**vs production worth:** {v_val} ({row['SURPLUS_VALUE']:+.1%} cap){badge}"
)

with st.expander("ℹ️ How to read these numbers"):
    st.markdown(
        "- **Actual** — what he's paid this year (his real, often years-old contract).\n"
        "- **Market (model)** — what a *fresh* deal for his recent track record would fetch "
        "(XGBoost on real signings). Capped, and it **under-prices true stars** (it predicts a "
        "bucket average and can't exceed ~0.31), so a max player can look 'overpaid vs market'.\n"
        "- **Comps** — what *genuinely similar players actually signed for* (kNN). Another take on the price.\n"
        "- **Production value** — what his on-court production is **worth**, *uncapped* (can exceed the max).\n"
        "- **Fair (cap-aware)** — the grading benchmark: the market pays the **lesser of worth and the max**, "
        "so stars snap to the max and read *fair*, not falsely overpaid.\n\n"
        "For most players price ≈ worth and everything clusters. For stars, worth ≫ the capped price — "
        "that gap is the cap ceiling, and it's why an underpaid superstar can still be 'paid the max'."
    )

# ── value lines across seasons ──
st.subheader("Value across seasons (% of cap)")
long = pdf.melt(id_vars="SEASON", value_vars=lib.CHART_COLS, var_name="metric", value_name="pct_cap")
long["metric"] = long["metric"].map(lib.VALUE_COLS)
chart = (
    alt.Chart(long).mark_line(point=True).encode(
        x=alt.X("SEASON:N", title=None),
        y=alt.Y("pct_cap:Q", title="% of cap", axis=alt.Axis(format="%")),
        color=alt.Color("metric:N", title=None),
        strokeDash=alt.condition(alt.datum.metric == "Max line", alt.value([4, 4]), alt.value([0])),
        tooltip=["SEASON", "metric", alt.Tooltip("pct_cap:Q", format=".1%")],
    ).properties(height=360)
)
st.altair_chart(chart, width="stretch")
st.caption("Where **production value** rises above the **max line**, he's worth more than the CBA "
           "lets a team pay — underpaid even at a max.")

# ── SHAP 'why' (precomputed; optional) ──
st.subheader("Why the market values him here")
shap = lib.load_shap()
if shap is None:
    st.info("SHAP not exported yet — run the updated `07_export_dashboard_data.ipynb` to enable.")
else:
    srow = shap[(shap["PLAYER_ID"] == pid) & (shap["SEASON"] == season)]
    if srow.empty:
        st.info("No SHAP row for this player-season.")
    else:
        sv = (srow.drop(columns=[c for c in ["PLAYER_ID", "SEASON", "BASE_VALUE"] if c in srow])
                  .iloc[0].rename(lambda c: c.replace("shap_", "")))
        sv = sv.reindex(sv.abs().sort_values(ascending=False).index).head(10).reset_index()
        sv.columns = ["feature", "shap"]
        sv["feature"] = sv["feature"].str.replace("ARCH_", "archetype: ", regex=False)
        bar = alt.Chart(sv).mark_bar().encode(
            x=alt.X("shap:Q", title="contribution to predicted %cap", axis=alt.Axis(format="%")),
            y=alt.Y("feature:N", sort="-x", title=None),
            color=alt.condition(alt.datum.shap > 0, alt.value("#2e7d32"), alt.value("#c0392b")),
            tooltip=["feature", alt.Tooltip("shap:Q", format="+.3f")])
        st.altair_chart(bar, width="stretch")
        st.caption("Green pushes his market value up, red down (top 10 features, in %cap units).")

# ── comparable signings ──
st.subheader(f"Comparable signings · {season}")
comps_tbl = lib.load_comps()
if comps_tbl is not None:
    c = comps_tbl[(comps_tbl["PLAYER_ID"] == pid) & (comps_tbl["SEASON"] == season)]
    if not c.empty:
        disp, cfg = lib.value_table(c.assign(SEASON=season)[["comp_name", "comp_pct_cap", "distance"]],
                                    ["comp_pct_cap"], unit, fixed_season=season)
        st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
        st.caption("The actual signings (most-similar first) that drove the kNN comps value.")
    else:
        st.info("No comps row for this player-season.")
else:
    comps = lib.find_comps(val, pid, season, k=8)
    if comps.empty:
        st.info("No same-archetype comparables in this season.")
    else:
        disp, cfg = lib.value_table(
            comps[["PLAYER_NAME", "AGE", "TRAILING_vorp_3Y", "ACTUAL_PCT_CAP",
                   "MARKET_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP"]].assign(SEASON=season),
            ["ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP"], unit, fixed_season=season)
        st.dataframe(disp.drop(columns="SEASON"), hide_index=True, width="stretch", column_config=cfg)
        st.caption("Closest same-archetype peers this season (simplified — export comps for the real kNN list).")

with st.expander("Season-by-season table"):
    base = ["SEASON", "AGE", "ARCHETYPE_NAME", "TRAILING_vorp_3Y"]
    vcols = ["ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "TRUE_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP",
             "MARKET_FAIR_PCT_CAP", "MAX_PCT_CAP", "SURPLUS_FAIR", "SURPLUS_VALUE"]
    disp, cfg = lib.value_table(pdf[base + vcols], vcols, unit)
    st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
