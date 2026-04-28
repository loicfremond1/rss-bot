import datetime
import email.utils
import html
import json
import sys
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen

SITE_TITLE = "HSJ - Latest news"
SITE_LINK = "https://www.hsj.co.uk/latest-news/20683.more?navcode=2238"
FEED_FILE = "feed_hsj.xml"

MAX_ITEMS = 20
TIMEOUT_SECONDS = 60

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def fetch_with_retry(url: str, attempts: int = 2) -> str:
    last_err = None
    for i in range(attempts):
        try:
            return fetch_html(url)
        except (OSError, URLError, UnicodeDecodeError) as e:
            last_err = e
            print(f"Attempt {i + 1} failed: {e}", flush=True)
    raise last_err


def clean(value: str) -> str:
    return " ".join((value or "").split())


def parse_datetime(value: str) -> datetime.datetime | None:
    cleaned = clean(value)
    if not cleaned:
        return None
    normalized = cleaned.replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(normalized)
    except ValueError:
        print(f"Skipping unrecognised date: {cleaned}", flush=True)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


class HsjListingParser(HTMLParser):
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
        self.items = []
        self._current = None
        self._story_depth = 0
        self._title_depth = 0
        self._description_depth = 0
        self._date_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = (attr_map.get("class") or "").split()
        is_void = tag in self.VOID_TAGS

        if tag == "div" and "storyDetails" in classes:
            self._current = {
                "title_parts": [],
                "description_parts": [],
                "link": "",
                "date": "",
            }
            self._story_depth = 1
            return

        if not self._current:
            return

        if not is_void:
            self._story_depth += 1

        if tag == "h3":
            self._title_depth = 1
        elif self._title_depth and not is_void:
            self._title_depth += 1

        if tag == "a" and self._title_depth and attr_map.get("href"):
            self._current["link"] = attr_map.get("href") or ""

        if tag == "span" and "date" in classes:
            self._date_depth = 1
            timezone_data = attr_map.get("data-date-timezone") or ""
            if timezone_data:
                self._current["date"] = self._date_from_attr(timezone_data)
        elif self._date_depth and not is_void:
            self._date_depth += 1

        if tag == "p" and "meta" not in classes and not self._current["description_parts"]:
            self._description_depth = 1
        elif self._description_depth and not is_void:
            self._description_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._title_depth:
            self._title_depth -= 1
        if self._description_depth:
            self._description_depth -= 1
        if self._date_depth:
            self._date_depth -= 1

        if self._current and self._story_depth:
            self._story_depth -= 1
            if self._story_depth == 0:
                self._finish_current()

    def handle_data(self, data: str) -> None:
        if not self._current:
            return
        if self._title_depth:
            self._current["title_parts"].append(data)
        elif self._description_depth:
            self._current["description_parts"].append(data)
        elif self._date_depth and not self._current["date"]:
            self._current["date"] = data

    def _date_from_attr(self, value: str) -> str:
        try:
            data = json.loads(html.unescape(value))
        except json.JSONDecodeError:
            return ""
        return data.get("publishdate") or ""

    def _finish_current(self) -> None:
        current = self._current or {}
        title = clean(" ".join(current.get("title_parts") or []))
        link = clean(current.get("link") or "")
        if title and link:
            item = {
                "title": title,
                "link": link,
                "description": clean(" ".join(current.get("description_parts") or [])),
            }
            published = parse_datetime(current.get("date") or "")
            if published:
                item["pubDate"] = email.utils.format_datetime(published)
            self.items.append(item)
        self._current = None
        self._story_depth = 0
        self._title_depth = 0
        self._description_depth = 0
        self._date_depth = 0


def build_items() -> list[dict]:
    parser = HsjListingParser()
    parser.feed(fetch_with_retry(SITE_LINK))
    return parser.items[:MAX_ITEMS]


def rss2(items: list[dict]) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    now_http = email.utils.format_datetime(now)
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<rss version="2.0">')
    out.append("<channel>")
    out.append(f"<title>{html.escape(SITE_TITLE)}</title>")
    out.append(f"<link>{html.escape(SITE_LINK)}</link>")
    out.append("<description>Custom RSS feed for HSJ latest news</description>")
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
