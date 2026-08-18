import os
import sys
import time
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

NOTION_VERSION = "2022-06-28"

def get_notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def get_strava_access_token():
    print("[+] Refreshing Strava access token...")
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    res = requests.post(url, data=payload)
    if res.status_code != 200:
        print(f"[-] Failed to refresh Strava token: {res.status_code} - {res.text}")
        sys.exit(1)
    data = res.json()
    print("[+] Strava access token refreshed successfully.")
    return data["access_token"]

def fetch_strava_activities(access_token, days_back=60):
    print(f"[+] Fetching Strava activity list from the last {days_back} days...")
    after_timestamp = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
    url = f"https://www.strava.com/api/v3/athlete/activities?after={after_timestamp}&per_page=200"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"[-] Failed to fetch Strava activities: {res.status_code} - {res.text}")
        sys.exit(1)
    activities = res.json()
    print(f"[+] Found {len(activities)} activities on Strava summary endpoint.")
    return activities

def fetch_strava_activity_detail(access_token, activity_id):
    """Fetch full detailed activity object from Strava including Description and Gear."""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json()
    return None

def fetch_strava_activity_photos(access_token, activity_id):
    """Fetch photo image URLs for a Strava activity."""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}/photos?size=600&photo_sources=true"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        urls = []
        for p in data:
            u = p.get("urls", {}).get("600") or p.get("urls", {}).get("100") or p.get("image_url")
            if u:
                urls.append(u)
        return urls
    return []

def find_existing_database():
    """Search Notion workspace for an existing 'Strava Workout Logs' database."""
    url = "https://api.notion.com/v1/search"
    payload = {
        "query": "Strava Workout Logs",
        "filter": {"value": "database", "property": "object"}
    }
    res = requests.post(url, headers=get_notion_headers(), json=payload)
    if res.status_code == 200:
        results = res.json().get("results", [])
        for item in results:
            if not item.get("in_trash", False) and not item.get("archived", False):
                title_list = item.get("title", [])
                title_text = "".join([t.get("plain_text", "") for t in title_list])
                if title_text == "Strava Workout Logs":
                    return item.get("id")
    return None

def ensure_database_schema(database_id):
    """Ensure Notion database schema has Description, Gear, Perceived Exertion, and Photos properties."""
    url = f"https://api.notion.com/v1/databases/{database_id}"
    payload = {
        "properties": {
            "Description": {"rich_text": {}},
            "Gear": {"rich_text": {}},
            "Perceived Exertion": {"number": {"format": "number"}},
            "Photos": {"files": {}}
        }
    }
    requests.patch(url, headers=get_notion_headers(), json=payload)

def create_notion_database(parent_page_id):
    """Create the 'Strava Workout Logs' database inside parent page."""
    print(f"[+] Creating 'Strava Workout Logs' database in Notion parent page ({parent_page_id})...")
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
                    {"name": "Yoga", "color": "purple"}
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
        "Location": {"rich_text": {}},
        "Description": {"rich_text": {}},
        "Gear": {"rich_text": {}},
        "Perceived Exertion": {"number": {"format": "number"}},
        "Photos": {"files": {}}
    }

    payload = {
        "parent": {"type": "page_id", "page_id": clean_page_id},
        "icon": {"type": "emoji", "emoji": "🏃"},
        "title": [{"type": "text", "text": {"content": "Strava Workout Logs"}}],
        "properties": properties_schema
    }

    res = requests.post(url, headers=get_notion_headers(), json=payload)
    if res.status_code != 200:
        print(f"[-] Failed to create Notion database: {res.status_code} - {res.text}")
        sys.exit(1)

    db_id = res.json()["id"]
    print(f"[+] Notion Database created successfully! Database ID: {db_id}")
    return db_id

def get_existing_strava_records(database_id):
    """Query Notion database to map Strava Activity IDs to Notion page IDs and existing properties."""
    print("[+] Querying Notion database for existing activity records...")
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    existing_map = {}  # strava_id -> page_id
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
        results = data.get("results", [])
        for page in results:
            page_id = page.get("id")
            props = page.get("properties", {})
            cover = page.get("cover")
            strava_id_prop = props.get("Strava ID", {}).get("rich_text", [])
            photos_prop = props.get("Photos", {}).get("files", [])
            if strava_id_prop:
                strava_id = strava_id_prop[0].get("plain_text", "").strip()
                desc_prop = props.get("Description", {}).get("rich_text", [])
                has_desc = bool(desc_prop and desc_prop[0].get("plain_text", "").strip())
                existing_map[strava_id] = {
                    "page_id": page_id,
                    "has_description": has_desc,
                    "has_cover": cover is not None,
                    "has_photos": bool(photos_prop)
                }

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    print(f"[+] Found {len(existing_map)} existing activity records in Notion database.")
    return existing_map

def format_seconds(seconds):
    """Format seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def calculate_pace(avg_speed_kph, sport_type):
    """Calculate running/walking pace in min/km or speed string."""
    is_foot_sport = sport_type.lower() in ["run", "trailrun", "walk", "hike", "virtualrun"]
    if is_foot_sport and avg_speed_kph > 0:
        pace_seconds = 3600.0 / avg_speed_kph
        pace_min = int(pace_seconds // 60)
        pace_sec = int(pace_seconds % 60)
        return f"{pace_min}:{pace_sec:02d} /km"
    elif avg_speed_kph > 0:
        return f"{avg_speed_kph:.1f} km/h"
    return "N/A"

def truncate_text(text, max_len=1990):
    if not text:
        return ""
    return text[:max_len] if len(text) > max_len else text

def replace_page_children(page_id, new_children_blocks):
    """Delete any existing child blocks of a Notion page to prevent duplicate blocks, then append new unique blocks."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    res = requests.get(url, headers=get_notion_headers())
    if res.status_code == 200:
        blocks = res.json().get("results", [])
        for block in blocks:
            block_id = block["id"]
            del_url = f"https://api.notion.com/v1/blocks/{block_id}"
            requests.delete(del_url, headers=get_notion_headers())

    if new_children_blocks:
        append_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        block_payload = {"children": new_children_blocks}
        requests.patch(append_url, headers=get_notion_headers(), json=block_payload)

def save_activity_to_notion(database_id, activity_detail, access_token, existing_page_id=None):
    strava_id_str = str(activity_detail["id"])
    name = activity_detail.get("name", "Untitled Workout")
    sport_type = activity_detail.get("sport_type") or activity_detail.get("type", "Workout")
    start_date_utc = activity_detail.get("start_date")  # ISO 8601 string
    
    distance_km = round(activity_detail.get("distance", 0) / 1000.0, 2)
    moving_time_sec = activity_detail.get("moving_time", 0)
    elapsed_time_sec = activity_detail.get("elapsed_time", 0)
    moving_time_min = round(moving_time_sec / 60.0, 1)
    
    avg_speed_kph = round(activity_detail.get("average_speed", 0) * 3.6, 2)
    max_speed_kph = round(activity_detail.get("max_speed", 0) * 3.6, 2)
    elevation_gain = round(activity_detail.get("total_elevation_gain", 0), 1)

    pace_str = calculate_pace(avg_speed_kph, sport_type)
    
    avg_hr = round(activity_detail["average_heartrate"], 1) if activity_detail.get("has_heartrate") else None
    max_hr = round(activity_detail["max_heartrate"], 1) if activity_detail.get("has_heartrate") else None
    
    calories = activity_detail.get("calories")
    if calories is None and "kilojoules" in activity_detail:
        calories = round(activity_detail["kilojoules"] / 4.184)
    if calories is not None:
        calories = round(calories)

    suffer_score = activity_detail.get("suffer_score") or activity_detail.get("suf_score")

    loc_parts = [p for p in [activity_detail.get("location_city"), activity_detail.get("location_state"), activity_detail.get("location_country")] if p]
    location_str = ", ".join(loc_parts) if loc_parts else ""

    strava_link = f"https://www.strava.com/activities/{strava_id_str}"

    description_text = truncate_text(activity_detail.get("description", ""))
    gear_info = activity_detail.get("gear")
    gear_name = gear_info.get("name") if isinstance(gear_info, dict) else None
    perceived_exertion = activity_detail.get("perceived_exertion")

    # Fetch Strava activity photos
    photo_urls = fetch_strava_activity_photos(access_token, strava_id_str)

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
        "Strava Link": {"url": strava_link}
    }

    if avg_hr is not None:
        properties["Avg Heart Rate (bpm)"] = {"number": avg_hr}
    if max_hr is not None:
        properties["Max Heart Rate (bpm)"] = {"number": max_hr}
    if calories is not None:
        properties["Calories (kcal)"] = {"number": calories}
    if suffer_score is not None:
        properties["Relative Effort"] = {"number": suffer_score}
    if location_str:
        properties["Location"] = {"rich_text": [{"text": {"content": location_str}}]}
    if description_text:
        properties["Description"] = {"rich_text": [{"text": {"content": description_text}}]}
    if gear_name:
        properties["Gear"] = {"rich_text": [{"text": {"content": gear_name}}]}
    if perceived_exertion is not None:
        properties["Perceived Exertion"] = {"number": round(float(perceived_exertion), 1)}

    # Map photos to Photos property (files type)
    if photo_urls:
        properties["Photos"] = {
            "files": [
                {
                    "name": f"Strava Photo {idx+1}",
                    "type": "external",
                    "external": {"url": p_url}
                } for idx, p_url in enumerate(photo_urls)
            ]
        }

    # Body children blocks: Only keep description callout block (no header cover, no body image gallery)
    children_blocks = []
    if description_text:
        children_blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": description_text}}],
                "icon": {"emoji": "📝"}
            }
        })

    if existing_page_id:
        # Update existing Notion page properties and remove header cover image
        url = f"https://api.notion.com/v1/pages/{existing_page_id}"
        payload = {
            "properties": properties,
            "cover": None  # Explicitly remove header cover image
        }

        res = requests.patch(url, headers=get_notion_headers(), json=payload)
        if res.status_code != 200:
            print(f"[-] Failed to update activity '{name}' (ID: {strava_id_str}): {res.status_code} - {res.text}")
            return False

        # Replace body blocks cleanly (keeps only description callout, removes body image gallery)
        replace_page_children(existing_page_id, children_blocks)

        return True
    else:
        # Create new Notion page without header cover image
        url = "https://api.notion.com/v1/pages"

        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
            "children": children_blocks
        }

        res = requests.post(url, headers=get_notion_headers(), json=payload)
        if res.status_code != 200:
            print(f"[-] Failed to add activity '{name}' (ID: {strava_id_str}): {res.status_code} - {res.text}")
            return False
        return True

def sync():
    print("=" * 60)
    print(" Strava to Notion Sync Automation ")
    print("=" * 60)

    # Check credentials
    if not NOTION_API_KEY:
        print("[-] Error: NOTION_API_KEY environment variable is missing.")
        sys.exit(1)
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET or not STRAVA_REFRESH_TOKEN:
        print("[-] Error: Strava API credentials (CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) are missing.")
        sys.exit(1)

    # 1. Database Resolution
    db_id = NOTION_DATABASE_ID
    if not db_id:
        db_id = find_existing_database()
        if db_id:
            print(f"[+] Auto-detected existing 'Strava Workout Logs' database: {db_id}")
        else:
            if not NOTION_PAGE_ID:
                print("[-] Error: NOTION_PAGE_ID environment variable is missing for database creation.")
                sys.exit(1)
            db_id = create_notion_database(NOTION_PAGE_ID)

    # Ensure database schema has Description, Gear, Perceived Exertion, and Photos properties
    ensure_database_schema(db_id)

    # 2. Strava Activities Fetch
    access_token = get_strava_access_token()
    activities_summary = fetch_strava_activities(access_token, days_back=60)

    # 3. Deduplication and Record map
    existing_map = get_existing_strava_records(db_id)

    # 4. Sync / Update activities
    synced_count = 0
    updated_count = 0
    skipped_count = 0

    for summary in reversed(activities_summary):  # Sync oldest to newest
        act_id = summary["id"]
        act_id_str = str(act_id)
        act_name = summary.get("name", "Workout")
        total_photos = summary.get("total_photo_count", 0)

        existing_record = existing_map.get(act_id_str)
        
        # Skip if record exists, has description, has photos property if photos exist, and has NO cover
        if existing_record and existing_record["has_description"] and not existing_record["has_cover"]:
            if total_photos == 0 or existing_record["has_photos"]:
                skipped_count += 1
                continue

        # Fetch detailed activity to get full Description, Gear, and Perceived Exertion
        act_detail = fetch_strava_activity_detail(access_token, act_id)
        if not act_detail:
            act_detail = summary  # fallback to summary object

        if existing_record:
            print(f"[+] Removing header cover image & updating Photos property: '{act_name}' (ID: {act_id_str})")
            success = save_activity_to_notion(db_id, act_detail, access_token, existing_page_id=existing_record["page_id"])
            if success:
                updated_count += 1
        else:
            print(f"[+] Syncing new activity: '{act_name}' (ID: {act_id_str}, Date: {summary.get('start_date')})")
            success = save_activity_to_notion(db_id, act_detail, access_token)
            if success:
                synced_count += 1

        time.sleep(0.4)  # Gentle rate limiting for Strava & Notion APIs

    print("\n" + "=" * 60)
    print(f"[+] SYNC COMPLETED SUCCESSFULLY!")
    print(f"    - New Workouts Added: {synced_count}")
    print(f"    - Existing Workouts Updated: {updated_count}")
    print(f"    - Already Up-to-Date: {skipped_count}")
    print("=" * 60)

if __name__ == "__main__":
    sync()
