# The CookieGuard cookie database

Two open datasets behind CookieGuard AI, rebuilt from the frozen November 2026 studies by
`build.py`. Browse and search them at <https://aiscihub.github.io/cookieguard-ai/database.html>.

| File | What it is | Rows |
| --- | --- | ---: |
| `known-cookie-names.json` / `.csv` | The known-name lookup table CookieGuard consults before its model | 12,481 raw names · 7,835 normalized names · 2,261 Open Cookie Database entries |
| `cookies-2026.jsonl` / `.csv` | Consent-declared cookies observed on real websites in November 2026 | 16,571 cookies · 788 sites · 2,781 normalized names |
| `stats.json` | Counts, feature names, and file sizes | |

**No cookie value is in these files.** Rows carry the value's length and character class only.
The crawler held values in memory solely to scan every saved file for leaks, and every scan passed.

## Known cookie names

A lookup: cookie name → `tracker` or `not-tracker`, with the votes behind it.

- **`cookieguard.raw`**: exact, case-sensitive names. One vote per labeled cookie we hold
  (241,912 rows from the 2021 CookieBlock crawl, 4,087 from our 2026 tuning crawl); the majority
  label wins, ties are dropped. `rows2021` / `rows2026` say where the votes came from.
- **`cookieguard.normalized`**: the same votes keyed by the normalized name (lowercase; split on
  `_ . -`; a piece of 6+ characters mixing letters and digits, or 8+ hex characters, becomes `#`;
  every digit run becomes `0`). Catches `_ga_ABC123` → `_ga_#`.
- **`ocd`**: the [Open Cookie Database](https://github.com/jkwakman/Open-Cookie-Database)
  (commit `7786335`), Marketing/Analytics → `tracker`, Functional/Security/Personalization →
  `not-tracker`; `match` is `exact` or `prefix`.

CookieGuard looks up in that order and stops at the first hit. On real sites, 9 cookies in 10 hit.

A `tracker` label means the website itself declared the cookie as Analytics, Statistics, or
Advertising in its Cookiebot or OneTrust banner; `not-tracker` means Necessary, Functional, or
Preference. Sites disagree about some names (`__cf_bm` is declared both ways); the table records
the majority and the vote counts so you can set your own threshold.

## Cookies observed in 2026

One row per cookie that a real website set after "Accept all" and also listed in its own cookie
declaration. Three crawls of the Tranco top-20,000 list (`947N2`, November 9, 2026), by rank range:

| `crawl` | Ranks | Sites | Rows | Job in our studies |
| --- | --- | ---: | ---: | --- |
| `tune` | 1–3,300 | 167 | 4,043 | threshold and method selection; never scored as a test |
| `unseen-test` | 3,401–12,560 | 262 | 1,368 | test on names never seen in training or tuning |
| `mix-test` | 12,561–20,000 | 359 | 11,160 | test on the natural mix; the 81% headline |

Columns: `rank` (Tranco rank of the visited site), `cmp` (`cookiebot` / `onetrust`),
`declaredCategory` and `declaredGroup` (the banner's own category), `name`, `normalizedName`,
`domain`, `path`, `label`, `secure`, `httpOnly`, `sameSite`, `hostOnly`, `session`,
`lifetimeSeconds` (null for session cookies), `valueLength`, `valueCharacterSet`
(`digits` / `hex` / `alphanumeric` / `base64/base64url` / `other` / `empty`), `declarationMatch`,
and for `mix-test` rows `seenInTraining` / `seenInTuning` (whether the normalized name occurs in
the 2021 training data or the `tune` crawl). `features` holds the 38 CookieGuard model inputs in
the order given by `featureNames` in `stats.json` (array in JSONL, one column each in CSV).

Only sites running Cookiebot or OneTrust with a parseable declaration are represented
(4.8% of attempted sites). The crawl visited each site once, from one US location, with a
desktop Chrome user agent.

## License and attribution

- The CookieGuard tables and the 2026 crawl rows: **CC BY 4.0**. Please cite:
  *Avelyn Jing, CookieGuard AI cookie database, November 2026, https://aiscihub.github.io/cookieguard-ai/database.html*
- 2021 votes derive from the CookieBlock dataset: Bollinger, Kubicek, Cotrini, Basin,
  "Automating Cookie Consent and GDPR Violation Detection," USENIX Security 2022; Zenodo
  record 5838646; CC BY 4.0.
- `ocd` entries are redistributed from the Open Cookie Database under Apache-2.0, unchanged
  except for the binary label mapping; their `ocdIds` link back to the source records.
- Site ranks come from the Tranco list (Le Pochat et al., NDSS 2019), <https://tranco-list.eu/list/947N2>.

## Rebuilding

`python3 data/build.py` rewrites every file here from the frozen study artifacts (the
`waicy_2026/` study folder, kept with the WAICY 2026 entry and not yet in this repository). It
never reads a cookie value because the study artifacts contain none. The files above are the
build's output as of the date in `stats.json`.
