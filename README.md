# ReprobationTool

ReprobationTool is a lightweight web dashboard that visualizes EU and nearby country sentiment on an interactive map. The frontend is a static HTML/CSS/JS app that reads precomputed JSON summaries and presents scores, trend context, and recent coverage highlights per country.

## What the app shows
- **Interactive map** with zoom controls and country selection.
- **Country popups** showing the current score, assessment, and sentiment mix.
- **Latest news** snippets tied to each country’s profile.

## How data gets there (high level)
1. **Ingest** news articles from configured feeds.
2. **Analyze** articles for country mentions and sentiment.
3. **Aggregate** results into per-country JSON summaries consumed by the UI.

## Running the pipeline
The data pipeline is intended to run in sequence: ingest feeds, analyze articles for sentiment, and aggregate country summaries for the UI. Each stage is handled by the backend scripts in the order listed above.

### Rescoring everything with AI
If you need to re-run AI scoring for **all** stored articles, reset the processed fields and cache first, then re-run the normal pipeline. The per-run LLM cap in `process_articles.py` (driven by `GEMINI_DAILY_REQUEST_LIMIT`) still applies, so large backfills may require multiple runs across days.

```bash
python backend/rescore_all.py
python backend/process_articles.py
python backend/score_countries.py
```

## Repository layout
- `index.html`, `styles.css`, `script.js`: frontend map UI and popups.
- `countries/`: per-country JSON outputs consumed by the UI.
- `data/`: data sources and ingested articles.
- `backend/`: ingestion, sentiment scoring, and aggregation scripts.
