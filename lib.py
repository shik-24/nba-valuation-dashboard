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
    "MARKET_PCT_CAP": "Market (model)",
    "TRUE_PCT_CAP": "Comps",
    "PRODUCTION_VALUE_PCT_CAP": "Production value",
    "MARKET_FAIR_PCT_CAP": "Fair (cap-aware)",
    "MAX_PCT_CAP": "Max line",
}
# Lines drawn on the player-page chart (kept to 4 for readability).
CHART_COLS = ["ACTUAL_PCT_CAP", "MARKET_PCT_CAP", "PRODUCTION_VALUE_PCT_CAP", "MAX_PCT_CAP"]

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
    "SURPLUS_FAIR": "Pay minus fair value. Negative = underpaid (bargain), positive = overpaid.",
    "SURPLUS_MARKET": "Pay minus the market-model value. Negative = bargain, positive = overpay.",
    "SURPLUS_VALUE": "Pay minus his uncapped production worth. Negative = underpaid vs what he's worth.",
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
    v["SURPLUS_FAIR"] = v["ACTUAL_PCT_CAP"] - v["MARKET_FAIR_PCT_CAP"]
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
        if unit == "$ millions":
            seasons = [fixed_season] * len(df) if fixed_season else df["SEASON"].tolist()
            df[c] = [pct_to_millions(v, s) for v, s in zip(df[c], seasons)]
            cfg[c] = st.column_config.NumberColumn(c, format="$%.1fM", help=COLUMN_HELP.get(c))
        else:
            df[c] = df[c] * 100.0
            cfg[c] = st.column_config.NumberColumn(c, format="%.1f%%", help=COLUMN_HELP.get(c))
    # tooltip-only config for other recognized columns (no reformat)
    for c in df.columns:
        if c not in cfg and c in COLUMN_HELP:
            cfg[c] = st.column_config.Column(c, help=COLUMN_HELP[c])
    return df, cfg


# ─────────────────────────── pure helpers (testable) ───────────────────────────
def latest_season(df: pd.DataFrame) -> str:
    return sorted(df["SEASON"].unique())[-1]


def pct_to_millions(pct: float, season: str) -> float | None:
    cap = SALARY_CAP.get(season)
    return None if cap is None or pd.isna(pct) else round(pct * cap / 1e6, 1)


def verdict(surplus: float) -> str:
    """Label a surplus (actual - fair): <0 underpaid (bargain), >0 overpaid."""
    if surplus <= -0.03:
        return "Bargain"
    if surplus >= 0.03:
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
    """Mean over/underpay by archetype (positive = market overpays the role)."""
    d = val if season is None else val[val["SEASON"] == season]
    g = d.groupby("ARCHETYPE_NAME")
    out = pd.DataFrame({
        "n": g.size(),
        "mean_surplus_market": g["SURPLUS_MARKET"].mean(),
        "mean_surplus_value": g["SURPLUS_VALUE"].mean(),
        "pct_overpaid": g["SURPLUS_MARKET"].apply(lambda s: (s > 0).mean()),
    }).sort_values("mean_surplus_market", ascending=False)
    return out.round(4)
