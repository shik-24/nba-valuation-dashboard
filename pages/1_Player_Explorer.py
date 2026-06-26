"""Player explorer — value lines vs the max, cap-aware verdict, career arc, SHAP 'why', comps."""
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

c_player, c_season = st.columns([3, 1])
player = c_player.selectbox("Player", names, index=default, help=lib.HELP["player"])
pdf = val[val["PLAYER_NAME"] == player].sort_values("SEASON")
pid = pdf["PLAYER_ID"].iloc[0]
seasons = list(pdf["SEASON"])
season = c_season.selectbox("Season", seasons, index=len(seasons) - 1, help=lib.HELP["season"])
row = pdf[pdf["SEASON"] == season].iloc[0]


def fmt(pct: float) -> str:
    if unit == "$ millions":
        m = lib.pct_to_millions(pct, season)
        return f"${m}M" if m is not None else "—"
    return f"{pct:.1%}"


# ── current-season headline: all five values + max ──
st.subheader(f"{player} — {season}  ·  {row['ARCHETYPE_NAME']}  ·  age {row['AGE']:.0f}")
cards = [("Actual", "ACTUAL_PCT_CAP", "actual"), ("Market", "MARKET_PCT_CAP", "market"),
         ("Comps", "TRUE_PCT_CAP", "comps"), ("Production value", "PRODUCTION_VALUE_PCT_CAP", "production_value"),
         ("Fair", "MARKET_FAIR_PCT_CAP", "fair"), ("Max", "MAX_PCT_CAP", "max")]
for col, (label, c, hk) in zip(st.columns(6), cards):
    col.metric(label, fmt(row[c]), help=lib.HELP[hk])

v_fair, v_val = lib.verdict(row["SURPLUS_FAIR"]), lib.verdict(row["SURPLUS_VALUE"])
badge = "  ·  ⭐ **Max player** (worth ≥ his max)" if row["IS_MAX_PLAYER"] == 1 else ""
st.markdown(
    f"**vs fair market:** {v_fair} ({row['SURPLUS_FAIR']:+.1%} cap)  ·  "
    f"**vs production worth:** {v_val} ({row['SURPLUS_VALUE']:+.1%} cap){badge}"
)
st.caption("Surplus = fair value − pay, so **+ (green) = underpaid bargain**, − (red) = overpaid.")

with st.expander("ℹ️ How to read these numbers"):
    st.markdown(
        "- **Actual** — what he's paid this year (his real, often years-old contract).\n"
        "- **Market** — what a *fresh* deal for his recent play would fetch. Capped, and it "
        "**under-prices true stars**, so a max player can look 'overpaid vs market'.\n"
        "- **Comps** — what *genuinely similar players actually signed for*.\n"
        "- **Production value** — what his play is **worth**, *uncapped* (can exceed the max).\n"
        "- **Fair** — the grading benchmark: the market pays the **lower of worth and the max**, "
        "so stars read *fair*, not falsely overpaid.\n\n"
        "For most players price ≈ worth and everything clusters. For stars, worth ≫ the capped price."
    )

# ── value lines across seasons (explicit colors; Actual thicker, Max dashed) ──
st.subheader("Value across seasons (% of cap)")
long = pdf.melt(id_vars="SEASON", value_vars=lib.CHART_COLS, var_name="metric", value_name="pct_cap")
long["metric"] = long["metric"].map(lib.VALUE_COLS)
order = list(lib.LINE_COLORS)
base = alt.Chart(long).encode(
    x=alt.X("SEASON:N", title=None),
    y=alt.Y("pct_cap:Q", title="% of cap", axis=alt.Axis(format="%")),
    color=alt.Color("metric:N", title=None, scale=alt.Scale(domain=order, range=[lib.LINE_COLORS[m] for m in order])),
    tooltip=["SEASON", "metric", alt.Tooltip("pct_cap:Q", format=".1%")],
)
lines = base.mark_line(point=True).encode(
    strokeDash=alt.condition(alt.datum.metric == "Max", alt.value([5, 4]), alt.value([0])),
    size=alt.condition(alt.datum.metric == "Actual", alt.value(3.5), alt.value(1.8)),
)
st.altair_chart(lines.properties(height=360), width="stretch")
st.caption("Where **production value** (orange) rises above the **max line** (dashed), he's worth "
           "more than the CBA lets a team pay — underpaid even at a max.")

# ── career archetype arc (#9) ──
st.subheader("Career archetype")
arc = alt.Chart(pdf).mark_line(point=alt.OverlayMarkDef(size=90), color="#888").encode(
    x=alt.X("SEASON:N", title=None),
    y=alt.Y("ARCHETYPE_NAME:N", title=None, sort="-x"),
    color=alt.Color("ARCHETYPE_NAME:N", legend=None),
    tooltip=[alt.Tooltip("SEASON:N", title="Season"), alt.Tooltip("ARCHETYPE_NAME:N", title="Archetype"),
             alt.Tooltip("AGE:Q", title="Age")],
).properties(height=max(120, 34 * pdf["ARCHETYPE_NAME"].nunique()))
st.altair_chart(arc, width="stretch")
st.caption("How his role (archetype) shifted season to season.")

# ── why this archetype (#6): top distinguishing role traits ──
why = lib.load_why()
if why is not None:
    w = why[(why["PLAYER_ID"] == pid) & (why["SEASON"] == season)]
    if w.empty:                                   # fall back to the player's most recent clustered season
        wany = why[why["PLAYER_ID"] == pid]
        w = wany[wany["SEASON"] == wany["SEASON"].max()] if not wany.empty else w
    if not w.empty:
        st.subheader(f"Why he's a {row['ARCHETYPE_NAME']}")
        w = w.copy()
        w["label"] = w["feature"].map(lib.role_label)
        bar = alt.Chart(w).mark_bar().encode(
            x=alt.X("z:Q", title="vs league average (standard deviations)"),
            y=alt.Y("label:N", sort="-x", title=None),
            color=alt.condition(alt.datum.z > 0, alt.value("#1f77b4"), alt.value("#c0392b")),
            tooltip=[alt.Tooltip("label:N", title="Trait"), alt.Tooltip("z:Q", title="vs league", format="+.1f")])
        st.altair_chart(bar, width="stretch")
        st.caption("How his playing-style stats compare to the league — the traits that place him "
                   "in this archetype (blue = more than average, red = less).")

# ── SHAP 'why' (precomputed; readable labels) ──
st.subheader("Why the market values him here")
shap = lib.load_shap()
if shap is None:
    st.info("SHAP not exported yet — run `07_export_dashboard_data.ipynb` to enable.")
else:
    srow = shap[(shap["PLAYER_ID"] == pid) & (shap["SEASON"] == season)]
    if srow.empty:
        st.info("No SHAP row for this player-season.")
    else:
        sv = (srow.drop(columns=[c for c in ["PLAYER_ID", "SEASON", "BASE_VALUE"] if c in srow])
                  .iloc[0])
        sv = sv.reindex(sv.abs().sort_values(ascending=False).index).head(10).reset_index()
        sv.columns = ["feature", "shap"]
        sv["feature"] = sv["feature"].map(lib.pretty_feature)
        bar = alt.Chart(sv).mark_bar().encode(
            x=alt.X("shap:Q", title="effect on predicted pay", axis=alt.Axis(format="%")),
            y=alt.Y("feature:N", sort="-x", title=None),
            color=alt.condition(alt.datum.shap > 0, alt.value("#1a7f37"), alt.value("#c0392b")),
            tooltip=[alt.Tooltip("feature:N", title="Factor"), alt.Tooltip("shap:Q", title="effect", format="+.3f")])
        st.altair_chart(bar, width="stretch")
        st.caption("Green pushes his market value up, red down (top 10 factors). "
                   "*(A plain-English summary is planned with the agent build.)*")

# ── comparable signings ──
st.subheader(f"Comparable signings · {season}")
comps_tbl = lib.load_comps()
if comps_tbl is not None:
    c = comps_tbl[(comps_tbl["PLAYER_ID"] == pid) & (comps_tbl["SEASON"] == season)]
    if not c.empty:
        keep = [col for col in ["comp_name", "comp_season", "comp_pct_cap", "comp_vorp", "comp_age",
                                "comp_usg", "distance"] if col in c.columns]
        c2 = c[keep].copy()
        c2["SEASON"] = c2["comp_season"] if "comp_season" in c2.columns else season  # $ uses comp's own season
        disp, cfg = lib.value_table(c2, ["comp_pct_cap"], unit)
        disp = disp.drop(columns="SEASON", errors="ignore")
        st.dataframe(disp, hide_index=True, width="stretch", column_config=cfg)
        st.caption("The actual signings (most-similar first) behind the comps value — with **which "
                   "season** the comp is from and the **VORP / age / usage** that make them similar.")
    else:
        st.info("No comps row for this player-season.")
else:
    comps = lib.find_comps(val, pid, season, k=8)
    if not comps.empty:
        disp, cfg = lib.value_table(
            comps[["PLAYER_NAME", "AGE", "TRAILING_vorp_3Y", "ACTUAL_PCT_CAP",
                   "MARKET_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP"]].assign(SEASON=season),
            ["ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP"], unit, fixed_season=season)
        st.dataframe(disp.drop(columns="SEASON"), hide_index=True, width="stretch", column_config=cfg)
        st.caption("Closest same-archetype peers this season (simplified — export comps for the real kNN list).")

with st.expander("Season-by-season table"):
    base_cols = ["SEASON", "AGE", "ARCHETYPE_NAME", "TRAILING_vorp_3Y"]
    vcols = ["ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "TRUE_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP",
             "MARKET_FAIR_PCT_CAP", "MAX_PCT_CAP", "SURPLUS_FAIR", "SURPLUS_VALUE"]
    disp, cfg = lib.value_table(pdf[base_cols + vcols], vcols, unit)
    st.dataframe(lib.color_surplus(disp, ["SURPLUS_FAIR", "SURPLUS_VALUE"]),
                 hide_index=True, width="stretch", column_config=cfg)
