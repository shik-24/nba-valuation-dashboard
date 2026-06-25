# NBA Valuation Dashboard

Streamlit app over the Stage 5 valuations. Reads compact parquet files from `data/` — no
database or Google Drive dependency, so it runs identically locally and on Streamlit Cloud.

## 1. Get the data

On Colab, run **`../07_export_dashboard_data.ipynb`**. It writes four files to
`data/dashboard/` on Drive. Download them into this folder's `data/`:

```
dashboard/data/player_valuations.parquet
dashboard/data/aging_curves.parquet
dashboard/data/archetype_retention.parquet
dashboard/data/team_lookup.parquet
```

## 2. Run locally

```bash
cd dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501. The sidebar has the four pages: Player Explorer, Archetype
Explorer, Team Cap Efficiency, League Leaderboards.

## 3. Deploy to Streamlit Community Cloud (later)

1. `git init` the project (if not already) and commit — **including `dashboard/data/*.parquet`**
   (a few MB; they travel with the repo so the cloud app can read them).
2. Push to GitHub.
3. On https://share.streamlit.io, point a new app at `dashboard/app.py`. Done — same code, same data.

## Pages

| Page | What it shows |
|------|---------------|
| **Player Explorer** | Actual / market / comps / production-value / max lines across a player's seasons, current-season verdict, closest comps |
| **Archetype Explorer** | Over/underpay, the Stage 4 aging + survival curves, current members |
| **Team Cap Efficiency** | Roster value vs pay, total surplus, best bargains / worst contracts |
| **League Leaderboards** | Sortable bargains/overpays vs market or production value; over/underpay by archetype |

Notes: `%cap` is the unit throughout (dollars shown via the season cap). Rows below
`ACTUAL_FLOOR` (1% of cap — prorated/10-day deals) are filtered from bargain views. Override the
data location with the `NBA_DASH_DATA` env var.
