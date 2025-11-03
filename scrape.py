# scrape.py
import datetime, html, sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SITE_TITLE = "Science, Innovation and Technology Committee — News"
SITE_LINK  = "https://committees.parliament.uk/committee/135/science-innovation-and-technology-committee/news/"
START_URL  = SITE_LINK

SELECTOR_ITEM    = "div.card-list a.card"
SELECTOR_TITLE   = ".primary-info"
SELECTOR_SUMMARY = ".text"
MAX_ITEMS = 20

def fetch_html_with_browser(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="en-GB",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        # Wait for the list of cards to be present
        page.wait_for_selector("div.card-list", timeout=30000)
        html_text = page.content()
        context.close()
        browser.close()
        return html_text

def clean(s): return " ".join((s or "").split())

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

        pub_http = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        items.append({"title": title or link, "link": link, "description": summary, "pubDate": pub_http})
    return items

def rss2(items):
    now_http = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<rss version="2.0">')
    out.append('<channel>')
    out.append(f"<title>{html.escape(SITE_TITLE)}</title>")
    out.append(f"<link>{html.escape(SITE_LINK)}</link>")
    out.append(f"<description>Custom RSS feed</description>")
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
    html_text = fetch_html_with_browser(START_URL)
    items = build_items(html_text, START_URL)
    xml = rss2(items)
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(xml)

if __name__ == "__main__":
    main()
