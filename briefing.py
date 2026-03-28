import os
import json
import datetime
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ── Config from environment variables ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]

GOOGLE_CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REFRESH_TOKEN = os.environ["GOOGLE_REFRESH_TOKEN"]

TIMEZONE_OFFSET_HOURS = 8  # Singapore (UTC+8)

# ── Google credentials ──────────────────────────────────────────────────────────
def get_google_credentials():
    return Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/tasks.readonly",
        ],
    )

# ── Fetch today's calendar events ──────────────────────────────────────────────
def fetch_events(creds):
    service = build("calendar", "v3", credentials=creds)
    now_utc = datetime.datetime.utcnow()
    # Singapore day boundaries in UTC
    today_local = now_utc + datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS)
    day_start = datetime.datetime(today_local.year, today_local.month, today_local.day, 0, 0, 0)
    day_end   = day_start + datetime.timedelta(days=1)
    time_min  = (day_start - datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS)).isoformat() + "Z"
    time_max  = (day_end   - datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS)).isoformat() + "Z"

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for e in result.get("items", []):
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        end   = e["end"].get("dateTime",   e["end"].get("date", ""))
        # Convert UTC time to SGT for display
        if "T" in start:
            dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
            dt_sgt = dt + datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS) if dt.utcoffset() is None else dt.astimezone(datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS)))
            start_str = dt_sgt.strftime("%I:%M %p")
        else:
            start_str = "All day"

        events.append({
            "title": e.get("summary", "Untitled"),
            "start": start_str,
            "location": e.get("location", ""),
            "description": e.get("description", "")[:200],
        })
    return events

# ── Fetch incomplete tasks ──────────────────────────────────────────────────────
def fetch_tasks(creds):
    service = build("tasks", "v1", credentials=creds)
    task_lists = service.tasklists().list().execute().get("items", [])

    all_tasks = []
    for tl in task_lists:
        tasks = service.tasks().list(
            tasklist=tl["id"],
            showCompleted=False,
            showHidden=False,
        ).execute().get("items", [])

        for t in tasks:
            if t.get("status") != "completed":
                due = t.get("due", "")
                if due:
                    due_dt = datetime.datetime.fromisoformat(due.replace("Z", "+00:00"))
                    due_str = due_dt.strftime("%d %b")
                else:
                    due_str = "No due date"
                all_tasks.append({
                    "title": t.get("title", "Untitled"),
                    "due": due_str,
                    "notes": t.get("notes", "")[:100],
                    "list": tl.get("title", "Tasks"),
                })
    return all_tasks

# ── Ask Claude to write the briefing ───────────────────────────────────────────
def generate_briefing(events, tasks, today_str):
    events_text = json.dumps(events, indent=2) if events else "No events today."
    tasks_text  = json.dumps(tasks,  indent=2) if tasks  else "No pending tasks."

    prompt = f"""Today is {today_str} (Singapore time). 

Here are today's calendar events:
{events_text}

Here are the user's incomplete tasks/checklists:
{tasks_text}

Write a friendly, concise daily briefing for the user to receive via Telegram. Format it clearly using plain text (no markdown — Telegram will handle basic formatting). Structure it as:

1. A warm good morning greeting with the date
2. A "Today's Schedule" section listing events in order with times
3. A "Pending Tasks" section listing incomplete items, highlighting anything due today or overdue
4. A short motivational closing line

Keep it punchy and scannable — this is a morning message, not a report. Use line breaks generously. Do NOT use asterisks or markdown symbols."""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]

# ── Send to Telegram ────────────────────────────────────────────────────────────
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "",
    }
    r = requests.post(url, json=payload)
    r.raise_for_status()
    print("Message sent to Telegram successfully.")

# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    creds = get_google_credentials()

    now_sgt = datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS)
    today_str = now_sgt.strftime("%A, %d %B %Y")

    print("Fetching calendar events...")
    events = fetch_events(creds)
    print(f"  Found {len(events)} events")

    print("Fetching tasks...")
    tasks = fetch_tasks(creds)
    print(f"  Found {len(tasks)} pending tasks")

    print("Generating briefing with Claude...")
    briefing = generate_briefing(events, tasks, today_str)
    print("Briefing generated.")

    send_telegram(briefing)

if __name__ == "__main__":
    main()
