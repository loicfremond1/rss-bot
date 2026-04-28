import datetime
import email.utils
import html
import json
import re
import sys
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SITE_TITLE = "The NHS Alliance - News"
SITE_LINK = "https://thenhsalliance.org/news?page=1"
BASE_URL = "https://thenhsalliance.org"
FEED_FILE = "feed_nhsalliance.xml"

PAGE_ID_FALLBACK = "ab85dc15-4664-4bb0-9b8f-4749227077e7"
LISTING_ACTION_FALLBACK = "47843f0ca49e9b1aa5eb38c23c081f96ab0397fd"

MAX_ITEMS = 20
PAGE_SIZE = 20
TIMEOUT_SECONDS = 60

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def request_text(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> str:
    request_headers = {
        "Accept": "*/*",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)
    req = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def fetch_with_retry(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    attempts: int = 2,
) -> str:
    last_err = None
    for i in range(attempts):
        try:
            return request_text(url, method=method, headers=headers, body=body)
        except (OSError, URLError, UnicodeDecodeError) as e:
            last_err = e
            print(f"Attempt {i + 1} failed for {url}: {e}", flush=True)
    raise last_err


def clean(value: object) -> str:
    if not isinstance(value, str) or value == "$undefined":
        return ""
    return " ".join(value.split())


def discover_page_id(page_html: str) -> str:
    for pattern in (
        r'pageId\\?":\\?"([0-9a-f-]{36})',
        r'data-id\\?":\\?"([0-9a-f-]{36})',
    ):
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return PAGE_ID_FALLBACK


def script_urls(page_html: str) -> list[str]:
    urls = []
    seen = set()
    for match in re.finditer(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', page_html):
        url = urljoin(BASE_URL, match.group(1))
        if "/_next/static/chunks/" in url and url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def discover_listing_action_id(page_html: str) -> str:
    action_pattern = re.compile(
        r'eL:function\(\)\{return r\}[\s\S]{0,1600}?'
        r'var r=\(0,[^)]+?\)\("([0-9a-f]{32,})"\)'
    )
    for url in script_urls(page_html):
        try:
            script = fetch_with_retry(url)
        except (OSError, URLError, UnicodeDecodeError) as e:
            print(f"Skipping action discovery chunk {url}: {e}", flush=True)
            continue
        match = action_pattern.search(script)
        if match:
            return match.group(1)
    return LISTING_ACTION_FALLBACK


def listing_request_body(page_id: str) -> bytes:
    return json.dumps([1, page_id, PAGE_SIZE, [], "news"], separators=(",", ":")).encode("utf-8")


def fetch_listing(action_id: str, page_id: str) -> list[dict]:
    response = fetch_with_retry(
        SITE_LINK,
        method="POST",
        headers={
            "Accept": "text/x-component",
            "Content-Type": "text/plain;charset=UTF-8",
            "Next-Action": action_id,
            "Origin": BASE_URL,
            "Referer": SITE_LINK,
        },
        body=listing_request_body(page_id),
    )
    for line in response.splitlines():
        if not line.startswith("1:"):
            continue
        payload = json.loads(line[2:])
        return (payload.get("cards") or {}).get("items") or []
    raise ValueError("Could not find listing payload in NHS Alliance response")


def parse_date(value: str) -> datetime.datetime | None:
    cleaned = clean(value)
    if not cleaned:
        return None
    for date_format in ("%d %b %Y", "%d %B %Y"):
        try:
            parsed = datetime.datetime.strptime(cleaned, date_format)
            return parsed.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    print(f"Skipping unrecognised date: {cleaned}", flush=True)
    return None


def parse_item(entry: dict) -> dict | None:
    props = entry.get("props") or {}
    title = clean(props.get("title"))
    path = clean(props.get("url"))
    if not title or not path:
        return None

    published = parse_date(props.get("date"))
    item = {
        "title": title,
        "link": urljoin(BASE_URL, path),
        "description": clean(props.get("description")),
    }
    if published:
        item["pubDate"] = email.utils.format_datetime(published)
    return item


def build_items() -> list[dict]:
    page_html = fetch_with_retry(SITE_LINK)
    page_id = discover_page_id(page_html)
    action_id = discover_listing_action_id(page_html)
    raw_items = fetch_listing(action_id, page_id)

    items = []
    for entry in raw_items:
        item = parse_item(entry)
        if item:
            items.append(item)
        if len(items) >= MAX_ITEMS:
            break
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
    out.append("<description>Custom RSS feed for The NHS Alliance news</description>")
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
