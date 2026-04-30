#!/usr/bin/env python3
"""
github_activity – fetch recent public GitHub activity for a user.

The script is pure‑standard‑library (urllib, json, argparse, datetime, os).
It now offers a --debug flag to show the raw JSON payload and the
X‑RateLimit‑Remaining header.
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request


# ----------------------------------------------------------------------
# Network helper – call the public GitHub API
# ----------------------------------------------------------------------
def fetch_events(username: str) -> tuple[list, dict]:
    """
    Returns (events, response_headers).

    * events – the JSON‑decoded list (empty list if the user has no public events)
    * response_headers – a dict‑like mapping of the HTTP response headers
    """
    url = f"https://api.github.com/users/{username}/events"
    headers = {"User-Agent": "github-activity-cli"}

    # Optional personal access token – raises the rate‑limit from 60 → 5 000/hr
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            # GitHub always returns JSON when status == 200
            if resp.status != 200:
                raise urllib.error.HTTPError(
                    url, resp.status, resp.reason, resp.headers, None
                )
            raw = resp.read().decode("utf-8")
            events = json.loads(raw)  # should be a list
            # urllib.response.headers behaves like a mapping
            return events, dict(resp.headers)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f'User "{username}" not found (404)') from None
        if e.code == 403:
            raise RuntimeError(
                "GitHub rate limit exceeded (403). "
                "Set a personal token in GITHUB_TOKEN to raise the limit."
            ) from None
        raise RuntimeError(f"GitHub HTTP error {e.code}: {e.reason}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from None


# ----------------------------------------------------------------------
# Time helper – short relative description (e.g. 2h ago)
# ----------------------------------------------------------------------
def relative_time(iso_ts: str) -> str:
    """Convert a GitHub ISO‑8601 timestamp into a short relative string."""
    try:
        ev_dt = datetime.datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.datetime.utcnow()
        diff = now - ev_dt
        secs = int(diff.total_seconds())

        if secs < 60:
            return "just now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hrs = mins // 60
        if hrs < 24:
            return f"{hrs}h ago"
        days = hrs // 24
        if days < 7:
            return f"{days}d ago"
        weeks = days // 7
        if weeks < 4:
            return f"{weeks}w ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        years = days // 365
        return f"{years}y ago"
    except Exception:
        # If anything goes wrong just return the raw timestamp.
        return iso_ts


# ----------------------------------------------------------------------
# Human‑readable formatting for each known event type
# ----------------------------------------------------------------------
def format_event(ev: dict) -> str:
    ev_type = ev.get("type", "")
    repo = ev.get("repo", {}).get("name", "UNKNOWN")
    payload = ev.get("payload", {})

    # PushEvent ---------------------------------------------------------
    if ev_type == "PushEvent":
        count = payload.get("size", 0)
        commits = payload.get("commits", [])
        msg_part = ""
        if commits:
            msgs = [c.get("message", "").split("\n")[0] for c in commits[:3]]
            msg_part = " – " + "; ".join(msgs)
        return f"Pushed {count} commit{'s' if count != 1 else ''} to {repo}{msg_part}"

    # IssuesEvent -------------------------------------------------------
    if ev_type == "IssuesEvent":
        action = payload.get("action", "").capitalize()
        issue = payload.get("issue", {})
        number = issue.get("number")
        if number:
            return f"{action} issue #{number} in {repo}"
        return f"{action} an issue in {repo}"

    # WatchEvent (star) -------------------------------------------------
    if ev_type == "WatchEvent":
        return f"Starred {repo}"

    # ForkEvent --------------------------------------------------------
    if ev_type == "ForkEvent":
        forkee = payload.get("forkee", {}).get("full_name")
        if forkee:
            return f"Forked {repo} → {forkee}"
        return f"Forked {repo}"

    # PullRequestEvent -------------------------------------------------
    if ev_type == "PullRequestEvent":
        action = payload.get("action", "").capitalize()
        pr = payload.get("pull_request", {})
        number = pr.get("number")
        if number:
            return f"{action} Pull Request #{number} in {repo}"
        return f"{action} a Pull Request in {repo}"

    # Create / Delete ---------------------------------------------------
    if ev_type in ("CreateEvent", "DeleteEvent"):
        verb = "Created" if ev_type == "CreateEvent" else "Deleted"
        ref_type = payload.get("ref_type", "")
        ref = payload.get("ref")
        if ref:
            return f"{verb} {ref_type} \"{ref}\" in {repo}"
        return f"{verb} {ref_type} in {repo}"

    # Fallback ----------------------------------------------------------
    return f"{ev_type} on {repo}"


# ----------------------------------------------------------------------
# CLI argument parsing
# ----------------------------------------------------------------------
def parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Show the most recent public GitHub activity for a user."
    )
    p.add_argument("username", help="GitHub username")
    p.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of events to display (default: 10)",
    )
    p.add_argument(
        "--type",
        dest="filter_type",
        help="Only show events of this type (e.g. PushEvent, IssuesEvent)",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Print the raw JSON payload and rate‑limit info (for troubleshooting)",
    )
    return p.parse_args()


# ----------------------------------------------------------------------
# Main driver
# ----------------------------------------------------------------------
def main() -> None:
    args = parse_cli()

    try:
        events, headers = fetch_events(args.username)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Show useful debug information if the flag was given
    if args.debug:
        remaining = headers.get("X-RateLimit-Remaining", "unknown")
        limit = headers.get("X-RateLimit-Limit", "unknown")
        reset_ts = headers.get("X-RateLimit-Reset")
        if reset_ts:
            reset_dt = datetime.datetime.utcfromtimestamp(int(reset_ts))
            reset_in = (reset_dt - datetime.datetime.utcnow()).seconds // 60
            reset_str = f"{reset_in} min"
        else:
            reset_str = "unknown"

        print("=== DEBUG INFO ===")
        print(f"Rate‑limit: {remaining}/{limit} remaining, resets in {reset_str}")
        print("Raw JSON payload:")
        print(json.dumps(events, indent=2, ensure_ascii=False))
        print("==================\n")

    # Optional filtering by event type
    if args.filter_type:
        events = [e for e in events if e.get("type") == args.filter_type]

    if not events:
        print("No recent activity found.")
        return

    # Print at most `limit` rows (GitHub already returns newest first)
    for ev in events[: args.limit]:
        description = format_event(ev)
        ts = ev.get("created_at", "")
        time_suffix = f" ({relative_time(ts)})" if ts else ""
        print(f"- {description}{time_suffix}")


if __name__ == "__main__":
    main()
