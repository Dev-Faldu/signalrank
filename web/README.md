# SignalRank web (glassmorphic, static)

Static site, no build step. The Spark GBT champion is exported to `data/model.json` and scored in the browser (`js/gbt.js`); `data/snapshot.json` holds real scored events.

- Local: `cd web && python -m http.server 8000`
- Refresh data after retraining: `python scripts/export_web.py`
- Deploy to Vercel: `cd web && npx vercel --prod` (framework: Other, no build command, output directory: `.`)
- Parity check: `node -e "..."` against `data/parity_fixtures.json` (max diff 1e-16 vs Spark)
