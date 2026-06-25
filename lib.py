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

# Canonical value columns present in player_valuations (post Stage 5c).
VALUE_COLS = {
    "ACTUAL_PCT_CAP": "Actual",
    "MARKET_PCT_CAP": "Market (XGB)",
    "TRUE_PCT_CAP": "True (comps)",
    "PRODUCTION_VALUE_PCT_CAP": "Production value",
    "MAX_PCT_CAP": "Max line",
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
    return _load("player_valuations")


def load_aging() -> pd.DataFrame:
    return _load("aging_curves")


def load_retention() -> pd.DataFrame:
    return _load("archetype_retention")


def load_team_lookup() -> pd.DataFrame:
    return _load("team_lookup")


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
