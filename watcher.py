"""
Doomsday Watch - checks BookMyShow for bookable night shows at chosen
Chennai theatres and pushes a loud alert to your phone through ntfy.

Run once:            python watcher.py
Run constantly:      python watcher.py --loop 180      (checks every ~3 min)
Send a test alert:   python watcher.py --test-notify

The notification channel name comes from the NTFY_TOPIC environment
variable (or a file called ntfy_topic.txt next to this script).
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "config.json").read_text())
STATE_FILE = HERE / "state.json"
STATUS_FILE = HERE / "docs" / "status.json"
IST = timezone(timedelta(hours=5, minutes=30))

API_URL = "https://in.bookmyshow.com/api/movies-data/v4/showtimes-by-event/primary-dynamic"
REGION = {"code": "CHEN", "slug": "chennai", "lat": "13.056", "lon": "80.206", "geohash": "tf3"}
OPEN_STATUSES = {"1": "Almost full", "2": "Filling fast", "3": "Available"}
FAILS_BEFORE_WARNING = 4


# ---------------------------------------------------------------- helpers
def now_ist():
    return datetime.now(IST)


def booking_url(date_code):
    return (f"https://in.bookmyshow.com/movies/{CONFIG['city_slug']}/{CONFIG['movie_slug']}"
            f"/buytickets/{CONFIG['event_code']}/{date_code}")


def pretty_date(date_code):
    return datetime.strptime(date_code, "%Y%m%d").strftime("%a %d %b")


def rupees(price):
    try:
        return f"{float(price):,.0f}"
    except ValueError:
        return price


def hhmm_to_int(s):
    h, m = s.split(":")
    return int(h) * 100 + int(m)


def show_time_code(show):
    """Return the show time as HHMM int, from BMS's code or the '08:30 PM' title."""
    code = str(show.get("time_code", "")).strip()
    if code.isdigit():
        return int(code)
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP]M)", show.get("time", ""), re.I)
    if not m:
        return -1
    h, mi, ap = int(m[1]), int(m[2]), m[3].upper()
    h = (h % 12) + (12 if ap == "PM" else 0)
    return h * 100 + mi


def is_night(show):
    t = show_time_code(show)
    if t < 0:
        return False
    return t >= hhmm_to_int(CONFIG["night_from"]) or t < hhmm_to_int(CONFIG["include_after_midnight_until"])


def theatre_label(venue_name):
    low = venue_name.lower()
    for label, keys in CONFIG["theatres"].items():
        if any(k in low for k in keys):
            return label
    return None


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def ntfy_topic():
    topic = os.getenv("NTFY_TOPIC", "").strip()
    f = HERE / "ntfy_topic.txt"
    if not topic and f.exists():
        topic = f.read_text().strip()
    return topic


def notify(title, message, priority=5, click=None, tags="rotating_light"):
    """Push to the phone via ntfy.sh. Title must stay plain ASCII (HTTP header)."""
    topic = ntfy_topic()
    if not topic:
        print("  ! No NTFY_TOPIC set - alert only printed here:\n   ", title, "|", message)
        return False
    headers = {"Title": title.encode("ascii", "ignore").decode(), "Priority": str(priority), "Tags": tags}
    if click:
        headers["Click"] = click
        headers["Actions"] = f"view, Book now, {click}"
    try:
        r = requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=15)
        print(f"  -> push sent ({r.status_code})")
        return r.ok
    except requests.RequestException as e:
        print(f"  ! push failed: {e}")
        return False


# ---------------------------------------------------------------- BookMyShow
def fetch_date(date_code):
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": booking_url(date_code),
        "x-app-code": "WEB",
        "x-region-code": REGION["code"],
        "x-region-slug": REGION["slug"],
        "x-geohash": REGION["geohash"],
        "x-latitude": REGION["lat"],
        "x-longitude": REGION["lon"],
        "x-location-selection": "manual",
        "x-lsid": "",
    }
    params = {
        "eventCode": CONFIG["event_code"], "dateCode": date_code, "isDesktop": "true",
        "regionCode": REGION["code"], "xLocationShared": "false",
        "memberId": "", "lsId": "", "subCode": "", "lat": REGION["lat"], "lon": REGION["lon"],
    }
    try:
        r = requests.get(API_URL, headers=headers, params=params, timeout=20)
        if r.status_code == 200:
            return r.json()
        print(f"  {date_code}: HTTP {r.status_code}")
    except (requests.RequestException, ValueError) as e:
        print(f"  {date_code}: request failed ({e})")
    return None


def parse_shows(data, requested_date):
    shows = []
    for w in data.get("data", {}).get("showtimeWidgets", []):
        if w.get("type") != "groupList":
            continue
        for g in w.get("data", []):
            if g.get("type") != "venueGroup":
                continue
            for card in g.get("data", []):
                if card.get("type") != "venue-card":
                    continue
                addl = card.get("additionalData", {})
                for st in card.get("showtimes", []):
                    sa = st.get("additionalData", {})
                    date_code = str(sa.get("showDateCode") or sa.get("dateCode") or "").strip()
                    if not date_code and re.match(r"^\d{8}", sa.get("cutOffDateTime", "")):
                        date_code = sa["cutOffDateTime"][:8]
                    cats = [{"name": c.get("priceDesc", ""), "price": str(c.get("curPrice", "")),
                             "status": str(c.get("availStatus", ""))} for c in sa.get("categories", [])]
                    shows.append({
                        "venue": addl.get("venueName", "Unknown"),
                        "venue_code": addl.get("venueCode", ""),
                        "session": str(sa.get("sessionId", "")),
                        "date": date_code or requested_date,
                        "time": st.get("title", ""),
                        "time_code": sa.get("showTimeCode", ""),
                        "format": st.get("screenAttr", "") or sa.get("attributes", ""),
                        "categories": cats,
                    })
    return shows


def open_categories(show):
    return [c for c in show["categories"] if c["status"] in OPEN_STATUSES]


# ---------------------------------------------------------------- one check
def check_once():
    state = load_json(STATE_FILE, {"alerted": {}, "fails": 0, "warned": False})
    started = now_ist()
    print(f"[{started:%d %b %H:%M:%S}] checking {len(CONFIG['dates'])} dates")

    all_shows, ok_dates = [], 0
    for i, d in enumerate(CONFIG["dates"]):
        data = fetch_date(d)
        if data is not None:
            ok_dates += 1
            all_shows.extend(parse_shows(data, d))
        if i < len(CONFIG["dates"]) - 1:
            time.sleep(random.uniform(0.8, 1.8))

    # -- could not reach BookMyShow at all: say so instead of staying silent
    if ok_dates == 0:
        state["fails"] = state.get("fails", 0) + 1
        print(f"  could not reach BookMyShow ({state['fails']} runs in a row)")
        if state["fails"] >= FAILS_BEFORE_WARNING and not state.get("warned"):
            notify("Doomsday watch is blind",
                   f"BookMyShow has refused the last {state['fails']} checks. "
                   "No alerts can fire until this clears - check the app manually.",
                   priority=3, tags="warning")
            state["warned"] = True
        write_status(started, [], reachable=False, fails=state["fails"])
        STATE_FILE.write_text(json.dumps(state, indent=2))
        return

    if state.get("warned"):
        notify("Doomsday watch is back", "BookMyShow is answering again. Watching resumed.",
               priority=2, tags="white_check_mark")
    state["fails"], state["warned"] = 0, False

    # -- find watched night shows and which of them have seats
    watched = []
    for s in all_shows:
        label = theatre_label(s["venue"])
        if not label and not CONFIG.get("alert_on_any_theatre"):
            continue
        if not is_night(s):
            continue
        s["label"] = label or s["venue"]
        s["open"] = open_categories(s)
        watched.append(s)

    newly_open = []
    alerted = state.get("alerted", {})
    still_open = {}
    for s in watched:
        key = f"{s['venue_code']}|{s['session']}|{s['date']}"
        if s["open"]:
            still_open[key] = True
            if key not in alerted:
                newly_open.append(s)
    # a show that sells out again is forgotten, so a later re-open alerts again
    state["alerted"] = still_open

    if newly_open:
        weekend = set(CONFIG["weekend_dates"])
        newly_open.sort(key=lambda s: (s["date"] not in weekend, s["date"], show_time_code(s)))
        lines = []
        for s in newly_open[:6]:
            best = max(s["open"], key=lambda c: c["status"])
            lines.append(f"{s['label']} - {pretty_date(s['date'])} {s['time']}"
                         f"{' ' + s['format'] if s['format'] else ''} ({best['name']} Rs {rupees(best['price'])}, "
                         f"{OPEN_STATUSES[best['status']]})")
        if len(newly_open) > 6:
            lines.append(f"+{len(newly_open) - 6} more shows")
        top = newly_open[0]
        any_weekend = any(s["date"] in weekend for s in newly_open)
        notify(f"DOOMSDAY SEATS OPEN: {top['label']} {pretty_date(top['date'])}",
               "\n".join(lines), priority=5 if any_weekend else 4, click=booking_url(top["date"]))
        print("  NEW:", *lines, sep="\n    ")
    else:
        print(f"  {len(watched)} watched night shows, {sum(1 for s in watched if s['open'])} with seats, nothing new")

    write_status(started, watched, reachable=True, fails=0)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def write_status(checked_at, watched, reachable, fails):
    STATUS_FILE.parent.mkdir(exist_ok=True)
    rows = [{
        "theatre": s["label"], "venue": s["venue"], "date": s["date"], "day": pretty_date(s["date"]),
        "time": s["time"], "format": s["format"],
        "open": [{"name": c["name"], "price": c["price"], "label": OPEN_STATUSES[c["status"]]} for c in s["open"]],
        "url": booking_url(s["date"]),
    } for s in watched]
    rows.sort(key=lambda r: (r["date"], r["theatre"], r["time"]))
    STATUS_FILE.write_text(json.dumps({
        "movie": CONFIG["movie_name"], "checked_at": checked_at.isoformat(),
        "reachable": reachable, "consecutive_failures": fails,
        "dates": CONFIG["dates"], "weekend_dates": CONFIG["weekend_dates"],
        "theatres": list(CONFIG["theatres"].keys()), "shows": rows,
    }, indent=1))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, metavar="SECONDS", help="keep checking, roughly every SECONDS")
    ap.add_argument("--test-notify", action="store_true", help="send a test push and exit")
    args = ap.parse_args()

    if args.test_notify:
        ok = notify("Doomsday watch test", "If you can read this, alerts reach your phone.",
                    priority=4, click=booking_url(CONFIG["dates"][0]), tags="tada")
        sys.exit(0 if ok else 1)

    if not args.loop:
        check_once()
        return

    interval = max(args.loop, 60)  # never hammer BookMyShow faster than once a minute
    print(f"Watching every ~{interval}s. Ctrl+C to stop.")
    while True:
        try:
            check_once()
        except Exception as e:  # keep the loop alive through odd responses
            print(f"  ! check crashed: {e}")
        time.sleep(interval + random.uniform(0, 30))


if __name__ == "__main__":
    main()
