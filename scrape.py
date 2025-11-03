# scrape.py
import datetime, html
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# ---- CONFIG (set for UK Parliament committee news) ----
SITE_TITLE = "Science, Innovation and Technology Committee — News"
SITE_LINK  = "https://committees.parliament.uk/committee/135/science-innovation-and-technology-committee/news/"
START_URL  = SITE_LINK

# Each article lives in an <a class="card ..."> inside <div class="card-list">
SELECTOR_ITEM    = "div.card-list a.card"
# The <a> tag itself has the href
SELECTOR_LINK    = None
# Title text appears in <div class='primary-info'> inside the card
SELECTOR_TITLE   = ".primary-info"
# Short blurb appears in <div class='text'> inside the card
SELECTOR_SUMMARY = ".text"

MAX_ITEMS = 20
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; custom-rss/1.0)"}
# -------------------------------------------------------

def fetch_html(url):
    r = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def clean_text(s):
    return " ".join((s or "").split())

def build_items(html_text, base_url):
    soup = BeautifulSoup(html_text, "lxml")
    items = []
    for card in soup.select(SELECTOR_ITEM)[:MAX_ITEMS]:
        # link
        href = card.get("href") if SELECTOR_LINK is None else (
            card.select_one(SELECTOR_LINK).get("href") if card.select_one(SELECTOR_LINK) else None
        )
        if not href:
            continue
        link = urljoin(base_url, href)

        # title
        title_el = card.select_one(SELECTOR_TITLE)
        # Fallback: if selector fails, use the card's text
        title = clean_text(title_el.get_text(strip=True) if title_el else card.get_text(" ", strip=True))

        # summary
        summary_el = card.select_one(SELECTOR_SUMMARY)
        summary = clean_text(summary_el.get_text(" ", strip=True) if summary_el else "")

        # pubDate: use current UTC (page does not expose per-item dates on the list reliably)
        pub_http = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

        items.append({
            "title": title or link,
            "link": link,
            "description": summary,
            "pubDate": pub_http
        })
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
    html_text = fetch_html(START_URL)
    items = build_items(html_text, START_URL)
    xml = rss2(items)
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(xml)

if __name__ == "__main__":
    main()
