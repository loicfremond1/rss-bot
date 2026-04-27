# UK Parliament Committee RSS Bot

This repository generates and updates custom RSS feeds for multiple UK Parliament committees.

## Feeds generated

- `feed_hsc.xml` (Health and Social Care)
- `feed_scitech.xml` (Science, Innovation and Technology)
- `feed_treasury.xml` (Treasury)
- `feed_workandpensions.xml` (Work and Pensions)
- `feed_businessandtrade.xml` (Business and Trade)

## Project layout

- `scrape_*.py` — one entry-point per committee feed.
- `scraper_common.py` — shared scraping, parsing, and RSS rendering helpers.
- `.github/workflows/build_*.yml` — one GitHub Actions workflow per feed.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   python -m playwright install --with-deps chromium
   ```

## Run locally

Run any feed scraper directly, for example:

```bash
python scrape_hsc.py
```

Or run all:

```bash
python scrape_hsc.py
python scrape_scitech.py
python scrape_treasury.py
python scrape_workandpensions.py
python scrape_businessandtrade.py
```

## How automation works

Each workflow in `.github/workflows/` runs every 6 hours on a staggered schedule, updates one feed file, rebases onto the latest branch state, and pushes the update.

## Troubleshooting

- If Playwright errors, rerun browser installation:

  ```bash
  python -m playwright install --with-deps chromium
  ```

- If selectors break due to upstream HTML changes, update selectors in the relevant scraper script.
