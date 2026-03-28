import os
import datetime
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TELEGRAM_BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID     = os.environ["TELEGRAM_CHAT_ID"]
GOOGLE_CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REFRESH_TOKEN = os.environ["GOOGLE_REFRESH_TOKEN"]

NAME            = "Kelvin"
TIMEZONE_OFFSET = datetime.timedelta(hours=8)

def get_credentials():
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

def now_sgt():
    return datetime.datetime.utcnow() + TIMEZONE_OFFSET

def friendly_due_label(due_date, today):
    delta = (due_date - today).days
    if delta < 0:
        days_ago = abs(delta)
        return f"[Overdue by {days_ago} day{'s' if days_ago > 1 else ''}]"
    elif delta == 0:
        return "[Due today]"
    elif delta == 1:
        return "[Due tomorrow]"
    elif delta <= 6:
        return f"[Due {due_date.strftime('%A')}]"
    else:
        return f"[Due {due_date.strftime('%d %b')}]"

def fetch_events(creds, today):
    service   = build("calendar", "v3", credentials=creds)
    day_start = datetime.datetime(today.year, today.month, today.day, 0, 0, 0)
    day_end   = day_start + datetime.timedelta(days=1)
    time_min  = (day_start - TIMEZONE_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_max  = (day_end   - TIMEZONE_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = []
    for e in result.get("items", []):
        raw_start = e["start"].get("dateTime", e["start"].get("date", ""))
        if "T" in raw_start:
            dt_utc = datetime.datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            dt_sgt = dt_utc.astimezone(datetime.timezone(TIMEZONE_OFFSET))
            start_str = dt_sgt.strftime("%I:%M %p").lstrip("0")
        else:
            start_str = "All day"
        events.append({"title": e.get("summary", "Untitled"), "start": start_str})
    return events

def fetch_tasks(creds, today):
    service    = build("tasks", "v1", credentials=creds)
    task_lists = service.tasklists().list().execute().get("items", [])
    upper_limit = today + datetime.timedelta(days=7)
    tasks = []
    for tl in task_lists:
        items = service.tasks().list(
            tasklist=tl["id"],
            showCompleted=False,
            showHidden=True,
        ).execute().get("items", [])
        for t in items:
            if t.get("status") == "completed":
                continue
            raw_due = t.get("due", "")
            if raw_due:
                due_dt = datetime.datetime.fromisoformat(raw_due.replace("Z", "+00:00")).date()
                if due_dt > upper_limit:
                    continue  # skip tasks more than 7 days away
                tasks.append({"title": t.get("title", "Untitled"), "due": due_dt})
            else:
                tasks.append({"title": t.get("title", "Untitled"), "due": None})
    # Overdue first, then today, then future, then no due date
    tasks.sort(key=lambda x: (x["due"] is None, x["due"] or datetime.date.max))
    return tasks

def build_message(events, tasks, today):
    date_str = today.strftime("%-d %b (%A)")
    lines = [f"Good morning {NAME}! Here's your day for {date_str}", ""]
    lines.append("📅 Your Schedule")
    if events:
        for e in events:
            lines.append(f"  {e['start']} — {e['title']}")
    else:
        lines.append("  No events today.")
    lines.append("")
    lines.append("📋 Pending Tasks")
    if tasks:
        for t in tasks:
            if t["due"]:
                label = friendly_due_label(t["due"], today)
                lines.append(f"  {label} {t['title']}")
            else:
                lines.append(f"  {t['title']}")
    else:
        lines.append("  No pending tasks.")
    return "\n".join(lines)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
    r.raise_for_status()
    print("Sent successfully.")

def main():
    today = now_sgt().date()
    creds = get_credentials()
    print("Fetching events...")
    events = fetch_events(creds, today)
    print(f"  {len(events)} events found")
    print("Fetching tasks...")
    tasks = fetch_tasks(creds, today)
    print(f"  {len(tasks)} tasks found")
    message = build_message(events, tasks, today)
    print("\n--- Preview ---")
    print(message)
    print("---------------\n")
    send_telegram(message)

if __name__ == "__main__":
    main()
