# CookieBlock comparison results

Run date: 2026-11-10T07:10:32.505184+00:00. Dataset MD5: `9aece7e28a54a7cfc2250f5c2861ca20`. Model SHA-256: `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2`.

Scored 304,422 cookies from 28,089 website IDs. Excluded 0 cookies for unsupported labels. Scoring phase elapsed time: 310.5 seconds; analysis elapsed time: 6.7 seconds.

## 1. Tracker detection

Each cell is point estimate (website/name bootstrap 95% range).

| View | Method | Precision | Recall | F1 | Balanced accuracy |
|---|---|---:|---:|---:|---:|
| A | Model | 0.819 (0.816–0.823) | 0.468 (0.466–0.470) | 0.596 (0.593–0.598) | 0.635 (0.634–0.637) |
| A | Rules | 0.964 (0.962–0.967) | 0.245 (0.242–0.249) | 0.391 (0.387–0.395) | 0.614 (0.612–0.616) |
| B | Model | 0.596 (0.580–0.613) | 0.268 (0.258–0.279) | 0.370 (0.358–0.382) | 0.551 (0.545–0.559) |
| B | Rules | 0.935 (0.924–0.945) | 0.339 (0.328–0.350) | 0.498 (0.486–0.509) | 0.659 (0.653–0.664) |
| C | Model | 0.595 (0.578–0.613) | 0.267 (0.257–0.277) | 0.369 (0.357–0.381) | 0.551 (0.544–0.558) |
| C | Rules | 0.936 (0.925–0.945) | 0.341 (0.329–0.352) | 0.499 (0.487–0.512) | 0.660 (0.654–0.665) |

View sizes: A = 304,422 cookies in 28,089 website clusters; B = 13,630 names; C = 13,531 unseen names.

**Main result: LOSS.** View C model-minus-rules F1 = -0.130 (95% range -0.150–-0.112). The predeclared win rule requires a difference of at least 0.05 and an interval entirely above zero.

## 2. Semi-synthetic tests saved

Eligible CookieBlock websites: 6,717. Each app uses 50 fixed-seed mixes.

| App | Method | Mean tests | Median tests | Within first 3 | Median mix size |
|---|---|---:|---:|---:|---:|
| grafana | Model | 2.82 | 2.00 | 68.0% | 15.5 |
| grafana | Rules | 1.44 | 1.00 | 100.0% | 15.5 |
| grafana | Random | 9.30 | 8.25 | 18.8% | 15.5 |
| jupyter | Model | 10.20 | 9.00 | 0.0% | 16.0 |
| jupyter | Rules | 1.14 | 1.00 | 100.0% | 16.0 |
| jupyter | Random | 9.36 | 8.50 | 18.5% | 16.0 |
| datasette | Model | 2.66 | 3.00 | 86.0% | 15.0 |
| datasette | Rules | 10.50 | 9.00 | 4.0% | 15.0 |
| datasette | Random | 9.31 | 8.00 | 18.8% | 15.0 |
| code-server | Model | 1.10 | 1.00 | 100.0% | 16.0 |
| code-server | Rules | 1.64 | 1.00 | 96.0% | 16.0 |
| code-server | Random | 9.10 | 8.50 | 19.4% | 16.0 |
| django-admin | Model | 1.54 | 1.00 | 100.0% | 16.5 |
| django-admin | Rules | 1.06 | 1.00 | 100.0% | 16.5 |
| django-admin | Random | 9.41 | 8.75 | 18.3% | 16.5 |
| overall | Model | 3.66 | 2.00 | 70.8% | 16.0 |
| overall | Rules | 3.16 | 1.00 | 80.0% | 16.0 |
| overall | Random | 9.30 | 8.50 | 18.7% | 16.0 |

App cookie names and deletion-tested login cookies:

- grafana: grafana_session, grafana_session_expiry; login cookie(s): grafana_session.
- jupyter: _xsrf, username-jupyter-localhost-8443; login cookie(s): username-jupyter-localhost-8443.
- datasette: ds_actor, ds_csrftoken; login cookie(s): ds_actor.
- code-server: code-server-session; login cookie(s): code-server-session.
- django-admin: csrftoken, sessionid; login cookie(s): sessionid.

## 3. Where each method fails

Model wrong and rules right:

- `_gid`: 17,745
- `optanonalertboxclosed`: 11,811
- `_gat`: 5,406
- `vuid`: 324
- `hubspotutk`: 304
- `machine_last_seen`: 229
- `maid`: 229
- `m`: 216
- `anx`: 204
- `_clck`: 152
- `_abck`: 151
- `ajs_anonymous_id`: 149
- `__stripe_mid`: 149
- `ai_user`: 124
- `messagesutk`: 117
- `__zlcmid`: 115
- `driftt_aid`: 111
- `_ga`: 103
- `_gcl_au`: 101
- `_pin_unauth`: 98

Rules wrong and model right:

- `ide`: 8,556
- `_fbp`: 7,784
- `bcookie`: 2,756
- `_hjid`: 2,735
- `_gcl_au`: 2,608
- `usermatchhistory`: 2,507
- `bscookie`: 2,477
- `muid`: 2,011
- `uuid2`: 1,380
- `__utmz`: 1,057
- `__utma`: 1,031
- `__gads`: 1,006
- `personalization_id`: 968
- `__hstc`: 956
- `nid`: 871
- `tuuid`: 849
- `a3`: 843
- `uuid`: 807
- `tdid`: 725
- `loc`: 707

## 4. Limits

- Consent-banner labels can be wrong.
- The dataset is from 2021.
- Necessary cookies combine login and other essential cookies, so tracker detection does not directly measure login-cookie detection.
- The tests-saved measurement is semi-synthetic.
- The app study contains only five apps, including one single-cookie app.

## 5. Draft wording for Avelyn's review

If the model wins:

- Slide line: On unseen real cookie names, CookieGuard beat the simple rules on tracking F1 and also reduced the tests needed to find app login cookies.
- Answer: The rules recognize patterns we already know. The model also combines security settings, lifetime, domain, name, and value-shape signals, and on this held-out test it performed better by the rule we fixed before running it.

If the model does not win:

- Slide line: On this held-out real-cookie test, the model did not beat the simple rules; CookieGuard therefore keeps the AI suggestion reviewable instead of treating it as automatic truth.
- Answer: This test did not show that the model is broadly better than simple rules. Its value is as a second, reviewable ranking signal in the login-cookie workflow, while the rules remain a strong baseline and the user confirms the choice.

## 6. Citation

Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. CookieBlock dataset, Zenodo record 5838646, CC BY 4.0.

## 7. Privacy check

`value_check.json` reports 0 files containing a serialized cookie value. It separately records 33 files with harmless raw substring overlaps, such as a value matching a cookie name or numeric output fragment.
