import os
import sys
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Strava Authorization Successful!</h1><p>You can close this browser tab and return to your terminal.</p></body></html>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization code missing.")

def main():
    global CLIENT_ID, CLIENT_SECRET
    print("=" * 60)
    print(" Strava OAuth Setup Helper ")
    print("=" * 60)

    if not CLIENT_ID:
        CLIENT_ID = input("Enter your Strava Client ID: ").strip()
    if not CLIENT_SECRET:
        CLIENT_SECRET = input("Enter your Strava Client Secret: ").strip()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: Both Client ID and Client Secret are required.")
        sys.exit(1)

    redirect_uri = "http://localhost:8000"
    scope = "read,activity:read_all"
    auth_url = (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"approval_prompt=force&scope={scope}"
    )

    print("\nPlease authorize access in your browser:")
    print(auth_url)
    print("\nStarting local server on http://localhost:8000 to listen for authorization callback...")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    server = HTTPServer(("localhost", 8000), OAuthHandler)
    server.handle_request()  # Handles single request and returns

    if not auth_code:
        print("\nFailed to obtain authorization code.")
        sys.exit(1)

    print("\nAuthorization code received! Exchanging for tokens...")

    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code"
    }

    res = requests.post(token_url, data=payload)
    if res.status_code != 200:
        print(f"Error fetching tokens: {res.status_code} - {res.text}")
        sys.exit(1)

    data = res.json()
    refresh_token = data.get("refresh_token")
    access_token = data.get("access_token")
    athlete = data.get("athlete", {})

    print("\n" + "=" * 60)
    print(" SUCCESS! ")
    print("=" * 60)
    print(f"Athlete: {athlete.get('firstname', '')} {athlete.get('lastname', '')} (ID: {athlete.get('id')})")
    print(f"\nSTRAVA_REFRESH_TOKEN: {refresh_token}")
    print("=" * 60)
    print("\nAdd these credentials to your .env file or GitHub Secrets:")
    print(f"STRAVA_CLIENT_ID={CLIENT_ID}")
    print(f"STRAVA_CLIENT_SECRET={CLIENT_SECRET}")
    print(f"STRAVA_REFRESH_TOKEN={refresh_token}")

if __name__ == "__main__":
    main()
