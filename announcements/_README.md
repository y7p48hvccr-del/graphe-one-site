# Announcements

One file per post, named `<id>.md` (for example `2026-11-05-weekly.md`). Copy `_TEMPLATE.md`.
Files starting with `_` are ignored. This folder is not published; only the generated files are.

    tools/generate_announcements.py --check     validate every post, write nothing
    tools/generate_announcements.py             validate, then write the feed, the RSS feed and the news page

Every post needs all 25 languages (`tools/app_languages.json`), or nothing is written. A post for chosen languages (`languages: he, ar`) needs English and those only, and a `minVersion` of at least `languageFilterMinVersion` in that file, because older apps ignore the field.
A `published` date in the future keeps the post hidden until that day.
Then commit and push the repository to publish.

The format is defined in `ScriptureStudy_macOS/docs/ANNOUNCEMENTS_INBOX_SPEC.md`.

© 2026 Studio Graphē One Ltd
