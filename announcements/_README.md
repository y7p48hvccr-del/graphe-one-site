# Announcements

One file per post, named `<id>.md` (for example `2026-11-05-weekly.md`). Copy `_TEMPLATE.md`.
Files starting with `_` are ignored. This folder is not published; only the generated files are.

    tools/generate_announcements.py --check     validate every post, write nothing
    tools/generate_announcements.py             validate, then write the feed, the RSS feed and the news page

Every post needs all 46 languages (`tools/app_languages.json`), or nothing is written. A post for chosen languages (`languages: he, ar`) needs English and those only, and a `minVersion` of at least `languageFilterMinVersion` in that file, because older apps ignore the field.
A `published` date in the future keeps the post hidden until that day.
Then commit and push the repository to publish.

TV Studio One's posts live in `tvstudioone/` (copy `tvstudioone/_TEMPLATE.md`) and are checked and written with
`--app tvstudioone`: Android only, audiences all / trial / full / expired, buttons openUrl and openSettings, and its own 28
languages (`tools/app_languages_tvstudioone.json`). Its feed is `docs/TVStudioOne/resources/announcements/announcements.json`.

Scrib's posts live in `scrib/` (copy `scrib/_TEMPLATE.md`) and are checked and written with `--app scrib`: iPhone, iPad
and Mac (`platforms: ios, macos`), audiences all / trial (the 5-day trial) / full (bought the unlock) / expired, buttons
openUrl and openSettings, and its own 35 languages (`tools/app_languages_scrib.json`; en-GB is served from en). Its feed is
`docs/Scrib/resources/announcements/announcements.json`. A post that uses `languages:` needs `minVersion: 1.1.0` or later.
To check the list against the app: `--check --app scrib --app-strings <Scrib/Scrib/Localizable.xcstrings>`.

The format is defined in `ScriptureStudy_macOS/docs/ANNOUNCEMENTS_INBOX_SPEC.md`.

© 2026 Studio Graphē One Ltd
