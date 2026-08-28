"""
Strava to Notion Sync Engine

Fetches Strava activities and syncs them into a Notion database with full
property mapping, GPS reverse-geocoding, route map previews, and photo
filtering for Hevy weight training summaries.

Usage:
    python strava_sync.py

Configuration:
    All credentials and options are read from environment variables.
    See .env.example for the full list of supported variables.
"""

import os
import sys
import time
import math
import io
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration (all values come from environment variables)
# ---------------------------------------------------------------------------
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

NOTION_VERSION = "2022-06-28"

# Optional date cutoff. When set (YYYY-MM-DD), only activities on or after
# this date are synced. When empty, all activities from the past 365 days
# are fetched.
SYNC_START_DATE_CUTOFF = os.getenv("SYNC_START_DATE_CUTOFF", "").strip()

# ---------------------------------------------------------------------------
# Notion helpers
# ---------------------------------------------------------------------------

def get_notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def find_existing_database():
    """Search Notion workspace for an existing 'Strava Workout Logs' database."""
    url = "https://api.notion.com/v1/search"
    payload = {
        "query": "Strava Workout Logs",
        "filter": {"value": "database", "property": "object"},
    }
    res = requests.post(url, headers=get_notion_headers(), json=payload)
    if res.status_code == 200:
        for item in res.json().get("results", []):
            if item.get("in_trash") or item.get("archived"):
                continue
            title_text = "".join(
                t.get("plain_text", "") for t in item.get("title", [])
            )
            if title_text == "Strava Workout Logs":
                return item["id"]
    return None


def ensure_database_schema(database_id):
    """Ensure the Notion database has all required properties."""
    url = f"https://api.notion.com/v1/databases/{database_id}"
    payload = {
        "properties": {
            "Description": {"rich_text": {}},
            "Gear": {"rich_text": {}},
            "Perceived Exertion": {"number": {"format": "number"}},
            "Photos": {"files": {}},
            "Place": {"rich_text": {}},
            "Route Map": {"files": {}},
        }
    }
    requests.patch(url, headers=get_notion_headers(), json=payload)


def create_notion_database(parent_page_id):
    """Create the 'Strava Workout Logs' database inside the parent page."""
    print(f"[+] Creating 'Strava Workout Logs' database in Notion...")
    url = "https://api.notion.com/v1/databases"
    clean_page_id = parent_page_id.replace("-", "")

    properties_schema = {
        "Activity Name": {"title": {}},
        "Activity Type": {
            "select": {
                "options": [
                    {"name": "Run", "color": "orange"},
                    {"name": "Ride", "color": "blue"},
                    {"name": "Swim", "color": "blue"},
                    {"name": "Walk", "color": "green"},
                    {"name": "Hike", "color": "brown"},
                    {"name": "WeightTraining", "color": "purple"},
                    {"name": "Workout", "color": "red"},
                    {"name": "VirtualRide", "color": "yellow"},
                    {"name": "VirtualRun", "color": "pink"},
                    {"name": "AlpineSki", "color": "gray"},
                    {"name": "Rowing", "color": "blue"},
                    {"name": "Yoga", "color": "purple"},
                ]
            }
        },
        "Date": {"date": {}},
        "Distance (km)": {"number": {"format": "number"}},
        "Moving Time": {"rich_text": {}},
        "Moving Time (min)": {"number": {"format": "number"}},
        "Elapsed Time": {"rich_text": {}},
        "Pace": {"rich_text": {}},
        "Avg Speed (km/h)": {"number": {"format": "number"}},
        "Max Speed (km/h)": {"number": {"format": "number"}},
        "Elevation Gain (m)": {"number": {"format": "number"}},
        "Avg Heart Rate (bpm)": {"number": {"format": "number"}},
        "Max Heart Rate (bpm)": {"number": {"format": "number"}},
        "Calories (kcal)": {"number": {"format": "number"}},
        "Relative Effort": {"number": {"format": "number"}},
        "Commute": {"checkbox": {}},
        "Trainer": {"checkbox": {}},
        "Strava ID": {"rich_text": {}},
        "Strava Link": {"url": {}},
        "Place": {"rich_text": {}},
        "Route Map": {"files": {}},
        "Description": {"rich_text": {}},
        "Gear": {"rich_text": {}},
        "Perceived Exertion": {"number": {"format": "number"}},
        "Photos": {"files": {}},
    }

    payload = {
        "parent": {"type": "page_id", "page_id": clean_page_id},
        "title": [{"type": "text", "text": {"content": "Strava Workout Logs"}}],
        "properties": properties_schema,
    }

    res = requests.post(url, headers=get_notion_headers(), json=payload)
    if res.status_code != 200:
        print(f"[-] Failed to create Notion database: {res.status_code} - {res.text}")
        sys.exit(1)

    db_id = res.json()["id"]
    print(f"[+] Notion database created successfully! ID: {db_id}")
    return db_id


def get_existing_strava_records(database_id):
    """Map existing Strava Activity IDs to Notion page IDs and metadata."""
    print("[+] Querying Notion database for existing activity records...")
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    existing_map = {}
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res = requests.post(url, headers=get_notion_headers(), json=payload)
        if res.status_code != 200:
            print(f"[-] Error querying database: {res.status_code} - {res.text}")
            break

        data = res.json()
        for page in data.get("results", []):
            page_id = page["id"]
            props = page.get("properties", {})
            cover = page.get("cover")
            strava_id_prop = props.get("Strava ID", {}).get("rich_text", [])
            photos_prop = props.get("Photos", {}).get("files", [])
            place_prop = props.get("Place", {}).get("rich_text", [])
            route_map_prop = props.get("Route Map", {}).get("files", [])

            has_valid_route_map = False
            if route_map_prop:
                file_url = route_map_prop[0].get("external", {}).get("url", "")
                if "tile.openstreetmap.org" in file_url or "mapbox.com" in file_url:
                    has_valid_route_map = True

            if strava_id_prop:
                strava_id = strava_id_prop[0].get("plain_text", "").strip()
                desc_prop = props.get("Description", {}).get("rich_text", [])
                desc_text = (
                    desc_prop[0].get("plain_text", "").strip() if desc_prop else ""
                )
                existing_map[strava_id] = {
                    "page_id": page_id,
                    "has_description": bool(desc_text),
                    "has_cover": cover is not None,
                    "has_photos": bool(photos_prop),
                    "photos_count": len(photos_prop),
                    "has_place": bool(
                        place_prop and place_prop[0].get("plain_text", "").strip()
                    ),
                    "has_route_map": has_valid_route_map,
                }

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    print(f"[+] Found {len(existing_map)} existing activity records in Notion.")
    return existing_map


def replace_page_children(page_id, new_children_blocks=None):
    """Clear all child blocks of a Notion page, then optionally append new ones."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    res = requests.get(url, headers=get_notion_headers())
    if res.status_code == 200:
        for block in res.json().get("results", []):
            requests.delete(
                f"https://api.notion.com/v1/blocks/{block['id']}",
                headers=get_notion_headers(),
            )

    if new_children_blocks:
        requests.patch(
            url,
            headers=get_notion_headers(),
            json={"children": new_children_blocks},
        )


# ---------------------------------------------------------------------------
# Strava helpers
# ---------------------------------------------------------------------------

def get_strava_access_token():
    """Refresh and return a valid Strava access token."""
    print("[+] Refreshing Strava access token...")
    res = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "refresh_token": STRAVA_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    if res.status_code != 200:
        print(f"[-] Failed to refresh Strava token: {res.status_code} - {res.text}")
        sys.exit(1)
    print("[+] Strava access token refreshed successfully.")
    return res.json()["access_token"]


def fetch_strava_activities(access_token):
    """Fetch the activity list from Strava, respecting the optional date cutoff."""
    if SYNC_START_DATE_CUTOFF:
        print(f"[+] Fetching Strava activities starting from {SYNC_START_DATE_CUTOFF}...")
        cutoff_dt = datetime.strptime(SYNC_START_DATE_CUTOFF, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    else:
        print("[+] Fetching Strava activities from the last 365 days...")
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=365)

    after_timestamp = int(cutoff_dt.timestamp())
    url = (
        f"https://www.strava.com/api/v3/athlete/activities"
        f"?after={after_timestamp}&per_page=200"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"[-] Failed to fetch Strava activities: {res.status_code} - {res.text}")
        sys.exit(1)

    activities = res.json()

    # Apply strict date filter when a cutoff is configured
    if SYNC_START_DATE_CUTOFF:
        activities = [
            a
            for a in activities
            if a.get("start_date_local", a.get("start_date", ""))[:10]
            >= SYNC_START_DATE_CUTOFF
        ]

    print(f"[+] Found {len(activities)} activities.")
    return activities


def fetch_strava_activity_detail(access_token, activity_id):
    """Fetch full detailed activity from Strava (includes description, gear, etc.)."""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else None


def is_hevy_heatmap_card(url_str):
    """Detect Hevy Muscle Heatmap Summary Cards via pixel analysis.

    Hevy attaches two images to weight training activities synced to Strava:
    one is a muscle heatmap card (gray body silhouette + blue muscle highlights),
    the other is a fun-fact comparison graphic. This function identifies the
    heatmap card by sampling pixel colors in the center-right region of the image.
    """
    try:
        img_data = requests.get(url_str, timeout=10).content
        img = Image.open(io.BytesIO(img_data))
        w, h = img.size
        gray_count = 0
        blue_count = 0
        for x in range(int(w * 0.45), int(w * 0.95)):
            for y in range(int(h * 0.15), int(h * 0.85)):
                r, g, b = img.getpixel((x, y))[:3]
                # Gray body silhouette pixels
                if abs(r - g) <= 8 and abs(g - b) <= 8 and 140 <= r <= 230:
                    gray_count += 1
                # Blue muscle highlight pixels
                if b > 140 and b > r + 30 and g > 90:
                    blue_count += 1
        return gray_count > 5000 and blue_count > 3000
    except Exception:
        return True  # Keep photo on inspection failure


def fetch_strava_activity_photos(access_token, activity_id, is_weight_training=False):
    """Fetch photo URLs for an activity. Filters for heatmap cards on gym workouts."""
    url = (
        f"https://www.strava.com/api/v3/activities/{activity_id}"
        f"/photos?size=600&photo_sources=true"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return []

    urls = []
    for photo in res.json():
        photo_url = (
            photo.get("urls", {}).get("600")
            or photo.get("urls", {}).get("100")
            or photo.get("image_url")
        )
        if not photo_url:
            continue
        if is_weight_training:
            if is_hevy_heatmap_card(photo_url):
                urls.append(photo_url)
        else:
            urls.append(photo_url)
    return urls


# ---------------------------------------------------------------------------
# Geocoding & mapping helpers
# ---------------------------------------------------------------------------

def reverse_geocode(lat, lng):
    """Convert GPS coordinates into a human-readable place name via OpenStreetMap."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json"
        res = requests.get(
            url, headers={"User-Agent": "StravaNotionSync/1.0"}, timeout=5
        )
        if res.status_code == 200:
            addr = res.json().get("address", {})
            suburb = (
                addr.get("suburb")
                or addr.get("neighbourhood")
                or addr.get("quarter")
                or ""
            )
            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("municipality")
                or addr.get("county")
                or ""
            )
            country = addr.get("country") or ""
            parts = [p for p in [suburb, city, country] if p]
            return ", ".join(parts) if parts else res.json().get("display_name", "")
    except Exception as e:
        print(f"[-] Reverse geocoding warning: {e}")
    return ""


def generate_static_map_url(lat, lng, polyline_str=""):
    """Generate a static map image URL for the activity's GPS location."""
    if not lat or not lng:
        return None

    if MAPBOX_TOKEN and polyline_str:
        enc_poly = urllib.parse.quote(polyline_str)
        return (
            f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v11/static/"
            f"path-4+ff5500-1({enc_poly})/auto/600x300"
            f"?access_token={MAPBOX_TOKEN}"
        )

    # Fallback: OpenStreetMap tile
    zoom = 14
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lng + 180.0) / 360.0 * n)
    ytile = int(
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )
    return f"https://tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_seconds(seconds):
    """Format seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def calculate_pace(avg_speed_kph, sport_type):
    """Calculate pace (min/km) for foot sports, or speed for others."""
    foot_sports = {"run", "trailrun", "walk", "hike", "virtualrun"}
    if sport_type.lower() in foot_sports and avg_speed_kph > 0:
        pace_seconds = 3600.0 / avg_speed_kph
        return f"{int(pace_seconds // 60)}:{int(pace_seconds % 60):02d} /km"
    elif avg_speed_kph > 0:
        return f"{avg_speed_kph:.1f} km/h"
    return "N/A"


def truncate_text(text, max_len=1990):
    """Truncate text to fit within Notion's rich text limit."""
    if not text:
        return ""
    return text[:max_len] if len(text) > max_len else text


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def save_activity_to_notion(database_id, activity_detail, access_token, existing_page_id=None):
    """Create or update a Notion page for the given Strava activity."""
    strava_id_str = str(activity_detail["id"])
    name = activity_detail.get("name", "Untitled Workout")
    sport_type = activity_detail.get("sport_type") or activity_detail.get("type", "Workout")
    start_date_utc = activity_detail.get("start_date")

    distance_km = round(activity_detail.get("distance", 0) / 1000.0, 2)
    moving_time_sec = activity_detail.get("moving_time", 0)
    elapsed_time_sec = activity_detail.get("elapsed_time", 0)
    moving_time_min = round(moving_time_sec / 60.0, 1)

    avg_speed_kph = round(activity_detail.get("average_speed", 0) * 3.6, 2)
    max_speed_kph = round(activity_detail.get("max_speed", 0) * 3.6, 2)
    elevation_gain = round(activity_detail.get("total_elevation_gain", 0), 1)
    pace_str = calculate_pace(avg_speed_kph, sport_type)

    avg_hr = (
        round(activity_detail["average_heartrate"], 1)
        if activity_detail.get("has_heartrate")
        else None
    )
    max_hr = (
        round(activity_detail["max_heartrate"], 1)
        if activity_detail.get("has_heartrate")
        else None
    )

    calories = activity_detail.get("calories")
    if calories is None and "kilojoules" in activity_detail:
        calories = round(activity_detail["kilojoules"] / 4.184)
    if calories is not None:
        calories = round(calories)

    suffer_score = activity_detail.get("suffer_score") or activity_detail.get("suf_score")

    # Reverse-geocode GPS coordinates
    place_str = ""
    start_latlng = activity_detail.get("start_latlng")
    summary_polyline = activity_detail.get("map", {}).get("summary_polyline", "")

    if start_latlng and isinstance(start_latlng, list) and len(start_latlng) == 2:
        lat, lng = start_latlng
        place_str = reverse_geocode(lat, lng)
        route_map_url = generate_static_map_url(lat, lng, summary_polyline)
    else:
        route_map_url = None
        loc_parts = [
            p
            for p in [
                activity_detail.get("location_city"),
                activity_detail.get("location_state"),
                activity_detail.get("location_country"),
            ]
            if p
        ]
        place_str = ", ".join(loc_parts) if loc_parts else ""

    strava_link = f"https://www.strava.com/activities/{strava_id_str}"
    description_text = truncate_text(activity_detail.get("description", ""))
    gear_info = activity_detail.get("gear")
    gear_name = gear_info.get("name") if isinstance(gear_info, dict) else None
    perceived_exertion = activity_detail.get("perceived_exertion")

    is_weight_training = sport_type in ("WeightTraining", "Workout")
    photo_urls = fetch_strava_activity_photos(
        access_token, strava_id_str, is_weight_training=is_weight_training
    )

    # Build Notion properties payload
    properties = {
        "Activity Name": {"title": [{"text": {"content": name}}]},
        "Activity Type": {"select": {"name": sport_type}},
        "Date": {"date": {"start": start_date_utc}},
        "Distance (km)": {"number": distance_km},
        "Moving Time": {"rich_text": [{"text": {"content": format_seconds(moving_time_sec)}}]},
        "Moving Time (min)": {"number": moving_time_min},
        "Elapsed Time": {"rich_text": [{"text": {"content": format_seconds(elapsed_time_sec)}}]},
        "Pace": {"rich_text": [{"text": {"content": pace_str}}]},
        "Avg Speed (km/h)": {"number": avg_speed_kph},
        "Max Speed (km/h)": {"number": max_speed_kph},
        "Elevation Gain (m)": {"number": elevation_gain},
        "Commute": {"checkbox": bool(activity_detail.get("commute", False))},
        "Trainer": {"checkbox": bool(activity_detail.get("trainer", False))},
        "Strava ID": {"rich_text": [{"text": {"content": strava_id_str}}]},
        "Strava Link": {"url": strava_link},
    }

    if avg_hr is not None:
        properties["Avg Heart Rate (bpm)"] = {"number": avg_hr}
    if max_hr is not None:
        properties["Max Heart Rate (bpm)"] = {"number": max_hr}
    if calories is not None:
        properties["Calories (kcal)"] = {"number": calories}
    if suffer_score is not None:
        properties["Relative Effort"] = {"number": suffer_score}
    if place_str:
        properties["Place"] = {"rich_text": [{"text": {"content": place_str}}]}
    if route_map_url:
        properties["Route Map"] = {
            "files": [
                {
                    "name": "Route Map Preview",
                    "type": "external",
                    "external": {"url": route_map_url},
                }
            ]
        }
    if description_text:
        properties["Description"] = {
            "rich_text": [{"text": {"content": description_text}}]
        }
    if gear_name:
        properties["Gear"] = {"rich_text": [{"text": {"content": gear_name}}]}
    if perceived_exertion is not None:
        properties["Perceived Exertion"] = {
            "number": round(float(perceived_exertion), 1)
        }

    properties["Photos"] = {
        "files": [
            {
                "name": (
                    f"Workout Photo {i + 1}"
                    if is_weight_training
                    else f"Strava Photo {i + 1}"
                ),
                "type": "external",
                "external": {"url": url},
            }
            for i, url in enumerate(photo_urls)
        ]
    }

    if existing_page_id:
        url = f"https://api.notion.com/v1/pages/{existing_page_id}"
        res = requests.patch(
            url,
            headers=get_notion_headers(),
            json={"properties": properties, "cover": None},
        )
        if res.status_code != 200:
            print(
                f"[-] Failed to update '{name}' (ID: {strava_id_str}): "
                f"{res.status_code} - {res.text}"
            )
            return False
        replace_page_children(existing_page_id, new_children_blocks=[])
        return True
    else:
        url = "https://api.notion.com/v1/pages"
        res = requests.post(
            url,
            headers=get_notion_headers(),
            json={"parent": {"database_id": database_id}, "properties": properties},
        )
        if res.status_code != 200:
            print(
                f"[-] Failed to add '{name}' (ID: {strava_id_str}): "
                f"{res.status_code} - {res.text}"
            )
            return False
        return True


def sync(force_resync_description=False):
    """Main sync entry point."""
    print("=" * 60)
    print(" Strava to Notion Sync Automation ")
    print("=" * 60)

    if not NOTION_API_KEY:
        print("[-] Error: NOTION_API_KEY environment variable is missing.")
        sys.exit(1)
    if not all([STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN]):
        print(
            "[-] Error: Strava API credentials "
            "(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) are missing."
        )
        sys.exit(1)

    # 1. Resolve or create database
    db_id = NOTION_DATABASE_ID
    if not db_id:
        db_id = find_existing_database()
        if db_id:
            print(f"[+] Auto-detected existing database: {db_id}")
        else:
            if not NOTION_PAGE_ID:
                print(
                    "[-] Error: NOTION_PAGE_ID is required for database creation."
                )
                sys.exit(1)
            db_id = create_notion_database(NOTION_PAGE_ID)

    ensure_database_schema(db_id)

    # 2. Fetch activities from Strava
    access_token = get_strava_access_token()
    activities_summary = fetch_strava_activities(access_token)

    # 3. Build deduplication map from existing Notion records
    existing_map = get_existing_strava_records(db_id)

    # 4. Sync activities (oldest first)
    synced_count = 0
    updated_count = 0
    skipped_count = 0

    for summary in reversed(activities_summary):
        act_id = summary["id"]
        act_id_str = str(act_id)
        act_name = summary.get("name", "Workout")
        sport_type = summary.get("sport_type") or summary.get("type", "Workout")

        existing_record = existing_map.get(act_id_str)
        is_weight_training = sport_type in ("WeightTraining", "Workout")

        if (
            not force_resync_description
            and existing_record
            and existing_record["has_description"]
        ):
            if is_weight_training and existing_record["photos_count"] > 1:
                pass  # Re-sync to apply photo filter
            elif not is_weight_training and existing_record["has_route_map"]:
                skipped_count += 1
                continue
            elif is_weight_training:
                skipped_count += 1
                continue

        act_detail = fetch_strava_activity_detail(access_token, act_id)
        if not act_detail:
            act_detail = summary

        if existing_record:
            print(f"[+] Updating: '{act_name}' (ID: {act_id_str})")
            if save_activity_to_notion(
                db_id,
                act_detail,
                access_token,
                existing_page_id=existing_record["page_id"],
            ):
                updated_count += 1
        else:
            print(
                f"[+] Syncing new: '{act_name}' "
                f"(ID: {act_id_str}, Date: {summary.get('start_date')})"
            )
            if save_activity_to_notion(db_id, act_detail, access_token):
                synced_count += 1

        time.sleep(0.4)  # Rate limiting for Strava & Notion APIs

    print()
    print("=" * 60)
    print("[+] SYNC COMPLETED SUCCESSFULLY!")
    print(f"    - New Workouts Added: {synced_count}")
    print(f"    - Existing Workouts Updated: {updated_count}")
    print(f"    - Already Up-to-Date: {skipped_count}")
    print("=" * 60)


if __name__ == "__main__":
    sync(force_resync_description=False)
