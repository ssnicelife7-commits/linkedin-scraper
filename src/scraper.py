"""
LinkedIn Post Engager Scraper
Collects likers and commenters from LinkedIn posts using a persistent browser session.
"""

import asyncio
import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import yaml
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"
COOKIES_PATH = ROOT / "cookies" / "linkedin_cookies.json"
PROFILE_DIR = ROOT / "browser_profile"
INPUT_PATH = ROOT / "input" / "post_urls.csv"
OUTPUT_DIR = ROOT / "output"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_post_urls():
    if not INPUT_PATH.exists():
        print(f"\n[ERROR] Input file not found at:\n  {INPUT_PATH}")
        print("\nAdd your post URLs to input/post_urls.csv")
        sys.exit(1)
    rows = []
    with open(INPUT_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = row.get("post_url", "").strip()
            if url and not url.startswith("http") is False and "example" not in url:
                rows.append({
                    "post_url": url,
                    "competitor": row.get("competitor", "unknown").strip(),
                })
    if not rows:
        print("\n[ERROR] No valid URLs found in input/post_urls.csv")
        print("Make sure each row has a real LinkedIn post URL in the post_url column.")
        sys.exit(1)
    return rows


def mark_urls_done(urls_done):
    """Overwrite input CSV, moving processed URLs to a done column."""
    all_rows = []
    with open(INPUT_PATH, newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    done_set = {u["post_url"] for u in urls_done}
    for row in all_rows:
        if row.get("post_url", "").strip() in done_set:
            row["status"] = "done"

    fieldnames = list(all_rows[0].keys()) if all_rows else []
    if "status" not in fieldnames:
        fieldnames.append("status")

    with open(INPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)


def save_engagers(engagers, session_id):
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / f"engagers_{session_id}.csv"
    fieldnames = ["name", "profile_url", "headline", "engagement_type",
                  "post_url", "competitor", "scraped_at"]
    write_header = not output_file.exists()
    with open(output_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(engagers)
    return output_file


async def human_delay(min_sec=2.0, max_sec=5.0):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def scroll_element(page, selector, amount=400):
    try:
        await page.evaluate(
            f'(s) => {{ const el = document.querySelector(s); if (el) el.scrollTop += {amount}; }}',
            selector,
        )
    except Exception:
        pass


# ── Session setup ─────────────────────────────────────────────────────────────────

async def import_cookies_if_present(context):
    """Import cookies from linkedin_cookies.json, clearing stale LinkedIn cookies first."""
    if not COOKIES_PATH.exists():
        print(f"[i] No cookies file found at cookies\\linkedin_cookies.json")
        print(f"    Using existing browser profile session.")
        return
    print(f"[*] Found cookies file — clearing stale session and importing...")
    with open(COOKIES_PATH, encoding="utf-8") as f:
        cookies = json.load(f)
    for c in cookies:
        if c.get("sameSite") not in {"Strict", "Lax", "None"}:
            c["sameSite"] = "None"
    # Wipe all existing cookies so stale LinkedIn session can't override the fresh ones
    await context.clear_cookies()
    await context.add_cookies(cookies)
    imported_path = COOKIES_PATH.with_suffix(".json.imported")
    COOKIES_PATH.rename(imported_path)
    print(f"[+] {len(cookies)} cookies imported. File renamed to: {imported_path.name}\n")


# ── Reactions (likers) ────────────────────────────────────────────────────────

REACTION_BTN_SELECTORS = [
    "button:has(span.social-detail-social-counts_reactions-count)",
    "span.social-detail-social-counts_reactions-count",
    "button.social-details-social-counts__reactions-count",
    "button[aria-label*='reaction']",
    "span.social-details-social-counts__reactions-count",
    ".social-details-social-counts__reactions button",
    "button.feed-shared-social-actions__reactions-count",
]

MODAL_CONTENT_SELECTORS = [
    "div.artdeco-modal__content",
    "div.social-details-reactors-modal__content",
    ".social-details-reactors-tab-body-list",
]

MODAL_PROFILE_LINK_SELECTOR = "div.artdeco-modal__content a[href*='/in/']"

HEADLINE_SELECTORS_IN_MODAL = [
    ".artdeco-entity-lockup__caption",
    ".artdeco-entity-lockup__subtitle",
    ".social-details-reactors-tab-body-list__lockup .artdeco-entity-lockup__caption",
]


async def scrape_reactions(page, config):
    likers = []

    reactions_btn = None
    for sel in REACTION_BTN_SELECTORS:
        try:
            btn = await page.wait_for_selector(sel, timeout=4000)
            if btn and await btn.is_visible():
                reactions_btn = btn
                break
        except PlaywrightTimeout:
            continue

    if not reactions_btn:
        print("  [!] No reactions button found — post may have 0 reactions or selector changed")
        return likers

    await reactions_btn.click()
    await human_delay(2, 4)

    modal_found = False
    for sel in MODAL_CONTENT_SELECTORS:
        try:
            await page.wait_for_selector(sel, timeout=7000)
            modal_found = True
            break
        except PlaywrightTimeout:
            continue

    if not modal_found:
        print("  [!] Reactions modal did not open")
        await page.keyboard.press("Escape")
        return likers

    print("  [+] Reactions modal open — scrolling through likers...")

    max_scrolls = config.get("max_reaction_scrolls", 25)
    prev_count = -1

    for scroll_num in range(max_scrolls):
        links = await page.query_selector_all(MODAL_PROFILE_LINK_SELECTOR)
        seen_urls = {e["profile_url"] for e in likers}

        for link in links:
            try:
                href = (await link.get_attribute("href") or "").split("?")[0].rstrip("/")
                if "/in/" not in href or href in seen_urls:
                    continue

                name = (await link.inner_text()).strip()
                if not name:
                    continue

                headline = ""
                try:
                    li_parent = await link.evaluate_handle(
                        "el => el.closest('li') || el.parentElement"
                    )
                    for hl_sel in HEADLINE_SELECTORS_IN_MODAL:
                        hl_el = await li_parent.query_selector(hl_sel)
                        if hl_el:
                            headline = (await hl_el.inner_text()).strip()
                            break
                except Exception:
                    pass

                profile_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
                likers.append({
                    "name": name,
                    "profile_url": profile_url,
                    "headline": headline,
                    "engagement_type": "like",
                })
                seen_urls.add(href)
            except Exception:
                continue

        current = len(likers)
        if current == prev_count and scroll_num > 2:
            print(f"  [+] End of likers list ({current} found)")
            break
        prev_count = current

        modal_sel = MODAL_CONTENT_SELECTORS[0]
        await scroll_element(page, modal_sel, 400)
        await human_delay(1.0, 2.5)

    try:
        close = await page.query_selector("button.artdeco-modal__dismiss")
        if close:
            await close.click()
        else:
            await page.keyboard.press("Escape")
        await human_delay(1, 2)
    except Exception:
        await page.keyboard.press("Escape")

    return likers


# ── Comments ──────────────────────────────────────────────────────────────────

LOAD_MORE_SELECTORS = [
    "button.comments-comments-list__load-more-comments-button",
    "button[aria-label*='Load more comments']",
    "button.comments-comments-list__show-previous-button",
]

COMMENT_AUTHOR_SELECTORS = [
    "article.comments-comment-entity a[href*='/in/']",
    ".comments-comment-item .comments-post-meta a[href*='/in/']",
    ".comment-item__author a[href*='/in/']",
    "a.comments-post-meta__name--multi-line[href*='/in/']",
]

COMMENT_HEADLINE_SELECTORS = [
    ".comments-post-meta__headline",
    ".artdeco-entity-lockup__caption",
]


async def scrape_comments(page, config):
    commenters = []
    max_load_more = config.get("max_load_more_clicks", 10)

    for _ in range(max_load_more):
        clicked = False
        for sel in LOAD_MORE_SELECTORS:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await human_delay(2, 4)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            break

    seen_urls = set()

    for sel in COMMENT_AUTHOR_SELECTORS:
        links = await page.query_selector_all(sel)
        if not links:
            continue

        for link in links:
            try:
                href = (await link.get_attribute("href") or "").split("?")[0].rstrip("/")
                if "/in/" not in href or href in seen_urls:
                    continue

                name = (await link.inner_text()).strip()
                if not name:
                    continue

                headline = ""
                try:
                    article = await link.evaluate_handle(
                        "el => el.closest('article') || el.closest('.comments-comment-entity')"
                    )
                    for hl_sel in COMMENT_HEADLINE_SELECTORS:
                        hl_el = await article.query_selector(hl_sel)
                        if hl_el:
                            headline = (await hl_el.inner_text()).strip()
                            break
                except Exception:
                    pass

                profile_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
                commenters.append({
                    "name": name,
                    "profile_url": profile_url,
                    "headline": headline,
                    "engagement_type": "comment",
                })
                seen_urls.add(href)
            except Exception:
                continue

        if commenters:
            break

    return commenters


# ── Per-post orchestration ────────────────────────────────────────────────────

def clean_url(url: str) -> str:
    """Strip UTM/tracking params — they trigger redirect chains that stall Playwright."""
    return url.split("?")[0].rstrip("/")


async def navigate_to_post(page, url: str) -> bool:
    """Navigate to a post page with one retry. Returns True if successful."""
    for attempt in range(2):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return True
        except PlaywrightTimeout:
            if attempt == 0:
                print(f"  [~] Navigation timeout, retrying...")
                await human_delay(3, 5)
    return False


async def scrape_post(page, post_info, config):
    raw_url = post_info["post_url"]
    url = clean_url(raw_url)
    competitor = post_info.get("competitor", "unknown")

    print(f"\n[>] {url}")
    print(f"    Competitor: {competitor}")

    try:
        if not await navigate_to_post(page, url):
            print(f"  [!] Could not load post page after retry — skipping")
            return []

        await human_delay(3, 6)
        await page.mouse.wheel(0, random.randint(200, 500))
        await human_delay(2, 4)

        print("  [*] Collecting likers...")
        likers = await scrape_reactions(page, config)
        print(f"      → {len(likers)} likers")

        await human_delay(3, 6)

        print("  [*] Collecting commenters...")
        commenters = await scrape_comments(page, config)
        print(f"      → {len(commenters)} commenters")

        ts = datetime.utcnow().isoformat()
        engagers = []
        for e in likers + commenters:
            e["post_url"] = url
            e["competitor"] = competitor
            e["scraped_at"] = ts
            engagers.append(e)

        print(f"  [=] Total from this post: {len(engagers)}")
        return engagers

    except Exception as exc:
        print(f"  [!] Failed: {exc}")
        return []


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    config = load_config()
    all_urls = load_post_urls()

    pending = [r for r in all_urls if r.get("status", "").lower() != "done"]
    max_posts = config.get("max_posts_per_session", 30)
    batch = pending[:max_posts]

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f" LinkedIn Engager Scraper  |  Session {session_id}")
    print(f" Posts this session : {len(batch)}  (total pending: {len(pending)})")
    print(f" Delay between posts: {config['delay_min_sec']}–{config['delay_max_sec']}s")
    print(f"{'='*60}\n")

    if not batch:
        print("Nothing to scrape — all URLs in post_urls.csv are marked done.")
        return

    proxy_url = config.get("proxy", "").strip()
    launch_kwargs = {"proxy": {"server": proxy_url}} if proxy_url else {}

    PROFILE_DIR.mkdir(exist_ok=True)

    done_posts = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            slow_mo=50,
            args=["--start-maximized"],
            user_agent=config.get("user_agent"),
            viewport={"width": 1280, "height": 800},
            **launch_kwargs,
        )

        await import_cookies_if_present(context)

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        print("[*] Checking LinkedIn session...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await human_delay(3, 5)

        current_url = page.url
        print(f"[i] Landed on: {current_url}")

        if "login" in current_url or "checkpoint" in current_url or "/uas/" in current_url:
            print("\n[ERROR] Session not recognised.")
            print("Export fresh cookies from Opera using Cookie-Editor,")
            print("save as cookies\\linkedin_cookies.json, then run again.\n")
            await context.close()
            return

        print("[+] Session active. Starting...\n")

        for i, post_info in enumerate(batch):
            engagers = await scrape_post(page, post_info, config)

            if engagers:
                out = save_engagers(engagers, session_id)
                print(f"  [saved → {out.name}]")

            done_posts.append(post_info)

            if i < len(batch) - 1:
                wait = random.uniform(config["delay_min_sec"], config["delay_max_sec"])
                print(f"\n[~] Waiting {wait:.0f}s before next post...")
                await asyncio.sleep(wait)

        await context.close()

    mark_urls_done(done_posts)

    remaining = len(pending) - len(batch)

    print(f"\n{'='*60}")
    print(f" Done! Session saved to: output/engagers_{session_id}.csv")
    print(f" Posts remaining in queue: {remaining}")
    if remaining > 0:
        print(f" Run the scraper again to process the next {min(max_posts, remaining)} posts.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
