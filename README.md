# 🏃 Strava to Notion Workout Log Automation

An automated sync engine built in Python that fetches your Strava activities and syncs them into a dedicated **Notion Database** ("Strava Workout Logs"), mapping every activity detail to a distinct Notion property using Metric units.

---

## 🌟 Key Features

- **Detailed Property Mapping**: Every Strava metric is stored in a dedicated database property:
  - 📌 **Activity Name** (Title)
  - 🏃 **Activity Type** (Select: Run, Ride, Swim, Walk, Hike, WeightTraining, Workout, etc.)
  - 📅 **Date** (Date & Time ISO 8601)
  - 📏 **Distance (km)** (Number)
  - ⏱️ **Moving Time** (Rich Text: `HH:MM:SS`) & **Moving Time (min)** (Number)
  - ⌛ **Elapsed Time** (Rich Text: `HH:MM:SS`)
  - ⚡ **Pace (min/km)** (Rich Text for foot sports, e.g. `5:15 /km`)
  - 🚴 **Avg Speed (km/h)** & **Max Speed (km/h)** (Number)
  - ⛰️ **Elevation Gain (m)** (Number)
  - ❤️ **Avg Heart Rate (bpm)** & **Max Heart Rate (bpm)** (Number)
  - 🔥 **Calories (kcal)** (Number)
  - 📈 **Relative Effort** (Number)
  - 🚴 **Commute** & 🏋️ **Trainer** (Checkboxes)
  - 🆔 **Strava ID** (Rich Text - unique deduplication key)
  - 🔗 **Strava Link** (URL direct link)
  - 📍 **Location** (Rich Text)
- **Automatic Database Creation**: If the database doesn't exist, the script automatically creates a formatted "Strava Workout Logs" database inside your designated Notion page.
- **Smart Deduplication**: Queries existing Notion records by `Strava ID` to avoid creating duplicate entries.
- **24/7 Background Automation**: Ready to run automatically on a schedule via **GitHub Actions**.

---

## 🛠️ Setup Instructions

### Step 1: Notion Integration Setup

1. Go to [Notion My Integrations](https://www.notion.so/my-integrations) and click **+ New integration**.
2. Name it (e.g. `Strava Sync Agent`), select your workspace, and save.
3. Copy the **Internal Integration Secret** (this is your `NOTION_API_KEY`).
4. In Notion, navigate to your target page (e.g. **Strava Workouts Dashboard**, ID: `your_notion_parent_page_id`).
5. Click the `...` menu at the top right of the page -> **Connections** / **Add Connection** -> Select your integration (`Strava Sync Agent`).

### Step 2: Strava API Application Setup

1. Go to your [Strava API Settings](https://www.strava.com/settings/api).
2. Create an application if you haven't already:
   - **Category**: Tool / Integration
   - **Authorization Callback Domain**: `localhost`
3. Copy your **Client ID** (`STRAVA_CLIENT_ID`) and **Client Secret** (`STRAVA_CLIENT_SECRET`).

### Step 3: Generate Strava Refresh Token

Run the included setup helper script to authorize your account and retrieve your permanent refresh token:

```bash
python setup_strava_auth.py
```

This will launch a browser window asking you to grant access (`read,activity:read_all`). Once approved, your `STRAVA_REFRESH_TOKEN` will be printed in your terminal.

---

## 🚀 Local Execution

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Fill in your credentials in `.env`:
   ```env
   NOTION_API_KEY=secret_xxx
   NOTION_PAGE_ID=your_notion_parent_page_id
   STRAVA_CLIENT_ID=12345
   STRAVA_CLIENT_SECRET=xxx
   STRAVA_REFRESH_TOKEN=xxx
   ```
3. Install dependencies and run the sync:
   ```bash
   pip install -r requirements.txt
   python strava_sync.py
   ```

---

## 🤖 Continuous Automation via GitHub Actions

To run this sync automatically every 6 hours without hosting a server:

1. Push this repository to GitHub.
2. In your GitHub repository, go to **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
3. Add the following 6 secrets:
   - `NOTION_API_KEY`
   - `NOTION_PAGE_ID`
   - `NOTION_DATABASE_ID` (optional)
   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REFRESH_TOKEN`
4. The workflow in `.github/workflows/strava_sync.yml` will now execute automatically every 6 hours and can also be triggered manually under the **Actions** tab!
