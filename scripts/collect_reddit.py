#!/usr/bin/env python3
"""
collect_reddit.py — Gather candidate comments from r/HouseOfTheDragon for TakeMeter.

Uses ONLY the Python standard library (urllib) — no pip installs, no API key.
It reads Reddit's public .json endpoints, walks the comment trees of the top /
hot posts, filters out junk (deleted, bots, too short/long, link dumps), dedupes,
and writes a CSV with empty `label` / `notes` columns ready for you to annotate.

This collects CANDIDATES only. You still read and label every row by hand
(optionally with an LLM pre-label pass) — that is the point of the project.

Usage (defaults are sensible — just run it):
    python3 scripts/collect_reddit.py
    python3 scripts/collect_reddit.py --pages 3 --listings top hot --time all
    python3 scripts/collect_reddit.py --out data/raw_candidates.csv

Then open the CSV, fill the `label` column with one of:
    lore_analysis | faction_cheerleading | visceral_reaction
"""

import argparse
import csv
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

# macOS python.org builds often ship without CA certs wired up, causing
# CERTIFICATE_VERIFY_FAILED. Prefer certifi if present; otherwise fall back to
# an unverified context (fine for reading public, non-sensitive Reddit JSON).
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CTX = ssl._create_unverified_context()

# A descriptive, unique User-Agent is required or Reddit returns 429/403.
USER_AGENT = "python:takemeter-collector:v1.0 (educational AI201 project; contact sidhdharth19pandya@gmail.com)"

BOT_AUTHORS = {"automoderator", "houseofthedragon-modteam", "[deleted]"}
SKIP_BODIES = {"[deleted]", "[removed]", ""}


def fetch_json(url, retries=4, backoff=3.0):
    """GET a Reddit .json URL, retrying on rate limits / transient errors."""
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 500, 502, 503) and attempt < retries - 1:
                wait = backoff * (attempt + 1)
                print(f"  HTTP {e.code} on {url} — backing off {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  HTTP {e.code} (giving up): {url}", file=sys.stderr)
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt < retries - 1:
                time.sleep(backoff)
                continue
            print(f"  Network error (giving up): {e}", file=sys.stderr)
            return None
    return None


def get_submission_ids(subreddit, listing, time_filter, pages, sleep):
    """Page through a subreddit listing (top/hot/new) and collect post IDs."""
    ids = []
    after = None
    for page in range(pages):
        url = (
            f"https://www.reddit.com/r/{subreddit}/{listing}.json"
            f"?limit=100&t={time_filter}"
        )
        if after:
            url += f"&after={after}"
        data = fetch_json(url)
        if not data or "data" not in data:
            break
        children = data["data"].get("children", [])
        for c in children:
            d = c.get("data", {})
            if d.get("id"):
                ids.append((d["id"], d.get("title", "")))
        after = data["data"].get("after")
        print(f"  [{listing}] page {page + 1}: +{len(children)} posts", file=sys.stderr)
        if not after:
            break
        time.sleep(sleep)
    return ids


def walk_comments(node, out):
    """Recursively pull comment bodies (kind == 't1') from a comment tree."""
    if not isinstance(node, dict):
        return
    kind = node.get("kind")
    data = node.get("data", {})
    if kind == "t1":
        author = (data.get("author") or "").lower()
        body = (data.get("body") or "").strip()
        if author not in BOT_AUTHORS and body not in SKIP_BODIES:
            out.append({"text": body, "author": author, "score": data.get("score", 0)})
    replies = data.get("replies")
    if isinstance(replies, dict):
        for child in replies.get("data", {}).get("children", []):
            walk_comments(child, out)


def get_comments(submission_id, max_per_thread, sleep):
    """Fetch and flatten all comments for one submission."""
    url = f"https://www.reddit.com/comments/{submission_id}.json?limit=500&depth=10"
    data = fetch_json(url)
    time.sleep(sleep)
    if not data or len(data) < 2:
        return []
    out = []
    for child in data[1].get("data", {}).get("children", []):
        walk_comments(child, out)
    # Prefer higher-scored comments (more representative of community discourse)
    out.sort(key=lambda c: c.get("score", 0), reverse=True)
    return out[:max_per_thread]


def clean(text):
    """Collapse whitespace/newlines so each comment is one tidy CSV cell."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&lt;", "<", text)
    return text


def is_usable(text, min_len, max_len):
    if not (min_len <= len(text) <= max_len):
        return False
    # Drop link-dump / quote-only / single-emoji comments
    if text.count("http") >= 2:
        return False
    letters = sum(c.isalpha() for c in text)
    if letters < min_len * 0.4:
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subreddit", default="HouseOfTheDragon")
    ap.add_argument("--listings", nargs="+", default=["top", "hot"],
                    help="Which listings to crawl (top hot new)")
    ap.add_argument("--time", default="all", choices=["all", "year", "month", "week"],
                    help="Time filter for 'top' listing")
    ap.add_argument("--pages", type=int, default=2, help="Listing pages per source (~100 posts each)")
    ap.add_argument("--max-per-thread", type=int, default=25, help="Top-scored comments to keep per post")
    ap.add_argument("--min-len", type=int, default=40)
    ap.add_argument("--max-len", type=int, default=600)
    ap.add_argument("--target", type=int, default=400, help="Stop once this many unique candidates collected")
    ap.add_argument("--sleep", type=float, default=2.0, help="Seconds between requests (be polite)")
    ap.add_argument("--out", default="data/raw_candidates.csv")
    args = ap.parse_args()

    print(f"Collecting candidates from r/{args.subreddit} ...", file=sys.stderr)

    # 1. Gather submission IDs across the requested listings.
    submissions = []
    seen_ids = set()
    for listing in args.listings:
        for sid, title in get_submission_ids(args.subreddit, listing, args.time, args.pages, args.sleep):
            if sid not in seen_ids:
                seen_ids.add(sid)
                submissions.append((sid, title))
    print(f"Found {len(submissions)} unique posts. Pulling comments ...", file=sys.stderr)

    # 2. Pull + filter comments until we hit the target.
    rows = []
    seen_text = set()
    for i, (sid, title) in enumerate(submissions):
        if len(rows) >= args.target:
            break
        comments = get_comments(sid, args.max_per_thread, args.sleep)
        kept = 0
        for c in comments:
            text = clean(c["text"])
            key = text.lower()[:120]
            if key in seen_text or not is_usable(text, args.min_len, args.max_len):
                continue
            seen_text.add(key)
            rows.append({"text": text, "label": "", "notes": "", "source_post": title[:80]})
            kept += 1
        print(f"  ({i + 1}/{len(submissions)}) {title[:50]!r}: kept {kept} | total {len(rows)}",
              file=sys.stderr)

    # 3. Write CSV.
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "notes", "source_post"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Wrote {len(rows)} candidate comments to {args.out}", file=sys.stderr)
    print("Next: open the CSV and fill the `label` column with one of:", file=sys.stderr)
    print("  lore_analysis | faction_cheerleading | visceral_reaction", file=sys.stderr)


if __name__ == "__main__":
    main()
