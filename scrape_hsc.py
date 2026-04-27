# scrape_hsc.py
import datetime, html, sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SITE_TITLE = "Health and Social Care Committee — News"
SITE_LINK  = "https://committees.parliament.uk/committee/81/health-and-social-care-committee/news/"
START_URL  = SITE_LINK
FEED_FILE  = "feed_hsc.xml"

SELECTOR_ITEM    = "a.card"
SELECTOR_TITLE   = ".primary-info"
SELECTOR_SUMMARY = ".text"
MAX_ITEMS = 20

def fetch_html_with_browser(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0 Safari/537.36"),
                locale="en-GB",
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("a.card", timeout=60000)
            return page.content()
        finally:
            context.close()
            browser.close()

def fetch_with_retry(url: str, attempts: int = 2) -> str:
    last_err = None
    for i in range(attempts):
        try:
            return fetch_html_with_browser(url)
        except Exception as e:
            last_err = e
            print(f"Attempt {i + 1} failed: {e}", flush=True)
    raise last_err

def clean(s):
    return " ".join((s or "").split())

def build_items(html_text, base_url):
    soup = BeautifulSoup(html_text, "lxml")
    items = []
    for card in soup.select(SELECTOR_ITEM)[:MAX_ITEMS]:
        href = card.get("href")
        if not href:
            continue
        link = urljoin(base_url, href)
        title_el = card.select_one(SELECTOR_TITLE)
        title = clean(title_el.get_text(" ", strip=True) if title_el else card.get_text(" ", strip=True))
        summary_el = card.select_one(SELECTOR_SUMMARY)
        summary = clean(summary_el.get_text(" ", strip=True) if summary_el else "")
        pub_http = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        items.append({"title": title or link, "link": link, "description": summary, "pubDate": pub_http})
    return items

def rss2(items):
    now_http = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<rss version="2.0">')
    out.append('<channel>')
    out.append(f"<title>{html.escape(SITE_TITLE)}</title>")
    out.append(f"<link>{html.escape(SITE_LINK)}</link>")
    out.append("<description>Custom RSS feed</description>")
    out.append(f"<lastBuildDate>{now_http}</lastBuildDate>")
    for it in items:
        out.append("<item>")
        out.append(f"<title>{html.escape(it['title'])}</title>")
        out.append(f"<link>{html.escape(it['link'])}</link>")
        out.append(f"<guid isPermaLink='true'>{html.escape(it['link'])}</guid>")
        if it.get("description"):
            out.append(f"<description>{html.escape(it['description'])}</description>")
        out.append(f"<pubDate>{it['pubDate']}</pubDate>")
        out.append("</item>")
    out.append("</channel></rss>")
    return "\n".join(out)

def main():
    html_text = fetch_with_retry(START_URL)
    items = build_items(html_text, START_URL)
    if not items:
        print(f"ERROR: 0 items scraped from {START_URL} — leaving existing feed unchanged", flush=True)
        sys.exit(1)
    print(f"Scraped {len(items)} items", flush=True)
    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss2(items))

if __name__ == "__main__":
    main()
