# Qode — Market Intelligence from X/Twitter

Real-time market intelligence for Indian equities: scrapes tweets under
`#nifty50`, `#sensex`, `#intraday`, `#banknifty` (and related tags), stores
them in partitioned Parquet, and converts the text into quantitative trading
signals (sentiment, lexicon, TF-IDF) aggregated per ticker and 15-minute IST
window with bootstrap confidence intervals — all without any paid APIs or
the official Twitter API.

## Architecture

```
 collectors/          storage/            signals/           viz/
 ┌────────────────┐   ┌──────────────┐   ┌───────────────┐   ┌───────────────┐
 │ playwright_graphql├─▶│ Parquet      ├──▶│ TF-IDF        ├──▶│ streaming     │
 │ cookie_replay     │  │ (partitioned │   │ lexicon       │   │ matplotlib    │
 │ fixture (default) │  │  by IST      │   │ VADER         │   │ charts        │
 └────────────────┘   │  date/hour)  │   │ composite+CI  │   └───────────────┘
        │              └──────────────┘   └───────────────┘
        ▼                     ▲                    │
 processing/ (clean/validate) ┘                    ▼
                                            data/sample/ + reports/
```

The CLI (`market-intel scrape|process|analyze|visualize|run-all`) wires
these stages together — see
[`src/market_intel/cli.py`](src/market_intel/cli.py). Full design rationale
is in [`docs/APPROACH.md`](docs/APPROACH.md).

## See it without running anything

This repo ships with committed sample output from a real 2,200-tweet
pipeline run, so you can browse results directly:

- [`reports/signal_timeline.png`](reports/signal_timeline.png) — composite
  trading signal per ticker over time with bootstrap 95% CI bands
- [`reports/volume_over_time.png`](reports/volume_over_time.png),
  [`reports/top_hashtags.png`](reports/top_hashtags.png),
  [`reports/engagement_distribution.png`](reports/engagement_distribution.png)
- [`data/sample/signals.parquet`](data/sample/signals.parquet) — the
  aggregated signals behind those charts
- [`docs/benchmark_report.txt`](docs/benchmark_report.txt) — measured
  throughput/memory per pipeline stage
- [`docs/APPROACH.md`](docs/APPROACH.md) — full design write-up and
  trade-offs

## How to run it

### Prerequisites

- Python 3.11+ (developed/tested on 3.12)
- No X/Twitter account needed to run the demo below — one is only required
  to collect *live* data.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # leave X_AUTH_TOKEN/X_CT0 blank to use the fixture backend
```

### Run the full demo (no X account needed)

The default backend (`collection.backend: fixture` in
`config/settings.yaml`) generates synthetic-but-realistic tweets shaped
exactly like real X GraphQL responses (see `docs/APPROACH.md` §2), so the
full pipeline runs end to end with zero external dependencies:

```bash
market-intel run-all --min-tweets 2200
```

This runs `scrape → process → analyze → visualize` and writes:
- `data/raw/` — partitioned Parquet tweet store (gitignored, regenerated each run)
- `data/sample/signals.parquet` — aggregated composite signals
- `reports/*.png` — volume, signal timeline with CI bands, top hashtags, engagement distribution

Or run each stage individually:

```bash
market-intel scrape --min-tweets 2200   # collect and write to data/raw/
market-intel process                    # clean/normalize/validate, idempotent
market-intel analyze                    # signal pipeline -> data/sample/signals.parquet
market-intel visualize                  # charts -> reports/
```

### Run against live X

This requires an authenticated X session and is **not exercised in CI or in
this repo's committed sample data** — see `docs/APPROACH.md` §2 and §11 for
why.

1. Log into x.com in a normal browser with the account you want to scrape from.
2. DevTools → Application → Cookies → `x.com` → copy the `auth_token` and `ct0` values.
3. Put them in `.env` (never commit this file):
   ```
   X_AUTH_TOKEN=...
   X_CT0=...
   ```
4. In `config/settings.yaml`, set `collection.backend: playwright_graphql`
   (or `cookie_replay` for the lighter HTTP-only fallback).
5. Install Playwright's browser binary once: `playwright install chromium`
6. Run `market-intel scrape --min-tweets 2000` as usual.

Respect the per-account pacing in `anti_bot.requests_per_account_per_day` —
this is what keeps a single account under X's informal rate ceiling.

### Run the tests

```bash
pytest tests/ -v
```

34 tests: unit coverage for the GraphQL parser, cleaning/Unicode handling,
dedup (exact + near-duplicate), core data structures (Bloom filter, Welford
stats, top-k, ring buffer), and signal math (lexicon, sentiment, ticker
mapping, bootstrap CI); one integration test runs the fixture-driven
pipeline end to end (collect → store → idempotent re-write → signals →
charts). **No test or CI job ever contacts live X.**

## Configuration

All non-secret settings live in [`config/settings.yaml`](config/settings.yaml):
hashtags, collection backend/targets, anti-bot pacing, storage paths/
partitioning, signal-generation parameters (time bucket size, ticker map,
market hours), visualization output. Secrets (`X_AUTH_TOKEN`, `X_CT0`) come
only from the environment/`.env`, never from YAML — see `.env.example`.

## Design decisions and trade-offs

See [`docs/APPROACH.md`](docs/APPROACH.md) for the full write-up: why
Playwright+GraphQL interception over Selenium/DOM scraping, the storage
schema and partitioning rationale, data-structure choices with complexity
notes, the text-to-signal methodology, and Indian-market grounding (ticker
mapping, NSE/BSE hours).

## Scalability (10x)

Summarized in `docs/APPROACH.md` §10: config-driven multi-account worker
pools for collection (the real bottleneck at scale), a documented
`set → BloomFilter` dedup upgrade, `ProcessPoolExecutor`-based parallel
feature computation, and storage/visualization that are already
partitioned/streamed and therefore volume-independent by design.

## Known limitations

- X's internal GraphQL shape and query IDs drift over time and need periodic
  maintenance (see `docs/APPROACH.md` §11).
- This execution environment has no browser/display and no X account, so the
  committed sample data comes from the fixture backend, not a live scrape —
  the live path is fully implemented and documented above but untested here.
- Near-duplicate detection is exact-after-normalization, not fuzzy.
