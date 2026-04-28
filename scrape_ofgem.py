# scrape_ofgem.py
import datetime
import email.utils
import html
import json
import sys
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

SITE_TITLE = "Ofgem - Press releases"
SITE_LINK = "https://www.ofgem.gov.uk/news-and-insight/press-releases"
API_ENDPOINT = "https://www.ofgem.gov.uk/api/listing/2054"
FEED_FILE = "feed_ofgem.xml"

MAX_ITEMS = 20
TIMEOUT_SECONDS = 60


def build_api_url(page: int = 0) -> str:
    params = [
        ("sort[field_published][path]", "field_published"),
        ("sort[field_published][direction]", "desc"),
    ]
    if page:
        params.append(("page", str(page)))
    return f"{API_ENDPOINT}?{urlencode(params)}"


def fetch_json(url: str) -> dict:
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
        },
    )
    with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_with_retry(url: str, attempts: int = 2) -> dict:
    last_err = None
    for i in range(attempts):
        try:
            return fetch_json(url)
        except (OSError, URLError, json.JSONDecodeError) as e:
            last_err = e
            print(f"Attempt {i + 1} failed: {e}", flush=True)
    raise last_err


def clean(value: str) -> str:
    return " ".join((value or "").split())


def parse_datetime(value: str) -> datetime.datetime:
    if not value:
        return datetime.datetime.now(datetime.timezone.utc)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


class OfgemTeaserParser(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.href = ""
        self.title_parts = []
        self.summary_parts = []
        self.datetime_value = ""
        self._title_depth = 0
        self._summary_container_depth = 0
        self._summary_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = (attr_map.get("class") or "").split()
        is_void = tag in self.VOID_TAGS

        if tag == "a" and not self.href and attr_map.get("href"):
            self.href = attr_map["href"] or ""

        if tag == "h3":
            self._title_depth = 1
        elif self._title_depth and not is_void:
            self._title_depth += 1

        if tag == "div" and "c-wysiwyg" in classes:
            self._summary_container_depth = 1
        elif self._summary_container_depth and not is_void:
            self._summary_container_depth += 1

        if tag == "p" and self._summary_container_depth and not self.summary_parts:
            self._summary_depth = 1
        elif self._summary_depth and not is_void:
            self._summary_depth += 1

        if tag == "time" and not self.datetime_value and attr_map.get("datetime"):
            self.datetime_value = attr_map["datetime"] or ""

    def handle_endtag(self, tag: str) -> None:
        if self._title_depth:
            self._title_depth -= 1
        if self._summary_depth:
            self._summary_depth -= 1
        if self._summary_container_depth:
            self._summary_container_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self.title_parts.append(data)
        if self._summary_depth:
            self.summary_parts.append(data)


def parse_item(markup: str) -> dict | None:
    parser = OfgemTeaserParser()
    parser.feed(markup)
    if not parser.href:
        return None

    link = urljoin(SITE_LINK, parser.href)
    title = clean(" ".join(parser.title_parts))
    summary = clean(" ".join(parser.summary_parts))
    published = parse_datetime(parser.datetime_value)

    return {
        "title": title or link,
        "link": link,
        "description": summary,
        "pubDate": email.utils.format_datetime(published),
    }


def build_items() -> list[dict]:
    items = []
    page = 0
    while len(items) < MAX_ITEMS:
        data = fetch_with_retry(build_api_url(page))
        page_items = data.get("items") or []
        if not page_items:
            break
        for entry in page_items:
            item = parse_item(entry.get("markup", ""))
            if item:
                items.append(item)
            if len(items) >= MAX_ITEMS:
                break
        page += 1
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
    out.append("<description>Custom RSS feed for Ofgem press releases</description>")
    out.append(f"<lastBuildDate>{now_http}</lastBuildDate>")
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
