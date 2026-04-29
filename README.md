# Strava Club Leaderboard Scraper

Scrapes member activity data from a private Strava club and generates leaderboards for the most active cyclists, runners, and swimmers.

Since Strava doesn't expose a public API for club member statistics, this tool logs into Strava using your credentials, navigates each member's profile via [Playwright](https://playwright.dev/python/), and stores the results locally in a JSON database ([TinyDB](https://tinydb.readthedocs.io/)).

## How it works

1. **`main.py`** — logs into Strava, iterates through all club members, and scrapes yearly activity stats (distance, duration, elevation) for cycling, running, and swimming. Data is saved to `./db/strava-leaderboard-{year}-{club_id}.json`.
2. **`post_processing.py`** — reads the database and prints ranked leaderboards for the top 10 members per category.

## Setup

**1. Install dependencies**

```bash
uv sync
uv run playwright install chromium
```

**2. Configure credentials**

Copy `.env.example` to `.env` and fill in your Strava login:

```bash
cp .env.example .env
```

```env
STRAVA_EMAIL=you@example.com
STRAVA_PASSWORD=yourpassword
```

**3. Set your club ID and year**

Edit the bottom of `main.py`:

```python
CLUB_ID = "285486"  # your Strava club ID
YEAR = 2025
```

## Usage

```bash
# Scrape member data (opens a browser window)
uv run main.py

# Print leaderboards from the scraped data
uv run post_processing.py
```

## Example output

```
parsed 42 members

🕓 Most active member:
1. Jane Doe - 123 hours 12 minutes

🚴 Most active cyclists
1. Jane Doe - 1234.1 Km - 12500hm

🏃 Most active runner
1. John Smith - 456.2 Km - 3200hm

🏊 Most active swimmer
1. Alice Brown - 24000 meter
```

## Notes

- The scraper runs with a visible browser (`headless=False`) so you can monitor progress and handle any login prompts.
- Private Strava accounts are skipped automatically. The scraper will send a follow request if the account is private.
- Data is upserted on each run, so re-running is safe and will update existing entries.

## Todo

- [ ] Deduplicate and clean up scraping code
- [ ] Refactor `post_processing.py`
- [ ] Fix swimming distance display for values above 999,999m
