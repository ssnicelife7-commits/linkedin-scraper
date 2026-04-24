"""
Deduplicator + Engagement Scorer
Merges all session CSVs, deduplicates by profile, and ranks by engagement strength.
Run this after all scraping sessions are done to get your Apollo-ready export.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"


def load_all_sessions():
    session_files = sorted(OUTPUT_DIR.glob("engagers_*.csv"))
    if not session_files:
        print(f"\n[ERROR] No engager files found in {OUTPUT_DIR}")
        print("Run the scraper first.")
        sys.exit(1)

    all_rows = []
    for f in session_files:
        with open(f, newline="", encoding="utf-8") as fh:
            all_rows.extend(list(csv.DictReader(fh)))

    print(f"[+] Loaded {len(all_rows)} raw rows from {len(session_files)} session file(s)")
    return all_rows


def deduplicate_and_score(rows):
    """
    Group by profile_url. For each person, track:
    - total engagements (likes + comments across all posts)
    - unique competitors engaged with
    - unique posts engaged with
    - engagement types seen
    """
    by_profile = defaultdict(lambda: {
        "name": "",
        "profile_url": "",
        "headline": "",
        "posts": set(),
        "competitors": set(),
        "engagement_types": set(),
        "total_engagements": 0,
    })

    for row in rows:
        url = row.get("profile_url", "").strip()
        if not url:
            continue

        p = by_profile[url]
        p["profile_url"] = url
        # Keep the most recent / non-empty name and headline
        if row.get("name"):
            p["name"] = row["name"]
        if row.get("headline"):
            p["headline"] = row["headline"]
        p["posts"].add(row.get("post_url", ""))
        p["competitors"].add(row.get("competitor", ""))
        p["engagement_types"].add(row.get("engagement_type", ""))
        p["total_engagements"] += 1

    return by_profile


def compute_score(p):
    """
    Simple engagement score:
    - Each engagement = 1 point
    - Each additional competitor = +3 bonus (cross-competitor signal is valuable)
    - Comment = slightly higher weight than like
    """
    base = p["total_engagements"]
    competitor_bonus = (len(p["competitors"]) - 1) * 3
    comment_bonus = 1 if "comment" in p["engagement_types"] else 0
    return base + competitor_bonus + comment_bonus


def export(by_profile, output_path):
    scored = []
    for url, p in by_profile.items():
        scored.append({
            "name": p["name"],
            "profile_url": url,
            "headline": p["headline"],
            "total_engagements": p["total_engagements"],
            "unique_posts_engaged": len(p["posts"]),
            "unique_competitors_engaged": len(p["competitors"]),
            "competitors_list": " | ".join(sorted(p["competitors"])),
            "engagement_types": " + ".join(sorted(p["engagement_types"])),
            "engagement_score": compute_score(p),
        })

    scored.sort(key=lambda x: x["engagement_score"], reverse=True)

    fieldnames = [
        "name", "profile_url", "headline",
        "engagement_score", "total_engagements",
        "unique_posts_engaged", "unique_competitors_engaged",
        "competitors_list", "engagement_types",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored)

    return scored


def main():
    rows = load_all_sessions()
    by_profile = deduplicate_and_score(rows)

    output_path = OUTPUT_DIR / "FINAL_engagers_ranked.csv"
    scored = export(by_profile, output_path)

    top10 = scored[:10]

    print(f"\n{'='*60}")
    print(f" Deduplication complete")
    print(f" Unique people found : {len(scored)}")
    print(f" Output file         : output/FINAL_engagers_ranked.csv")
    print(f"\n Top 10 by engagement score:")
    print(f"{'='*60}")
    print(f" {'Name':<30} {'Score':>6}  {'Posts':>5}  {'Competitors':>11}")
    print(f" {'-'*30} {'-'*6}  {'-'*5}  {'-'*11}")
    for p in top10:
        print(f" {p['name'][:30]:<30} {p['engagement_score']:>6}  "
              f"{p['unique_posts_engaged']:>5}  {p['unique_competitors_engaged']:>11}")
    print(f"{'='*60}")
    print(f"\n Ready to upload to Apollo: output/FINAL_engagers_ranked.csv\n")


if __name__ == "__main__":
    main()
