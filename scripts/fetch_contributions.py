#!/usr/bin/env python3
"""
Scrapes real daily contribution counts from GitHub's public, unauthenticated
contributions endpoint (https://github.com/users/<username>/contributions)
and writes data/contributions.json.

Includes safety guarantees:
- If zero cells are found or parsing fails, DOES NOT overwrite existing data/contributions.json.
- Exits with a clear non-zero error.
"""
import datetime
import json
import os
import re
import sys
import tempfile
import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "helloabhishek2004")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")


def fetch_days():
    print(f"Fetching contribution data from {URL}...")
    try:
        resp = requests.get(URL, headers={"User-Agent": "profile-readme-bot/1.0"}, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to fetch contributions page: {e}", file=sys.stderr)
        sys.exit(1)

    soup = BeautifulSoup(resp.text, "html.parser")
    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print("ERROR: No calendar cells found (td.ContributionCalendar-day). GitHub markup may have changed.", file=sys.stderr)
        print("Aborting without touching existing contributions.json.", file=sys.stderr)
        sys.exit(1)

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if not text:
            # Fallback for aria-label or inner text if tool-tip tag isn't found
            text = td.get("aria-label") or td.get_text(strip=True) or ""

        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0

        level_str = td.get("data-level")
        level = int(level_str) if level_str and level_str.isdigit() else 0

        days.append({"date": date, "count": count, "level": level})

    if not days:
        print("ERROR: Found cells but failed to parse any valid day records.", file=sys.stderr)
        print("Aborting without touching existing contributions.json.", file=sys.stderr)
        sys.exit(1)

    days.sort(key=lambda d: d["date"])
    print(f"Successfully parsed {len(days)} days of contributions.")
    return days


def compute_current_streak(days):
    if not days:
        return 0, None, None
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet; don't break streak on today
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


def main():
    days = fetch_days()
    data = build_data(days)

    target_dir = os.path.dirname(os.path.abspath(OUT_PATH))
    os.makedirs(target_dir, exist_ok=True)

    # Atomic write to avoid partial or corrupted files
    tmp_fd, tmp_file = tempfile.mkstemp(dir=target_dir, prefix="contrib_", suffix=".tmp")
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, OUT_PATH)

    print(
        f"Wrote {OUT_PATH}: {data['total_contributions']} contributions, "
        f"current streak {data['current_streak']['length']}, "
        f"longest streak {data['longest_streak']['length']}."
    )


if __name__ == "__main__":
    main()
