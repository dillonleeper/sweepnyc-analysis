# Trick-or-Streets Router

A fun spinoff of the SweepNYC project, reusing the same "pull real NYC geodata and route it" technique for something less serious: planning a walkable trick-or-treating route for NYC DOT's annual **Trick-or-Streets** car-free Halloween event series.

**Live tool:** https://claude.ai/artifact/NkANdN4gkJiBFz8epXQKhz

## What it does

Pick a night in October and a borough, click the map to set your starting point, and it builds a walking route through the Trick-or-Streets locations within your chosen walk radius (nearest-neighbor ordering), with straight-line mileage and an estimated walking time.

## Data

- `data/tos_2026_raw.json` — all 151 2026 Trick-or-Streets locations (name, cross streets, borough, date, hours, host, lat/lon), pulled directly from the Esri ArcGIS FeatureServer that powers DOT's own interactive map (`TrickOrStreet_Point_View`), not scraped or geocoded.
- `data/tos_2026_trimmed.json` — same data, re-keyed with short field names and a sortable date field.
- `data/boro_compact.json` — simplified NYC borough land-boundary outlines (NYC Open Data, "Borough Boundaries," dataset `gthc-hcne`), trimmed to the landmasses large enough to matter, used purely as a visual backdrop on the map.

## File

- `trick-or-streets-router.html` — the full, self-contained page (same content as the published artifact above). Open it directly in a browser.

## How it differs from the SweepNYC analysis

SweepNYC geocodes OATH/sanitation records against CSCL street segments because the city doesn't publish exact coordinates for that data. This project didn't need that step — DOT's own Trick-or-Streets map already ships exact lat/lon per location through its public FeatureServer, so this is a much shorter pipeline: fetch → trim → route → render.
