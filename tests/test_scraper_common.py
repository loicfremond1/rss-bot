import re
import unittest

from scraper_common import build_items_from_html, rss2


class ScraperCommonTests(unittest.TestCase):
    def test_build_items_from_html_extracts_expected_fields(self):
        sample_html = """
        <div class='card-list'>
          <a class='card' href='/news/alpha/'>
            <div class='primary-info'>Alpha title</div>
            <div class='text'>Alpha summary</div>
          </a>
          <a class='card' href='/news/beta/'>
            <div class='primary-info'>Beta title</div>
          </a>
        </div>
        """

        items = build_items_from_html(
            sample_html,
            base_url="https://committees.parliament.uk/example/",
            selector_item="div.card-list a.card",
            selector_title=".primary-info",
            selector_summary=".text",
            max_items=20,
        )

        self.assertEqual(2, len(items))
        self.assertEqual("Alpha title", items[0]["title"])
        self.assertEqual(
            "https://committees.parliament.uk/news/alpha/",
            items[0]["link"],
        )
        self.assertEqual("Alpha summary", items[0]["description"])
        self.assertEqual("", items[1]["description"])
        self.assertRegex(items[0]["pubDate"], r"\+0000$")

    def test_rss2_escapes_xml_entities(self):
        items = [
            {
                "title": "A & B <C>",
                "link": "https://example.com/item?x=1&y=2",
                "description": "One < Two & Three",
                "pubDate": "Mon, 01 Jan 2024 00:00:00 +0000",
            }
        ]

        xml = rss2(
            site_title="Title & Co",
            site_link="https://example.com/?a=1&b=2",
            items=items,
        )

        self.assertIn("<title>Title &amp; Co</title>", xml)
        self.assertIn("A &amp; B &lt;C&gt;", xml)
        self.assertIn("One &lt; Two &amp; Three", xml)
        self.assertRegex(xml, re.compile(r"<rss version=\"2.0\">"))


if __name__ == "__main__":
    unittest.main()
