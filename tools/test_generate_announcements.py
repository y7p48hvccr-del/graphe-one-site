#!/usr/bin/env python3
"""Tests for generate_announcements.py. Run:  python3 tools/test_generate_announcements.py

Everything runs in a temporary copy of the site layout; no real file is touched.

© 2026 Studio Graphē One Ltd
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_announcements as g  # noqa: E402

REAL_LANGUAGES = json.loads((Path(__file__).resolve().parent / "app_languages.json").read_text(encoding="utf-8"))["languages"]
TODAY = dt.date(2026, 11, 10)
NOW = "2026-11-10T09:00:00Z"


def post_text(pid="2026-11-05-weekly", published="2026-11-05", expires="2026-12-05", languages=None,
              platforms="macos, ios, windows, android", audience="all", action="none", target="",
              min_version="", max_version="", kind="weekly", title=None, body=None, extra=""):
    languages = REAL_LANGUAGES if languages is None else languages
    text = (f"---\nid: {pid}\nkind: {kind}\npublished: {published}\nexpires: {expires}\n"
            f"platforms: {platforms}\nminVersion: {min_version}\nmaxVersion: {max_version}\n"
            f"audience: {audience}\naction: {action}\ntarget: {target}\n---\n\n")
    for code in languages:
        text += f"[{code}]\n{title or 'Title ' + code}\n\n{body or 'Body for ' + code + '.'}\n\n"
    return text + extra


class Site:
    """A throwaway site layout with the real language list."""
    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "tools").mkdir()
        (self.root / "announcements").mkdir()
        (self.root / "tools" / "app_languages.json").write_text(
            json.dumps({"languages": REAL_LANGUAGES}), encoding="utf-8")

    def add(self, name, text):
        (self.root / "announcements" / name).write_text(text, encoding="utf-8")

    def run(self, **kw):
        return g.run(self.root, kw.pop("today", TODAY), NOW, **kw)

    def feed(self):
        return json.loads((self.root / "docs/ScriptureStudy/resources/announcements/announcements.json")
                          .read_text(encoding="utf-8"))

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def written(self):
        return (self.root / "docs").exists()


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.site = Site()

    def tearDown(self):
        self.site.dir.cleanup()

    def assertRejected(self, fragment):
        errors, written = self.site.run()
        self.assertTrue(any(fragment in e for e in errors), f"expected {fragment!r} in {errors}")
        self.assertEqual(written, [])
        self.assertFalse(self.site.written(), "nothing may be written when a post is invalid")

    # ---- the empty feed
    def test_no_posts_writes_an_empty_feed(self):
        errors, written = self.site.run()
        self.assertEqual(errors, [])
        self.assertEqual(len(written), 3)
        feed = self.site.feed()
        self.assertEqual((feed["schema"], feed["items"], feed["generated"]), (1, [], NOW))
        self.assertIn("No announcements yet.", self.site.read("docs/ScriptureStudy/news.html"))
        ET.fromstring(self.site.read("docs/ScriptureStudy/resources/announcements/feed.xml"))

    def test_templates_and_underscore_files_are_ignored(self):
        self.site.add("_TEMPLATE.md", "not a post")
        self.assertEqual(self.site.run()[0], [])

    # ---- a valid post
    def test_valid_post_carries_every_language_in_order(self):
        self.site.add("2026-11-05-weekly.md", post_text())
        self.assertEqual(self.site.run()[0], [])
        item = self.site.feed()["items"][0]
        self.assertEqual(list(item["title"]), REAL_LANGUAGES)
        self.assertEqual(list(item["body"]), REAL_LANGUAGES)
        self.assertEqual(item["platforms"], ["macos", "ios", "windows", "android"])
        self.assertEqual(item["action"], {"type": "none", "target": None})
        self.assertIsNone(item["minVersion"])
        self.assertEqual(item["audience"], "all")

    def test_platform_list_is_normalised_and_versions_kept(self):
        self.site.add("2026-11-05-weekly.md",
                      post_text(platforms="windows, macos", min_version="2.4", audience="basic"))
        self.site.run()
        item = self.site.feed()["items"][0]
        self.assertEqual(item["platforms"], ["macos", "windows"])
        self.assertEqual((item["minVersion"], item["audience"]), ("2.4", "basic"))

    def test_actions_with_targets(self):
        self.site.add("2026-11-05-weekly.md",
                      post_text(action="openUrl", target="https://example.com/x"))
        self.assertEqual(self.site.run()[0], [])
        self.assertEqual(self.site.feed()["items"][0]["action"],
                         {"type": "openUrl", "target": "https://example.com/x"})

    # ---- the language rule
    def test_a_missing_language_blocks_publication(self):
        self.site.add("2026-11-05-weekly.md", post_text(languages=[c for c in REAL_LANGUAGES if c != "lt"]))
        self.assertRejected("missing 1 of 25 languages: lt")

    def test_an_unknown_language_is_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(languages=REAL_LANGUAGES + ["el"]))
        self.assertRejected("unknown language(s): el")

    def test_an_empty_body_is_rejected(self):
        text = post_text().replace("Body for de.", "")
        self.site.add("2026-11-05-weekly.md", text)
        self.assertRejected("[de] has no body")

    def test_a_language_given_twice_is_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(extra="[de]\nAgain\n\nAgain.\n"))
        self.assertRejected("[de] appears twice")

    # ---- limits and markup
    def test_long_title_and_body_are_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(title="T" * 81))
        self.assertRejected("title is 81 characters")

    def test_long_body_is_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(body="B" * 601))
        self.assertRejected("body is 601 characters")

    def test_html_is_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(body="Click <b>here</b>"))
        self.assertRejected("HTML is not allowed")

    def test_non_https_links_are_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(body="See [this](http://example.com)."))
        self.assertRejected("links must look like")

    def test_https_links_and_bold_are_allowed(self):
        self.site.add("2026-11-05-weekly.md",
                      post_text(body="See **this** [page](https://example.com/a?b=1&c=2)."))
        self.assertEqual(self.site.run()[0], [])

    def test_unbalanced_bold_is_rejected(self):
        self.site.add("2026-11-05-weekly.md", post_text(body="A **broken bold."))
        self.assertRejected("unbalanced")

    # ---- front matter
    def test_id_must_match_the_file_name(self):
        self.site.add("2026-11-05-weekly.md", post_text(pid="something-else"))
        self.assertRejected("must equal the file name")

    def test_expiry_must_follow_publication(self):
        self.site.add("2026-11-05-weekly.md", post_text(expires="2026-11-05"))
        self.assertRejected("expires must be after published")

    def test_bad_date_kind_platform_audience_version(self):
        for kwargs, fragment in [
            (dict(published="05/11/2026"), "must be a date"),
            (dict(kind="gossip"), "kind 'gossip'"),
            (dict(platforms="macos, symbian"), "unknown platform 'symbian'"),
            (dict(audience="vip"), "audience 'vip'"),
            (dict(min_version="two"), "minVersion 'two'"),
        ]:
            with self.subTest(fragment=fragment):
                site = Site()
                site.add("2026-11-05-weekly.md", post_text(**kwargs))
                errors, _ = site.run()
                self.assertTrue(any(fragment in e for e in errors), errors)
                site.dir.cleanup()

    def test_action_targets(self):
        for kwargs, fragment in [
            (dict(action="openModule"), "needs a target"),
            (dict(action="openUrl", target="http://example.com"), "must start with https://"),
            (dict(action="openCatalogue", target="x"), "must not have a target"),
            (dict(action="openLegacy"), "action 'openLegacy'"),
        ]:
            with self.subTest(fragment=fragment):
                site = Site()
                site.add("2026-11-05-weekly.md", post_text(**kwargs))
                errors, _ = site.run()
                self.assertTrue(any(fragment in e for e in errors), errors)
                site.dir.cleanup()

    def test_missing_front_matter_is_rejected(self):
        self.site.add("2026-11-05-weekly.md", "just text")
        self.assertRejected("missing front matter")

    # ---- dates decide what the app sees
    def test_expired_and_scheduled_posts_stay_out_of_the_feed(self):
        self.site.add("2026-10-01-old.md", post_text(pid="2026-10-01-old", published="2026-10-01", expires="2026-11-01"))
        self.site.add("2026-11-05-now.md", post_text(pid="2026-11-05-now"))
        self.site.add("2026-12-01-later.md", post_text(pid="2026-12-01-later", published="2026-12-01", expires="2027-01-01"))
        self.assertEqual(self.site.run()[0], [])
        self.assertEqual([i["id"] for i in self.site.feed()["items"]], ["2026-11-05-now"])

    def test_the_public_page_keeps_expired_posts_but_not_scheduled_ones(self):
        self.site.add("2026-10-01-old.md", post_text(pid="2026-10-01-old", published="2026-10-01", expires="2026-11-01"))
        self.site.add("2026-12-01-later.md", post_text(pid="2026-12-01-later", published="2026-12-01", expires="2027-01-01"))
        self.site.run()
        news = self.site.read("docs/ScriptureStudy/news.html")
        self.assertIn('id="2026-10-01-old"', news)
        self.assertNotIn("2026-12-01-later", news)
        rss = ET.fromstring(self.site.read("docs/ScriptureStudy/resources/announcements/feed.xml"))
        self.assertEqual([i.find("guid").text for i in rss.iter("item")], ["2026-10-01-old"])

    def test_newest_first(self):
        for day in ("01", "05", "03"):
            self.site.add(f"2026-11-{day}-w.md", post_text(pid=f"2026-11-{day}-w", published=f"2026-11-{day}", expires="2026-12-31"))
        self.site.run()
        self.assertEqual([i["id"] for i in self.site.feed()["items"]],
                         ["2026-11-05-w", "2026-11-03-w", "2026-11-01-w"])

    # ---- the public pages
    def test_news_page_and_rss_use_english_and_render_markup_safely(self):
        self.site.add("2026-11-05-weekly.md",
                      post_text(title="Fish & chips", body="A **bold** claim & [a link](https://example.com/?a=1&b=2)."))
        self.site.run()
        news = self.site.read("docs/ScriptureStudy/news.html")
        self.assertIn("Fish &amp; chips", news)
        self.assertIn("<strong>bold</strong>", news)
        self.assertIn('<a href="https://example.com/?a=1&amp;b=2">a link</a>', news)
        rss = ET.fromstring(self.site.read("docs/ScriptureStudy/resources/announcements/feed.xml"))
        self.assertEqual(rss.find("channel/item/title").text, "Fish & chips")

    def test_platform_specific_posts_say_so_on_the_public_page(self):
        self.site.add("2026-11-05-weekly.md", post_text(platforms="macos, ios"))
        self.site.run()
        self.assertIn("For macOS, iPhone and iPad only.", self.site.read("docs/ScriptureStudy/news.html"))

    def test_output_is_identical_on_a_second_run(self):
        self.site.add("2026-11-05-weekly.md", post_text())
        self.site.run()
        first = {p: self.site.read(p) for p in (
            "docs/ScriptureStudy/resources/announcements/announcements.json",
            "docs/ScriptureStudy/resources/announcements/feed.xml", "docs/ScriptureStudy/news.html")}
        self.site.run()
        self.assertEqual(first, {p: self.site.read(p) for p in first})

    def test_check_mode_writes_nothing(self):
        self.site.add("2026-11-05-weekly.md", post_text())
        errors, written = self.site.run(check_only=True)
        self.assertEqual((errors, written), ([], []))
        self.assertFalse(self.site.written())

    # ---- cross-check with the app's own languages
    def test_app_languages_cross_check(self):
        strings = self.site.root / "Localizable.xcstrings"
        langs = {c: {} for c in REAL_LANGUAGES if c != "en"}
        strings.write_text(json.dumps({"sourceLanguage": "en", "strings": {"k": {"localizations": langs}}}))
        self.assertEqual(self.site.run(check_only=True, app_strings=strings)[0], [])
        langs["el"] = {}
        strings.write_text(json.dumps({"sourceLanguage": "en", "strings": {"k": {"localizations": langs}}}))
        errors = self.site.run(check_only=True, app_strings=strings)[0]
        self.assertTrue(any("missing from tools/app_languages.json: el" in e for e in errors), errors)

    def test_the_real_language_list_has_no_duplicates_and_starts_with_english(self):
        self.assertEqual(len(set(REAL_LANGUAGES)), len(REAL_LANGUAGES))
        self.assertEqual(REAL_LANGUAGES[0], "en")
        self.assertEqual(len(REAL_LANGUAGES), 25)


if __name__ == "__main__":
    unittest.main(verbosity=1)
