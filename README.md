# Strava to Notion

### Seamlessly sync your Strava activities and workout logs to a Notion database.

---

## Table of Contents

- [About The Project](#about-the-project)
  - [Key Features](#key-features)
- [Usage](#usage)
- [Setup](#setup)
  - [Step 1: Notion Integration and Page Setup](#step-1-notion-integration-and-page-setup)
  - [Step 2: Strava API Application Setup](#step-2-strava-api-application-setup)
  - [Step 3: Generate Strava Refresh Token](#step-3-generate-strava-refresh-token)
  - [Step 4: Configure GitHub Actions Secrets](#step-4-configure-github-actions-secrets)
  - [Step 5: Local Run (Optional)](#step-5-local-run-optional)
- [Database Properties](#database-properties)
- [Optional Configuration](#optional-configuration)
- [Contributing](#contributing)
- [License](#license)

---

## About The Project

Strava to Notion is an automated sync tool that connects your Strava account to Notion. It fetches your activities (runs, rides, swims, gym workouts, etc.) and logs each one into a formatted Notion database ("Strava Workout Logs"). Every activity metric is mapped into its own dedicated database property using metric units.

### Key Features

- **Automated Background Sync**: Runs automatically every 6 hours via GitHub Actions, or manually at any time via workflow dispatch.
- **Complete Metric Mapping**: Stores over 20 distinct metrics (pace, speed, distance, elevation, heart rate, calories, relative effort, gear, perceived exertion, and description notes).
- **Photo and Heatmap Support**: Extracts activity photos and uses image pixel analysis to extract workout summary cards.
- **Route Map and Reverse Geocoding**: Converts GPS coordinates into readable city and district names using OpenStreetMap Nominatim and attaches map preview images.
- **Automatic Database Creation**: If no database is found, the script automatically creates a formatted "Strava Workout Logs" database inside your parent Notion page.
- **Deduplication**: Matches entries by `Strava ID` to prevent duplicate database rows.

---

## Usage

> Before running the sync, complete the steps in the [Setup](#setup) section below.

Once configured, the automation runs automatically:

- **Automated Runs**: GitHub Actions runs the workflow on schedule every 6 hours (`0 */6 * * *`).
- **Manual Trigger**: Go to your GitHub repository -> **Actions** -> **Strava to Notion Sync** -> **Run workflow**.
- **Local Runs**: Execute `python strava_sync.py` directly from your local terminal.

---

## Setup

### Step 1: Notion Integration and Page Setup

1. Create a Notion parent page where you want your workout database to live (for example, "Workouts Dashboard").
2. Copy the **Page ID** from your browser URL:
   ```text
   Page URL: https://www.notion.so/username/Workouts-Dashboard-3bfb2a0f0d2081909c42e9af1e629747
   Page ID:  3bfb2a0f0d2081909c42e9af1e629747 (or with hyphens: 3bfb2a0f-0d20-8190-9c42-e9af1e629747)
   ```
   This value is your `NOTION_PAGE_ID`.
3. Go to [Notion My Integrations](https://www.notion.so/my-integrations) and click **+ New integration**.
4. Set the name (e.g. `Strava Sync Agent`), select your Notion workspace, and submit.
5. Copy the **Internal Integration Secret** (this is your `NOTION_API_KEY`).
6. In Notion, open your parent page -> click the three dots (`...`) in the top-right corner -> **Connections** (or **Add connection**) -> select your newly created integration.

### Step 2: Strava API Application Setup

1. Log in to Strava and navigate to [Strava API Settings](https://www.strava.com/settings/api).
2. Create an application with the following parameters:
   - **Application Name**: Strava to Notion
   - **Category**: Tool / Integration
   - **Authorization Callback Domain**: `localhost`
3. Copy your **Client ID** (`STRAVA_CLIENT_ID`) and **Client Secret** (`STRAVA_CLIENT_SECRET`).

### Step 3: Generate Strava Refresh Token

1. Clone or download this repository to your local machine:
   ```bash
   git clone https://github.com/bruhhm/strava-to-notion.git
   cd strava-to-notion
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the included authorization helper:
   ```bash
   python setup_strava_auth.py
   ```
4. Enter your `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` when prompted.
5. Your web browser will open requesting permissions (`read,activity:read_all`). Click **Authorize**.
6. Once authorized, the script prints your permanent `STRAVA_REFRESH_TOKEN` to your terminal.

### Step 4: Configure GitHub Actions Secrets

To run the sync automatically via GitHub Actions:

1. Push or fork this repository to your GitHub account.
2. In your repository, navigate to **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
3. Add the following repository secrets:

| Secret Name | Required | Description |
| :--- | :--- | :--- |
| `NOTION_API_KEY` | Yes | Your Notion internal integration token (`ntn_...` or `secret_...`) |
| `NOTION_PAGE_ID` | Yes | 32-character ID of your Notion parent page |
| `NOTION_DATABASE_ID` | No | Direct database ID (leave empty to auto-detect/create) |
| `STRAVA_CLIENT_ID` | Yes | Strava API application Client ID |
| `STRAVA_CLIENT_SECRET` | Yes | Strava API application Client Secret |
| `STRAVA_REFRESH_TOKEN` | Yes | Permanent refresh token from Step 3 |
| `SYNC_START_DATE_CUTOFF` | No | Optional start date filter (format: `YYYY-MM-DD`) |
| `MAPBOX_TOKEN` | No | Optional Mapbox token for route polyline previews |

### Step 5: Local Run (Optional)

You can also run the sync manually on your local computer:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Enter your credentials into `.env`.
3. Run the sync:
   ```bash
   python strava_sync.py
   ```

---

## Database Properties

The sync script creates and maintains the following database schema in Notion:

| Property Name | Property Type | Description |
| :--- | :--- | :--- |
| **Activity Name** | Title | Name of the Strava activity |
| **Activity Type** | Select | Sport type (Run, Ride, Swim, WeightTraining, Workout, Walk, Hike, etc.) |
| **Date** | Date | Activity start timestamp (ISO 8601) |
| **Distance (km)** | Number | Total distance in kilometers |
| **Moving Time** | Rich Text | Moving duration formatted as `HH:MM:SS` |
| **Moving Time (min)** | Number | Moving duration in decimal minutes |
| **Elapsed Time** | Rich Text | Total elapsed duration formatted as `HH:MM:SS` |
| **Pace** | Rich Text | Running pace in `min/km` or cycling speed in `km/h` |
| **Avg Speed (km/h)** | Number | Average speed |
| **Max Speed (km/h)** | Number | Maximum speed recorded |
| **Elevation Gain (m)** | Number | Total elevation gain in meters |
| **Avg Heart Rate (bpm)** | Number | Average heart rate |
| **Max Heart Rate (bpm)** | Number | Maximum recorded heart rate |
| **Calories (kcal)** | Number | Total calories burned |
| **Relative Effort** | Number | Strava suffer score / relative effort |
| **Description** | Rich Text | Activity notes, description, and gym set logs |
| **Gear** | Rich Text | Shoes or bike equipment name |
| **Perceived Exertion** | Number | Self-reported effort rating (1-10) |
| **Photos** | Files | Attached workout summary cards or Strava photos |
| **Place** | Rich Text | Reverse-geocoded location name (e.g. Suburb, City, Country) |
| **Route Map** | Files | Static map preview image of GPS route |
| **Commute** | Checkbox | Whether the activity was marked as commute |
| **Trainer** | Checkbox | Whether the activity was recorded on an indoor trainer |
| **Strava ID** | Rich Text | Unique Strava activity ID (used for deduplication) |
| **Strava Link** | URL | Direct link to the activity on Strava |

---

## Optional Configuration

- **`SYNC_START_DATE_CUTOFF`**: Restricts syncing to activities starting on or after a specified date (`YYYY-MM-DD`). Activities before this date are skipped.
- **`MAPBOX_TOKEN`**: When provided, the tool uses the Mapbox Static Images API to render route polylines. If omitted, the tool falls back to OpenStreetMap tile previews.

---

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the issues page if you want to contribute.

---

## License

Distributed under the MIT License.
