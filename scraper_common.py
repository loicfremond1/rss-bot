import datetime
import html
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def utc_http_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def fetch_html_with_browser(url: str, wait_selector: str = "div.card-list") -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            locale="en-GB",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(wait_selector, timeout=30000)
        html_text = page.content()
        context.close()
        browser.close()
        return html_text


def clean(text: str) -> str:
    return " ".join((text or "").split())


def build_items_from_html(
    html_text: str,
    base_url: str,
    selector_item: str,
    selector_title: str,
    selector_summary: str,
    max_items: int,
):
    soup = BeautifulSoup(html_text, "lxml")
    items = []
    for card in soup.select(selector_item)[:max_items]:
        href = card.get("href")
        if not href:
            continue

        link = urljoin(base_url, href)
        title_el = card.select_one(selector_title)
        title = clean(
            title_el.get_text(" ", strip=True) if title_el else card.get_text(" ", strip=True)
        )
        summary_el = card.select_one(selector_summary)
        summary = clean(summary_el.get_text(" ", strip=True) if summary_el else "")

        items.append(
            {
                "title": title or link,
                "link": link,
                "description": summary,
                "pubDate": utc_http_date(),
            }
        )
    return items


def rss2(site_title: str, site_link: str, items, description: str = "Custom RSS feed") -> str:
    now_http = utc_http_date()
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '<channel>',
        f"<title>{html.escape(site_title)}</title>",
        f"<link>{html.escape(site_link)}</link>",
        f"<description>{html.escape(description)}</description>",
        f"<lastBuildDate>{now_http}</lastBuildDate>",
    ]

    for item in items:
        out.append("<item>")
        out.append(f"<title>{html.escape(item['title'])}</title>")
        out.append(f"<link>{html.escape(item['link'])}</link>")
        out.append(f"<guid isPermaLink='true'>{html.escape(item['link'])}</guid>")
        if item.get("description"):
            out.append(f"<description>{html.escape(item['description'])}</description>")
        out.append(f"<pubDate>{item['pubDate']}</pubDate>")
        out.append("</item>")

    out.append("</channel></rss>")
    return "\n".join(out)
