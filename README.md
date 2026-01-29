# ReprobationTool

ReprobationTool is a lightweight web application that visualizes EU member state sentiment on an interactive map. The project pairs a static frontend with scheduled data updates, keeping the interface fast and easy to host.

## Project Overview
- **Frontend:** Static HTML/CSS/JavaScript with an SVG-based EU map and country detail panels.
- **Data:** Per-country JSON files containing scores, trends, and sentiment breakdowns.
- **Automation:** Periodic data refreshes via scheduled jobs that regenerate JSON outputs.

## Repository Layout
- `index.html`, `styles.css`, `script.js`: Frontend application.
- `countries/`: Country-level JSON outputs consumed by the UI.
- `data/`: Supporting data sources and assets.
- `backend/`: Scripts and utilities for generating country scores.

## Notes
This repository focuses on the core UI and data pipeline. Hosting, scheduling, and data sourcing can be configured to fit your deployment environment.
