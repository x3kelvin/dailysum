"""
Run this script ONCE on your local machine to get your Google refresh token.
You only need to do this one time — the refresh token doesn't expire.

Requirements:
  pip install google-auth-oauthlib

Usage:
  python get_google_token.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]

CLIENT_ID     = input("Paste your Google Client ID: ").strip()
CLIENT_SECRET = input("Paste your Google Client Secret: ").strip()

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

print("\n" + "="*60)
print("SUCCESS! Copy these values into your GitHub secrets:\n")
print(f"GOOGLE_CLIENT_ID:     {CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET: {CLIENT_SECRET}")
print(f"GOOGLE_REFRESH_TOKEN: {creds.refresh_token}")
print("="*60)
