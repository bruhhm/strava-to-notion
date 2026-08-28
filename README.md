# Strava to Notion Workout Log Automation

An automated sync engine built in Python that fetches Strava activities and syncs them into a dedicated Notion Database ("Strava Workout Logs"), mapping activity details to distinct Notion database properties using Metric units.

---

## Key Features

- **Detailed Property Mapping**: Every Strava metric is stored in a dedicated database property:
  - **Activity Name** (Title)
  - **Activity Type** (Select: Run, Ride, Swim, Walk, Hike, WeightTraining, Workout, etc.)
  - **Date** (Date & Time ISO 8601)
  - **Distance (km)** (Number)
  - **Moving Time** (Rich Text: `HH:MM:SS`) and **Moving Time (min)** (Number)
  - **Elapsed Time** (Rich Text: `HH:MM:SS`)
  - **Pace** (Rich Text for foot sports, e.g. `5:15 /km`, or speed for cycling)
  - **Avg Speed (km/h)** and **Max Speed (km/h)** (Number)
  - **Elevation Gain (m)** (Number)
  - **Avg Heart Rate (bpm)** and **Max Heart Rate (bpm)** (Number)
  - **Calories (kcal)** (Number)
  - **Relative Effort** (Number)
  - **Description** (Rich Text - full workout notes and set logs)
  - **Gear** (Rich Text - equipment/shoes used)
  - **Perceived Exertion** (Number - self-reported effort rating)
  - **Photos** (Files & Media - attached activity photos and workout cards)
  - **Place** (Rich Text - reverse-geocoded place name from GPS coordinates via OpenStreetMap)
  - **Route Map** (Files & Media - static route map preview tile)
  - **Commute** and **Trainer** (Checkboxes)
  - **Strava ID** (Rich Text - unique deduplication key)
  - **Strava Link** (URL direct link)
- **Automatic Database Creation**: If the database does not exist, the script automatically creates a formatted "Strava Workout Logs" database inside your designated Notion page.
- **Smart Deduplication**: Queries existing Notion records by `Strava ID` to avoid creating duplicate entries.
- **Background Automation**: Ready to run automatically on a schedule via GitHub Actions.

---

## Setup Instructions

### Step 1: Notion Integration Setup

1. Go to Notion Integrations (https://www.notion.so/my-integrations) and click **+ New integration**.
2. Name it (e.g. `Strava Sync Agent`), select your workspace, and save.
3. Copy the **Internal Integration Secret** (this is your `NOTION_API_KEY`).
4. In Notion, navigate to your target parent page where you want the database to live.
5. Copy the Page ID from the URL (the 32-character string at the end of the page URL). This is your `NOTION_PAGE_ID`.
6. Click the `...` menu at the top right of the page -> **Connections** -> Select your integration (`Strava Sync Agent`).

### Step 2: Strava API Application Setup

1. Go to Strava API Settings (https://www.strava.com/settings/api).
2. Create an application if you have not already:
   - **Category**: Tool / Integration
   - **Authorization Callback Domain**: `localhost`
3. Copy your **Client ID** (`STRAVA_CLIENT_ID`) and **Client Secret** (`STRAVA_CLIENT_SECRET`).

### Step 3: Generate Strava Refresh Token

Run the included setup helper script to authorize your account and retrieve your permanent refresh token:

```bash
python setup_strava_auth.py
```

This will open a browser window asking you to grant access (`read,activity:read_all`). Once approved, your `STRAVA_REFRESH_TOKEN` will be displayed in your terminal.

---

## Local Execution

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Fill in your credentials in `.env`:
   ```env
   NOTION_API_KEY=ntn_xxx
   NOTION_PAGE_ID=your_notion_parent_page_id
   STRAVA_CLIENT_ID=12345
   STRAVA_CLIENT_SECRET=xxx
   STRAVA_REFRESH_TOKEN=xxx
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the sync:
   ```bash
   python strava_sync.py
   ```

---

## Continuous Automation via GitHub Actions

To run this sync automatically every 6 hours without hosting a server:

1. Fork or push this repository to your GitHub account.
2. In your GitHub repository, go to **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
3. Add the following repository secrets:
   - `NOTION_API_KEY`
   - `NOTION_PAGE_ID`
   - `NOTION_DATABASE_ID` (optional, script auto-detects if omitted)
   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REFRESH_TOKEN`
   - `MAPBOX_TOKEN` (optional, for custom map polyline rendering)
   - `SYNC_START_DATE_CUTOFF` (optional, format `YYYY-MM-DD` to only sync activities from a specific date forward)
4. The workflow in `.github/workflows/strava_sync.yml` will execute automatically on schedule every 6 hours, and can also be manually triggered from the **Actions** tab.
