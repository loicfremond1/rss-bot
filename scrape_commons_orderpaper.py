import datetime
import email.utils
import html
import re
import sys
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

SITE_TITLE = "UK Parliament - Commons Order Paper"
SITE_LINK = "https://commonsbusiness.parliament.uk/search?DocumentTypeId=1&EndDate=&SearchTerm=&StartDate="
BASE_URL = "https://commonsbusiness.parliament.uk"
FEED_FILE = "feed_commons_orderpaper.xml"

MAX_ITEMS = 20
TIMEOUT_SECONDS = 60

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

TAG_RE = re.compile(r"<[^>]+>")


def build_search_url(page: int = 1) -> str:
    params = [
        ("DocumentTypeId", "1"),
        ("EndDate", ""),
        ("SearchTerm", ""),
        ("StartDate", ""),
    ]
    if page > 1:
        params.append(("page", str(page)))
    return f"{BASE_URL}/search?{urlencode(params)}"


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        text = response.read().decode("utf-8", errors="replace")
    if "<title>Just a moment" in text or "Enable JavaScript and cookies to continue" in text:
        raise RuntimeError("Commons business papers returned a challenge page")
    return text


def fetch_with_retry(url: str, attempts: int = 2) -> str:
    last_err = None
    for i in range(attempts):
        try:
            return fetch_html(url)
        except (OSError, URLError, UnicodeDecodeError, RuntimeError) as e:
            last_err = e
            print(f"Attempt {i + 1} failed: {e}", flush=True)
    raise last_err


def clean(value: str) -> str:
    return " ".join((value or "").split())


def clean_fragment(fragment: str) -> str:
    return clean(html.unescape(TAG_RE.sub(" ", fragment)))


def first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def absolute_url(path: str) -> str:
    return urljoin(f"{BASE_URL}/", html.unescape(path or ""))


def parse_date(value: str) -> datetime.datetime | None:
    cleaned = clean(value)
    if not cleaned:
        return None
    for date_format in ("%A %d %B %Y", "%d %B %Y"):
        try:
            parsed = datetime.datetime.strptime(cleaned, date_format)
            return parsed.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    print(f"Skipping unrecognised date: {cleaned}", flush=True)
    return None


def parse_card(card_html: str) -> dict | None:
    primary = clean_fragment(first_match(r'<div class="primary-info">\s*(.*?)\s*</div>', card_html))
    item_type = clean_fragment(first_match(r'<span class="item item-type">\s*(.*?)\s*</span>', card_html))
    if primary != "Order Paper" or item_type != "Order Paper":
        return None

    date_text = clean_fragment(first_match(r'<span class="item item-date">\s*(.*?)\s*</span>', card_html))
    description = clean_fragment(first_match(r'<div class="text">\s*(.*?)\s*</div>', card_html))
    html_path = first_match(r'href="([^"]*Document/\d+/Html\?subType=Standard)"', card_html)
    pdf_path = first_match(r'href="([^"]*Document/\d+/Pdf\?subType=Standard)"', card_html)
    link = absolute_url(html_path or pdf_path)
    if not link:
        return None

    item = {
        "title": f"Order Paper - {date_text}" if date_text else "Order Paper",
        "link": link,
        "description": description,
    }
    pdf_url = absolute_url(pdf_path) if pdf_path else ""
    if pdf_url and pdf_url != link:
        item["description"] = clean(f"{description} PDF: {pdf_url}")

    published = parse_date(date_text)
    if published:
        item["pubDate"] = email.utils.format_datetime(published)
    return item


def build_items() -> list[dict]:
    items = []
    seen = set()

    for page in range(1, 5):
        page_html = fetch_with_retry(build_search_url(page))
        cards = page_html.split('<div class="card card-document card-document-standalone">')[1:]
        if not cards:
            break

        for card_html in cards:
            item = parse_card(card_html)
            if not item or item["link"] in seen:
                continue
            items.append(item)
            seen.add(item["link"])
            if len(items) >= MAX_ITEMS:
                return items

    return items


def rss2(items: list[dict]) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    now_http = email.utils.format_datetime(now)
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<rss version="2.0">')
    out.append("<channel>")
    out.append(f"<title>{html.escape(SITE_TITLE)}</title>")
    out.append(f"<link>{html.escape(SITE_LINK)}</link>")
    out.append("<description>Custom RSS feed for the UK Parliament House of Commons Order Paper</description>")
    out.append(f"<lastBuildDate>{now_http}</lastBuildDate>")
    for item in items:
        out.append("<item>")
        out.append(f"<title>{html.escape(item['title'])}</title>")
        out.append(f"<link>{html.escape(item['link'])}</link>")
        out.append(f"<guid isPermaLink='true'>{html.escape(item['link'])}</guid>")
        if item.get("description"):
            out.append(f"<description>{html.escape(item['description'])}</description>")
        if item.get("pubDate"):
            out.append(f"<pubDate>{item['pubDate']}</pubDate>")
        out.append("</item>")
    out.append("</channel></rss>")
    return "\n".join(out)


def main() -> None:
    items = build_items()
    if not items:
        print(f"ERROR: 0 items scraped from {SITE_LINK} - leaving existing feed unchanged", flush=True)
        sys.exit(1)
    print(f"Scraped {len(items)} items", flush=True)
    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss2(items))


if __name__ == "__main__":
    main()
