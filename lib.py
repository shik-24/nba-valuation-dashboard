"""Shared data loaders + helpers for the NBA valuation dashboard.

Host-agnostic: reads compact parquet files from `dashboard/data/` (override with the
NBA_DASH_DATA env var). The same files work locally and on Streamlit Community Cloud, so
deploying is just `git push` -- no DB or Drive dependency. Pure helpers (no Streamlit calls)
live below the loaders so they can be unit-tested without a running app.
"""
from __future__ import annotations
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = Path(os.environ.get("NBA_DASH_DATA", Path(__file__).parent / "data"))

# Drop prorated / partial-season salary artifacts (10-day, mid-season waivers) from bargain views.
# These sit below the league minimum %cap and would otherwise masquerade as extreme bargains.
ACTUAL_FLOOR = 0.01

# NBA salary cap by season (same dict the notebooks use) -> %cap to $ for readability.
SALARY_CAP = {
    "2015-16":  70_000_000, "2016-17":  94_143_000, "2017-18":  99_093_000,
    "2018-19": 101_869_000, "2019-20": 109_140_000, "2020-21": 109_140_000,
    "2021-22": 112_414_000, "2022-23": 123_655_000, "2023-24": 136_021_000,
    "2024-25": 140_588_000, "2025-26": 154_647_000,
}

# Canonical value columns (post Stage 5c) + the derived cap-aware fair value.
VALUE_COLS = {
    "ACTUAL_PCT_CAP": "Actual",
    "MARKET_PCT_CAP": "Market",
    "TRUE_PCT_CAP": "Comps",
    "PRODUCTION_VALUE_PCT_CAP": "Production value",
    "MARKET_FAIR_PCT_CAP": "Fair",
    "MAX_PCT_CAP": "Max",
}
# Lines drawn on the player-page chart, with explicit colors (label -> hex).
CHART_COLS = ["ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "TRUE_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP", "MAX_PCT_CAP"]
LINE_COLORS = {
    "Actual": "#2e9e3f",            # green, drawn thicker
    "Market": "#1f77b4",            # blue
    "Comps": "#d4a017",             # gold
    "Production value": "#ff7f0e",  # orange
    "Max": "#777777",              # gray, dashed
}

# Human-readable column headers (item: tables/charts shouldn't show variable names).
LABELS = {
    "ACTUAL_PCT_CAP": "Actual", "MARKET_PCT_CAP": "Market", "TRUE_PCT_CAP": "Comps",
    "PRODUCTION_VALUE_PCT_CAP": "Production value", "MARKET_FAIR_PCT_CAP": "Fair", "MAX_PCT_CAP": "Max",
    "SURPLUS_FAIR": "Surplus vs fair", "SURPLUS_MARKET": "Surplus vs market", "SURPLUS_VALUE": "Surplus vs value",
    "TRAILING_vorp_3Y": "Trailing VORP", "ARCHETYPE_NAME": "Archetype", "PLAYER_NAME": "Player",
    "AGE": "Age", "SEASON": "Season", "YEARS_IN_LEAGUE": "Yrs in league", "N_TRAILING": "Seasons of data",
    "comp_name": "Comp player", "comp_pct_cap": "Comp's salary", "comp_season": "Comp's season",
    "distance": "Distance (lower = closer)",
}

# ── Plain-language tooltips (audience: basketball fans, not data scientists) ──
# Widgets (st.metric / st.selectbox / st.radio help=).
HELP = {
    "units": "Show every number as a share of the team salary cap, or as dollars (using that season's cap).",
    "player": "Pick any player. We can value anyone with enough recent playing history.",
    "season": "Which season's salary and roster to show.",
    "team": "Pick a team to see its roster's value versus what it pays.",
    "archetype": "A playing-style group learned from tracking + box-score stats — role, not quality "
                 "(e.g. '3-and-D wing', 'Lead on-ball guard').",
    "value_reference": "Which 'fair pay' yardstick to grade salaries against. Cap-aware fair is the "
                       "default; it pays the lower of a player's worth and his max.",
    "actual": "What he is actually paid this season, as a share of the cap (his real, often older, contract).",
    "market": "What the open market would likely pay him on a NEW deal today — based on his last 3 "
              "seasons, age, and role. It's capped, so it under-rates true superstars.",
    "fair": "Our headline 'what he should make': the market pays the LOWER of his worth and the max, "
            "so stars land at the max here. Compare this to his actual pay.",
    "production_value": "What his on-court play is worth, with NO max ceiling — so an elite player can "
                        "read above the max (e.g. 'worth 50% of the cap').",
    "comps": "What genuinely similar players (same role, similar production and age) actually signed for.",
    "max": "The most he can earn this year under the CBA — 25 / 30 / 35% of the cap by years of service.",
    "is_max_player": "His production is worth at least his max — i.e. a smart team pays him the max.",
    "payroll": "Total of this roster's salaries as a share of the cap (only players we can value).",
    "team_surplus": "Roster value minus what it's paid. Positive = the team gets more value than it pays for.",
}

# Table column tooltips (attached via st.column_config in value_table).
COLUMN_HELP = {
    "ACTUAL_PCT_CAP": HELP["actual"],
    "MARKET_PCT_CAP": HELP["market"],
    "MARKET_FAIR_PCT_CAP": HELP["fair"],
    "TRUE_PCT_CAP": HELP["comps"],
    "PRODUCTION_VALUE_PCT_CAP": HELP["production_value"],
    "MAX_PCT_CAP": HELP["max"],
    "SURPLUS_FAIR": "Fair value minus pay. Positive (green) = underpaid bargain, negative (red) = overpaid.",
    "SURPLUS_MARKET": "Market value minus pay. Positive (green) = bargain, negative (red) = overpay.",
    "SURPLUS_VALUE": "Uncapped production worth minus pay. Positive (green) = paid below what he's worth.",
    "TRAILING_vorp_3Y": "VORP (value over replacement) averaged over his last 3 seasons — total value "
                        "added vs a freely-available player, in one number.",
    "ARCHETYPE_NAME": HELP["archetype"],
    "AGE": "Age during this season.",
    "comp_pct_cap": "What this comparable player signed for (share of cap).",
    "distance": "How similar this comp is — smaller means more similar.",
}


# ─────────────────────────────── loaders ───────────────────────────────
@st.cache_data(show_spinner=False)
def _load(name: str) -> pd.DataFrame:
    pq, csv = DATA_DIR / f"{name}.parquet", DATA_DIR / f"{name}.csv"
    if pq.exists():
        return pd.read_parquet(pq)
    if csv.exists():
        return pd.read_csv(csv)
    raise FileNotFoundError(name)


def data_available() -> bool:
    return all((DATA_DIR / f"{n}.parquet").exists() or (DATA_DIR / f"{n}.csv").exists()
               for n in ("player_valuations", "aging_curves", "archetype_retention", "team_lookup"))


def require_data() -> None:
    """Render a friendly setup message + stop the page if the data files aren't present yet."""
    if not data_available():
        st.error(
            f"Dashboard data not found in `{DATA_DIR}`.\n\n"
            "Run **`07_export_dashboard_data.ipynb`** on Colab to export the compact tables, "
            "download the `data/dashboard/` folder, and drop its files into `dashboard/data/`."
        )
        st.stop()


def load_valuations() -> pd.DataFrame:
    """player_valuations + a derived cap-aware MARKET_FAIR.

    The XGB market model is censored at the max and shrinks extremes toward the mean, so it
    under-prices genuine stars (Jokić → ~0.31, not his real max). A rational market pays the
    LESSER of a player's worth and his max, but never below the model's fresh-market estimate:
        MARKET_FAIR = max(MARKET, min(PRODUCTION_VALUE, MAX))
    -> stars snap up to the max (read 'fair, paid the max'); sub-max players keep the model value.
    """
    v = _load("player_valuations").copy()
    v["MARKET_FAIR_PCT_CAP"] = np.maximum(
        v["MARKET_PCT_CAP"], np.minimum(v["PRODUCTION_VALUE_PCT_CAP"], v["MAX_PCT_CAP"]))
    # Surplus = fair value − actual pay, so a BARGAIN (underpaid) is POSITIVE (shown green),
    # an overpay NEGATIVE (red). Overrides the raw (actual−fair) columns.
    v["SURPLUS_FAIR"] = v["MARKET_FAIR_PCT_CAP"] - v["ACTUAL_PCT_CAP"]
    v["SURPLUS_MARKET"] = v["MARKET_PCT_CAP"] - v["ACTUAL_PCT_CAP"]
    v["SURPLUS_VALUE"] = v["PRODUCTION_VALUE_PCT_CAP"] - v["ACTUAL_PCT_CAP"]
    return v


def load_aging() -> pd.DataFrame:
    return _load("aging_curves")


def load_retention() -> pd.DataFrame:
    return _load("archetype_retention")


def load_team_lookup() -> pd.DataFrame:
    return _load("team_lookup")


def _load_optional(name: str) -> pd.DataFrame | None:
    """Optional enrichment tables (SHAP, comps) — return None if not exported yet."""
    try:
        return _load(name)
    except FileNotFoundError:
        return None


def load_shap() -> pd.DataFrame | None:
    return _load_optional("shap_values")


def load_comps() -> pd.DataFrame | None:
    return _load_optional("player_comps")


# ─────────────────────────── unit toggle ($ / %cap) ───────────────────────────
def unit_toggle():
    return st.sidebar.radio("Units", ["% of cap", "$ millions"], horizontal=True, key="units",
                            help=HELP["units"])


def value_table(df: pd.DataFrame, cols, unit: str, fixed_season: str | None = None):
    """Format %cap value columns for display per the unit toggle, and attach plain-language
    tooltips to every recognized column. Returns (display_df, column_config) for st.dataframe."""
    df = df.copy()
    cfg = {}
    for c in cols:
        if c not in df.columns:
            continue
        label = LABELS.get(c, c)
        if unit == "$ millions":
            seasons = [fixed_season] * len(df) if fixed_season else df["SEASON"].tolist()
            df[c] = [pct_to_millions(v, s) for v, s in zip(df[c], seasons)]
            cfg[c] = st.column_config.NumberColumn(label, format="$%.1fM", help=COLUMN_HELP.get(c))
        else:
            df[c] = df[c] * 100.0
            cfg[c] = st.column_config.NumberColumn(label, format="%.1f%%", help=COLUMN_HELP.get(c))
    # label + tooltip for every other recognized column (no reformat)
    for c in df.columns:
        if c not in cfg and (c in LABELS or c in COLUMN_HELP):
            cfg[c] = st.column_config.Column(LABELS.get(c, c), help=COLUMN_HELP.get(c))
    return df, cfg


_FEAT_LABELS = {
    "TRAILING_vorp_3Y": "Trailing VORP", "TRAILING_bpm_3Y": "Trailing BPM", "TRAILING_USG_PCT_3Y": "Usage %",
    "TRAILING_GAMES_MISSED_3Y": "Games missed", "TRAILING_DEFICIT_REL_3Y": "Availability deficit",
    "TRAILING_AVAIL_3Y": "Availability", "MISSED_SEASONS_3Y": "Missed seasons", "N_TRAILING": "Seasons of data",
    "AGE": "Age", "AGE2": "Age²", "YEARS_IN_LEAGUE": "Yrs in league", "DRAFT_NUMBER": "Draft pick #",
}


def pretty_feature(name: str) -> str:
    """Turn a model feature / SHAP column into a plain-English label."""
    name = name.replace("shap_", "")
    if name.startswith("ARCH_"):
        return "Archetype: " + name[5:]
    return _FEAT_LABELS.get(name, name)


def color_surplus(disp: pd.DataFrame, surplus_cols):
    """Style: surplus columns green when positive (bargain), red when negative (overpay)."""
    cols = [c for c in surplus_cols if c in disp.columns]

    def _c(v):
        if pd.isna(v) or v == 0:
            return ""
        return "color:#1a7f37;font-weight:600" if v > 0 else "color:#c0392b;font-weight:600"

    return disp.style.map(_c, subset=cols) if cols else disp.style


# ─────────────────────────── pure helpers (testable) ───────────────────────────
def latest_season(df: pd.DataFrame) -> str:
    return sorted(df["SEASON"].unique())[-1]


def pct_to_millions(pct: float, season: str) -> float | None:
    cap = SALARY_CAP.get(season)
    return None if cap is None or pd.isna(pct) else round(pct * cap / 1e6, 1)


def verdict(surplus: float) -> str:
    """Label a surplus (fair − actual): >0 underpaid (bargain), <0 overpaid."""
    if surplus >= 0.03:
        return "Bargain"
    if surplus <= -0.03:
        return "Overpay"
    return "Fair"


def with_team(val: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    return val.merge(teams, on=["PLAYER_ID", "SEASON"], how="left")


def find_comps(val: pd.DataFrame, player_id: int, season: str, k: int = 8) -> pd.DataFrame:
    """Nearest same-archetype, same-season players by standardized [trailing VORP, age].
    Excludes every row of the same player. Read-only stand-in for the 5b kNN comps."""
    row = val[(val["PLAYER_ID"] == player_id) & (val["SEASON"] == season)]
    if row.empty:
        return val.iloc[0:0]
    arch = row["ARCHETYPE_NAME"].iloc[0]
    pool = val[(val["SEASON"] == season) & (val["ARCHETYPE_NAME"] == arch)
               & (val["PLAYER_ID"] != player_id)].copy()
    if pool.empty:
        return pool
    feats = ["TRAILING_vorp_3Y", "AGE"]
    mu, sd = pool[feats].mean(), pool[feats].std().replace(0, 1)
    z_pool = (pool[feats] - mu) / sd
    z_row = (row[feats].iloc[0] - mu) / sd
    pool["distance"] = np.sqrt(((z_pool - z_row) ** 2).sum(axis=1))
    return pool.nsmallest(k, "distance")


def archetype_surplus(val: pd.DataFrame, season: str | None = None) -> pd.DataFrame:
    """Mean surplus by archetype (new sign: positive = market underpays the role; negative = a
    'win-now' premium / overpaid). Sorted most-overpaid (premium) first."""
    d = val if season is None else val[val["SEASON"] == season]
    g = d.groupby("ARCHETYPE_NAME")
    out = pd.DataFrame({
        "n": g.size(),
        "mean_surplus_fair": g["SURPLUS_FAIR"].mean(),
        "mean_surplus_value": g["SURPLUS_VALUE"].mean(),
        "pct_underpaid": g["SURPLUS_FAIR"].apply(lambda s: (s > 0).mean()),
    }).sort_values("mean_surplus_fair")
    return out.round(4)
