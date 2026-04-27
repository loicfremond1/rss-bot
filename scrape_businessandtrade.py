from scraper_common import build_items_from_html, fetch_html_with_browser, rss2

SITE_TITLE = "Business and Trade Committee — News"
SITE_LINK = "https://committees.parliament.uk/committee/365/business-and-trade-committee/news/"
START_URL = SITE_LINK

SELECTOR_ITEM = "div.card-list a.card"
SELECTOR_TITLE = ".primary-info"
SELECTOR_SUMMARY = ".text"
MAX_ITEMS = 20
OUTPUT_FILE = "feed_businessandtrade.xml"


def main():
    html_text = fetch_html_with_browser(START_URL)
    items = build_items_from_html(
        html_text,
        base_url=START_URL,
        selector_item=SELECTOR_ITEM,
        selector_title=SELECTOR_TITLE,
        selector_summary=SELECTOR_SUMMARY,
        max_items=MAX_ITEMS,
    )
    xml = rss2(SITE_TITLE, SITE_LINK, items)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(xml)


if __name__ == "__main__":
    main()
