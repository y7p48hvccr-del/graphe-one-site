#!/usr/bin/env python3
"""
Generate ScriptureStudy Pro's announcements feed from the post files.

What it does
------------
Reads every post in  <repo>/announcements/*.md  and writes three things:

    docs/ScriptureStudy/resources/announcements/announcements.json   the feed the app reads
    docs/ScriptureStudy/resources/announcements/feed.xml             a public RSS feed (English)
    docs/ScriptureStudy/news.html                                    a public news page (English)

The app (macOS, iPadOS, iPhone, Windows, Android) reads announcements.json at launch.
The format is defined in ScriptureStudy_macOS/docs/ANNOUNCEMENTS_INBOX_SPEC.md.

The rule that matters
---------------------
Every post must exist in EVERY app language (tools/app_languages.json). If any language is
missing, empty or unknown, nothing is written and the script exits with an error. Add
--app-strings <Localizable.xcstrings> to also check that app_languages.json still matches the
languages the app itself ships.

Post file format (see announcements/_TEMPLATE.md)
-------------------------------------------------
    ---
    id: 2026-11-05-weekly            (must equal the file name without .md)
    kind: weekly                     weekly | roundup | catalogue | licence | app
    published: 2026-11-05            shown from this date (a later date = scheduled)
    expires: 2026-12-05
    platforms: macos, ios, windows, android
    minVersion:                      optional floor, e.g. 2.4 (2.4 and later)
    maxVersion:                      optional; covers its whole line, so 2.3 includes 2.3.5 and
                                     excludes 2.4 ("coming in 2.4" is maxVersion 2.3)
    audience: all                    all | basic | full | trial | expired
    theme: standard                  standard | update | new   how the card looks in the app
                                     (update = general notice; new = a new service, with fanfare).
                                     Older apps ignore it and show the standard card.
    languages: he, ar                optional: only users whose app language is listed see it
                                     (blank = everyone). Needs minVersion of languageFilterMinVersion
                                     or later (tools/app_languages.json), because older apps ignore it.
    action: openCatalogue            none | openCatalogue | openModule | openSettings | openUrl
    target:                          catalogue path / settings section / https URL
    ---

    [en]
    Title on the first line

    Body text. Plain text, with **bold** and [links](https://example.com) only.

    [de]
    ...

Usage
-----
    tools/generate_announcements.py                  validate, then write the three outputs
    tools/generate_announcements.py --check          validate only, write nothing
    tools/generate_announcements.py --now 2026-11-05 pretend today is that date (for tests)

Deploy stays a separate, deliberate step: commit and push this repository.

© 2026 Studio Graphē One Ltd
"""
import argparse
import datetime as dt
import email.utils
import html
import json
import re
import sys
from pathlib import Path

KINDS = ["weekly", "roundup", "catalogue", "licence", "app"]
PLATFORMS = ["macos", "ios", "windows", "android"]
AUDIENCES = ["all", "basic", "full", "trial", "expired"]
THEMES = ["standard", "update", "new"]
ACTIONS = ["none", "openCatalogue", "openModule", "openSettings", "openUrl"]
ACTIONS_NEEDING_TARGET = ["openModule", "openSettings", "openUrl"]
MAX_TITLE = 80
MAX_BODY = 600
SCHEMA = 1

PLATFORM_LABELS = {"macos": "macOS", "ios": "iPhone and iPad", "windows": "Windows", "android": "Android"}
LINK = re.compile(r"\[([^\]\n]+)\]\((https://[^)\s]+)\)")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
LANG_HEADER = re.compile(r"^\[([A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?)\]\s*$", re.M)
VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")


# --------------------------------------------------------------------------- parsing

def read_languages(root):
    path = root / "tools" / "app_languages.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    langs = data["languages"]
    if len(set(langs)) != len(langs):
        raise SystemExit(f"{path}: duplicate language codes")
    return langs


def read_language_filter_min_version(root):
    """The first app version that understands a post's `languages` field (or None if not set)."""
    path = root / "tools" / "app_languages.json"
    return json.loads(path.read_text(encoding="utf-8")).get("languageFilterMinVersion")


def version_tuple(value):
    return tuple(int(x) for x in value.split("."))


def parse_post(path, languages, filter_min_version=None):
    """Returns (post_dict, [errors]). Never raises for bad content."""
    errors = []
    name = path.name

    def err(msg):
        errors.append(f"{name}: {msg}")

    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    parts = text.split("\n---\n", 1) if text.startswith("---\n") else None
    if not parts or len(parts) != 2:
        err("missing front matter (the block between two --- lines at the top)")
        return None, errors
    front = parts[0][4:] if parts[0].startswith("---\n") else parts[0]
    body_text = parts[1]

    meta = {}
    for line in front.split("\n"):
        if not line.strip():
            continue
        if ":" not in line:
            err(f"front matter line without a colon: {line!r}")
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()

    post = {"_file": name}

    # id
    pid = meta.get("id", "")
    if not pid:
        err("id is missing")
    elif pid != path.stem:
        err(f"id {pid!r} must equal the file name {path.stem!r}")
    post["id"] = pid

    # kind, audience
    kind = meta.get("kind", "")
    if kind not in KINDS:
        err(f"kind {kind!r} must be one of {', '.join(KINDS)}")
    post["kind"] = kind
    audience = meta.get("audience", "all") or "all"
    if audience not in AUDIENCES:
        err(f"audience {audience!r} must be one of {', '.join(AUDIENCES)}")
    post["audience"] = audience
    theme = meta.get("theme", "standard") or "standard"
    if theme not in THEMES:
        err(f"theme {theme!r} must be one of {', '.join(THEMES)}")
    post["theme"] = theme

    # dates
    def parse_date(field):
        raw = meta.get(field, "")
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            err(f"{field} {raw!r} must be a date like 2026-11-05")
            return None
    published, expires = parse_date("published"), parse_date("expires")
    if published and expires and expires <= published:
        err("expires must be after published")
    post["published"], post["expires"] = published, expires

    # platforms
    plats = [p.strip() for p in meta.get("platforms", "").split(",") if p.strip()]
    if not plats:
        err("platforms is empty (use: macos, ios, windows, android)")
    for p in plats:
        if p not in PLATFORMS:
            err(f"unknown platform {p!r} (allowed: {', '.join(PLATFORMS)})")
    post["platforms"] = [p for p in PLATFORMS if p in plats]

    # versions
    for field in ("minVersion", "maxVersion"):
        value = meta.get(field, "")
        if value and not VERSION.match(value):
            err(f"{field} {value!r} must look like 2.4 or 2.4.1")
        post[field] = value or None

    # languages: who it is for (blank = everyone)
    wanted = [c.strip() for c in meta.get("languages", "").split(",") if c.strip()]
    for c in wanted:
        if c not in languages:
            err(f"languages: unknown language {c!r} (allowed: {', '.join(languages)})")
    if len(set(wanted)) != len(wanted):
        err("languages lists a language twice")
    wanted = [c for c in languages if c in wanted]
    if wanted and set(wanted) == set(languages):
        wanted = []  # every language is the same as no restriction
    if wanted:
        if not filter_min_version:
            err("languages needs languageFilterMinVersion in tools/app_languages.json "
                "(older apps ignore the field and would show the post to everyone)")
        elif not post["minVersion"] or version_tuple(post["minVersion"]) < version_tuple(filter_min_version):
            err(f"a post for chosen languages needs minVersion {filter_min_version} or later, "
                f"because older apps ignore the languages field and would show it to everyone")
    post["languages"] = wanted
    required = (["en"] + [c for c in wanted if c != "en"]) if wanted else list(languages)

    # action
    action = meta.get("action", "none") or "none"
    target = meta.get("target", "")
    if action not in ACTIONS:
        err(f"action {action!r} must be one of {', '.join(ACTIONS)}")
    elif action in ACTIONS_NEEDING_TARGET and not target:
        err(f"action {action} needs a target")
    elif action not in ACTIONS_NEEDING_TARGET and target:
        err(f"action {action} must not have a target")
    if action == "openUrl" and target and not target.startswith("https://"):
        err("openUrl target must start with https://")
    post["action"] = {"type": action, "target": target or None}

    # languages
    sections = {}
    headers = list(LANG_HEADER.finditer(body_text))
    if body_text[:headers[0].start()].strip() if headers else body_text.strip():
        err("text before the first [language] line")
    for i, h in enumerate(headers):
        code = h.group(1)
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body_text)
        chunk = body_text[h.end():end].strip("\n")
        if code in sections:
            err(f"language [{code}] appears twice")
            continue
        lines = [ln.rstrip() for ln in chunk.split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        title = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:]).strip()
        sections[code] = (title, body)

    missing = [c for c in required if c not in sections]
    unknown = [c for c in sections if c not in languages]
    extra = [c for c in sections if c in languages and c not in required]
    if missing:
        err(f"missing {len(missing)} of {len(required)} languages: {', '.join(missing)}")
    if extra:
        err(f"text for languages the post is not for: {', '.join(extra)} (remove them or add them to languages)")
    if unknown:
        err(f"unknown language(s): {', '.join(unknown)}")
    title_map, body_map = {}, {}
    for code in required:
        if code not in sections:
            continue
        title, body = sections[code]
        if not title:
            err(f"[{code}] has no title")
        if not body:
            err(f"[{code}] has no body")
        if len(title) > MAX_TITLE:
            err(f"[{code}] title is {len(title)} characters (limit {MAX_TITLE})")
        if len(body) > MAX_BODY:
            err(f"[{code}] body is {len(body)} characters (limit {MAX_BODY})")
        for label, value in (("title", title), ("body", body)):
            for problem in markup_problems(value):
                err(f"[{code}] {label}: {problem}")
        title_map[code], body_map[code] = title, body
    post["title"], post["body"] = title_map, body_map
    return post, errors


def markup_problems(value):
    """Plain text with **bold** and [text](https://...) links only."""
    problems = []
    if re.search(r"<[A-Za-z/!?]", value):
        problems.append("HTML is not allowed")
    if value.count("](") != len(LINK.findall(value)):
        problems.append("links must look like [text](https://...)")
    if value.count("**") % 2:
        problems.append("unbalanced ** (bold)")
    return problems


# --------------------------------------------------------------------------- output

def feed_json(posts, languages, today, now):
    items = []
    for p in sorted(posts, key=lambda x: (x["published"], x["id"]), reverse=True):
        if p["published"] > today or p["expires"] < today:
            continue  # scheduled for later, or expired
        items.append({
            "id": p["id"],
            "kind": p["kind"],
            "published": p["published"].isoformat(),
            "expires": p["expires"].isoformat(),
            "platforms": p["platforms"],
            "minVersion": p["minVersion"],
            "maxVersion": p["maxVersion"],
            "audience": p["audience"],
            "theme": None if p["theme"] == "standard" else p["theme"],
            "languages": p["languages"] or None,
            "title": {c: p["title"][c] for c in languages if c in p["title"]},
            "body": {c: p["body"][c] for c in languages if c in p["body"]},
            "action": p["action"],
        })
    return {"schema": SCHEMA, "generated": now, "items": items}


def inline_html(text):
    out = html.escape(text, quote=False)
    out = LINK.sub(lambda m: '<a href="%s">%s</a>' % (m.group(2).replace('"', "%22"), m.group(1)), out)
    return BOLD.sub(r"<strong>\1</strong>", out)


def body_html(body):
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "\n".join("<p>%s</p>" % inline_html(p).replace("\n", "<br>") for p in paras)


LANGUAGE_LABELS = {
    "en": "English", "ar": "Arabic", "cs": "Czech", "da": "Danish", "de": "German", "es": "Spanish",
    "fr": "French", "he": "Hebrew", "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "lt": "Lithuanian", "nl": "Dutch", "pl": "Polish",
    "pt-BR": "Brazilian Portuguese", "pt-PT": "European Portuguese", "ro": "Romanian", "ru": "Russian",
    "sv": "Swedish", "tr": "Turkish", "zh-Hans": "Simplified Chinese", "zh-Hant": "Traditional Chinese",
}


def platform_note(platforms, languages=None):
    notes = []
    if set(platforms) != set(PLATFORMS):
        notes.append("For " + ", ".join(PLATFORM_LABELS[p] for p in platforms) + " only.")
    if languages:
        notes.append("For readers of " + ", ".join(LANGUAGE_LABELS.get(c, c) for c in languages) + " only.")
    return " ".join(notes)


def visible_posts(posts, today):
    return sorted((p for p in posts if p["published"] <= today),
                  key=lambda x: (x["published"], x["id"]), reverse=True)


def feed_xml(posts, today, now):
    base = "https://graphe.one/ScriptureStudy/news.html"
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0"><channel>',
           "<title>ScriptureStudy Pro™ news</title>",
           f"<link>{base}</link>",
           "<description>Announcements from Studio Graphē One for ScriptureStudy Pro™.</description>",
           "<language>en</language>",
           f"<lastBuildDate>{email.utils.format_datetime(dt.datetime.fromisoformat(now.replace('Z', '+00:00')))}</lastBuildDate>"]
    for p in visible_posts(posts, today):
        when = dt.datetime.combine(p["published"], dt.time(9, 0), tzinfo=dt.timezone.utc)
        text = p["body"]["en"]
        note = platform_note(p["platforms"], p.get("languages"))
        description = body_html(text) + (f"<p><em>{html.escape(note)}</em></p>" if note else "")
        out += ["<item>",
                f"<title>{html.escape(p['title']['en'])}</title>",
                f"<link>{base}#{p['id']}</link>",
                f'<guid isPermaLink="false">{p["id"]}</guid>',
                f"<pubDate>{email.utils.format_datetime(when)}</pubDate>",
                f"<description>{html.escape(description)}</description>",
                "</item>"]
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


NEWS_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>News — ScriptureStudy Pro™</title>
<link rel="alternate" type="application/rss+xml" title="ScriptureStudy Pro™ news" href="/ScriptureStudy/resources/announcements/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Crimson+Pro:wght@300;400&display=swap" rel="stylesheet">
<style>
  :root { --sky: #8fa1b5; --sky-light: #b8cad8; --sky-dark: #5d7289; --gold: #b8943a; --gold-light: #d4aa55;
          --navy: #1e2d3d; --cream: #f5f0e8; --cream-dark: #e8e0d0; --text: #1a2a38; --text-muted: #4a6070; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Crimson Pro', Georgia, serif; background: var(--cream); color: var(--text); -webkit-font-smoothing: antialiased; }
  .nav { background: var(--navy); padding: 16px 40px; display: flex; align-items: center; justify-content: space-between; }
  .nav-brand { font-family: 'Cormorant Garamond', serif; font-size: 20px; font-weight: 300; color: rgba(255,255,255,0.85); text-decoration: none; }
  .nav-brand em { font-style: italic; color: var(--gold-light); }
  .nav a { color: rgba(255,255,255,0.45); text-decoration: none; font-size: 14px; font-weight: 300; }
  .nav a:hover { color: var(--gold-light); }
  .hero { background: linear-gradient(160deg, var(--sky-dark) 0%, var(--sky) 100%); padding: 80px 24px 60px; text-align: center; }
  .hero h1 { font-family: 'Cormorant Garamond', serif; font-size: clamp(36px, 6vw, 56px); font-weight: 300; color: #fff; margin-bottom: 12px; }
  .hero h1 em { font-style: italic; color: var(--gold-light); }
  .hero p { font-size: 18px; font-weight: 300; color: rgba(255,255,255,0.75); }
  .content { max-width: 800px; margin: 0 auto; padding: 60px 24px 100px; }
  .post { margin-bottom: 44px; padding-bottom: 32px; border-bottom: 1px solid var(--cream-dark); }
  .post h2 { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; color: var(--navy); margin-bottom: 6px; }
  .post .date { font-size: 15px; color: var(--text-muted); margin-bottom: 14px; }
  .post p { font-size: 18px; font-weight: 300; color: var(--text-muted); line-height: 1.7; margin-bottom: 12px; }
  .post a { color: var(--sky-dark); text-decoration: none; border-bottom: 1px solid var(--sky-light); }
  .post a:hover { color: var(--gold); }
  .empty { font-size: 18px; color: var(--text-muted); }
  footer { background: var(--navy); padding: 32px 24px; text-align: center; }
  footer a { color: rgba(255,255,255,0.35); text-decoration: none; font-size: 13px; margin: 0 12px; font-weight: 300; }
  footer a:hover { color: var(--gold-light); }
  .footer-copy { font-size: 12px; color: rgba(255,255,255,0.2); margin-top: 12px; font-weight: 300; }
  @media (max-width: 640px) { .nav { padding: 14px 20px; } .hero { padding: 60px 20px 40px; } .content { padding: 40px 20px 80px; } }
</style>
</head>
<body>

<nav class="nav">
  <a href="/" class="nav-brand">Studio <em>Graphē</em> One</a>
  <a href="/ScriptureStudy/">← Overview</a>
</nav>

<div class="hero">
  <h1>News from <em>ScriptureStudy</em> Pro™</h1>
  <p>New modules, licensed material and changes to the app. <a href="/ScriptureStudy/resources/announcements/feed.xml" style="color:#fff">RSS</a></p>
</div>

<div class="content">
"""

NEWS_FOOT = """
</div>

<footer>
  <a href="/">Home</a>
  <a href="/ScriptureStudy/support.html">Support</a>
  <a href="/ScriptureStudy/privacy.html">Privacy Policy</a>
  <div class="footer-copy">© 2026 Studio Graphē One Ltd. All rights reserved.</div>
</footer>

</body>
</html>
"""


def news_page(posts, today):
    shown = visible_posts(posts, today)
    parts = [NEWS_HEAD]
    if not shown:
        parts.append('  <p class="empty">No announcements yet.</p>')
    for p in shown:
        note = platform_note(p["platforms"], p.get("languages"))
        parts.append(
            f'  <article class="post" id="{p["id"]}">\n'
            f'    <h2>{html.escape(p["title"]["en"])}</h2>\n'
            f'    <div class="date">{p["published"].strftime("%-d %B %Y")}</div>\n'
            f'    {body_html(p["body"]["en"])}\n'
            + (f'    <p><em>{html.escape(note)}</em></p>\n' if note else "")
            + "  </article>")
    parts.append(NEWS_FOOT)
    return "\n".join(parts)


# --------------------------------------------------------------------------- driver

def check_app_languages(languages, xcstrings_path):
    data = json.loads(Path(xcstrings_path).read_text(encoding="utf-8"))
    found = {data.get("sourceLanguage", "en")}
    for entry in data.get("strings", {}).values():
        found.update((entry.get("localizations") or {}).keys())
    problems = []
    if found - set(languages):
        problems.append("the app has languages missing from tools/app_languages.json: "
                        + ", ".join(sorted(found - set(languages))))
    if set(languages) - found:
        problems.append("tools/app_languages.json lists languages the app does not have: "
                        + ", ".join(sorted(set(languages) - found)))
    return problems


def run(root, today, now, check_only=False, app_strings=None):
    """Returns (errors, written_paths). Writes nothing when there are errors."""
    root = Path(root)
    languages = read_languages(root)
    errors, posts, seen = [], [], {}
    if app_strings:
        errors += check_app_languages(languages, app_strings)
    posts_dir = root / "announcements"
    for path in sorted(posts_dir.glob("*.md")) if posts_dir.exists() else []:
        if path.name.startswith("_"):
            continue  # _TEMPLATE.md and other notes
        post, errs = parse_post(path, languages, read_language_filter_min_version(root))
        errors += errs
        if post and not errs:
            if post["id"] in seen:
                errors.append(f"{path.name}: id already used by {seen[post['id']]}")
            seen[post["id"]] = path.name
            posts.append(post)
    if errors or check_only:
        return errors, []

    out_dir = root / "docs" / "ScriptureStudy" / "resources" / "announcements"
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        out_dir / "announcements.json": json.dumps(feed_json(posts, languages, today, now),
                                                    ensure_ascii=False, indent=2) + "\n",
        out_dir / "feed.xml": feed_xml(posts, today, now),
        root / "docs" / "ScriptureStudy" / "news.html": news_page(posts, today),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    return [], list(outputs)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate the ScriptureStudy Pro announcements feed.")
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--now", metavar="YYYY-MM-DD", help="pretend today is this date")
    ap.add_argument("--app-strings", metavar="PATH", help="Localizable.xcstrings, to cross-check the language list")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.now:
        today = dt.date.fromisoformat(args.now)
        now = f"{today.isoformat()}T09:00:00Z"
    else:
        stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        today, now = stamp.date(), stamp.isoformat().replace("+00:00", "Z")

    errors, written = run(args.root, today, now, args.check, args.app_strings)
    if errors:
        print(f"{len(errors)} problem(s); nothing was written:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    if args.check:
        print("All posts are valid.")
    else:
        for path in written:
            print("wrote", Path(path).relative_to(args.root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
