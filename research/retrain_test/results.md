# Real-cookie retraining results

Run date: 2026-11-10T07:37:14.952979+00:00.

Environment: Python 3.9.6; NumPy 1.26.4; scikit-learn 1.5.2; skl2onnx 1.17.0; ONNX Runtime 1.19.2; ONNX 1.16.2.

Dataset MD5: `9aece7e28a54a7cfc2250f5c2861ca20`. Split SHA-256: `d1dc80459727466bfd4c9128395c6c823b6802c4d5a61e94bcca73a92b34b4c5`. M1 ONNX: `3d3d46206da96d6cc8f32527a92b408c310aef872f471dc4ee15d064d1fc6cdd`. M2 ONNX: `fda09e27d4b5de367d21305aaa30f3ffd7d0b8288d962d34d4fbdc87ce84a661`. Shipped model: `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2`.

Training: 7,173 names and 242,394 cookies. Test: 1,794 names and 62,028 cookies. Total elapsed time through analysis: 830.0 seconds.

Training class counts (necessary, functional, analytics, advertising): 75,890, 14,216, 72,685, 79,603. Test class counts: 9,823, 4,567, 15,627, 32,011.

## 1. Tracker detection on test names

Each cell is estimate (paired bootstrap 95% range).

| View | Method | Precision | Recall | F1 | Balanced accuracy |
|---|---|---:|---:|---:|---:|
| T-B | M1 | 0.684 (0.643–0.726) | 0.474 (0.438–0.514) | 0.560 (0.527–0.595) | 0.675 (0.655–0.697) |
| T-B | M2 | 0.693 (0.648–0.737) | 0.408 (0.375–0.444) | 0.514 (0.479–0.550) | 0.653 (0.634–0.674) |
| T-B | Shipped model | 0.559 (0.512–0.606) | 0.354 (0.316–0.394) | 0.433 (0.394–0.470) | 0.598 (0.576–0.620) |
| T-B | Rules | 0.842 (0.714–0.947) | 0.049 (0.034–0.068) | 0.093 (0.065–0.126) | 0.522 (0.514–0.532) |
| T-B | Fixed rules | 0.848 (0.735–0.947) | 0.060 (0.042–0.080) | 0.113 (0.080–0.146) | 0.527 (0.518–0.537) |
| T-A | M1 | 0.935 (0.932–0.938) | 0.648 (0.644–0.652) | 0.765 (0.762–0.769) | 0.749 (0.746–0.753) |
| T-A | M2 | 0.947 (0.944–0.950) | 0.635 (0.631–0.640) | 0.760 (0.757–0.764) | 0.759 (0.755–0.763) |
| T-A | Shipped model | 0.900 (0.896–0.905) | 0.405 (0.401–0.409) | 0.558 (0.554–0.562) | 0.628 (0.625–0.632) |
| T-A | Rules | 0.966 (0.962–0.971) | 0.143 (0.140–0.146) | 0.249 (0.244–0.254) | 0.563 (0.561–0.565) |
| T-A | Fixed rules | 0.966 (0.961–0.971) | 0.209 (0.204–0.214) | 0.344 (0.337–0.351) | 0.593 (0.590–0.596) |

**Main verdict: WIN.** T-B M1-minus-rules F1 = 0.467 (95% range 0.421–0.507).

Prespecified paired F1 differences (left minus right):

| View | Comparison | Difference | 95% range |
|---|---|---:|---:|
| T-B | M1 − rules | 0.467 | 0.421–0.507 |
| T-B | M1 − fixed rules | 0.448 | 0.405–0.490 |
| T-B | M1 − shipped | 0.127 | 0.083–0.172 |
| T-B | M2 − M1 | -0.047 | -0.073–-0.022 |
| T-B | M2 − shipped | 0.080 | 0.037–0.126 |
| T-B | M2 − rules | 0.420 | 0.377–0.464 |
| T-B | M2 − fixed rules | 0.401 | 0.358–0.445 |
| T-A | M1 − rules | 0.516 | 0.511–0.522 |
| T-A | M1 − fixed rules | 0.421 | 0.414–0.428 |
| T-A | M1 − shipped | 0.207 | 0.203–0.211 |
| T-A | M2 − M1 | -0.005 | -0.008–-0.002 |
| T-A | M2 − shipped | 0.202 | 0.198–0.206 |
| T-A | M2 − rules | 0.512 | 0.506–0.518 |
| T-A | M2 − fixed rules | 0.416 | 0.410–0.423 |

## 2. Semi-synthetic tests saved

The app-cookie split column reports whether each normalized app-cookie name was in M1 training (`train`), held out (`test`), or absent from CookieBlock (`absent`).

| App | App cookie normalized-name split | Method | Mean tests | Median tests | Within first 3 | Median mix size |
|---|---|---|---:|---:|---:|---:|
| grafana | grafana_session: absent; grafana_session_expiry: absent | M1 | 1.42 | 1.00 | 98.0% | 13.0 |
| grafana | grafana_session: absent; grafana_session_expiry: absent | M2 | 1.16 | 1.00 | 100.0% | 13.0 |
| grafana | grafana_session: absent; grafana_session_expiry: absent | Shipped | 2.68 | 3.00 | 76.0% | 13.0 |
| grafana | grafana_session: absent; grafana_session_expiry: absent | Rules | 1.38 | 1.00 | 100.0% | 13.0 |
| grafana | grafana_session: absent; grafana_session_expiry: absent | Random | 7.40 | 7.00 | 22.2% | 13.0 |
| jupyter | _xsrf: train; username-jupyter-localhost-8443: absent | M1 | 1.22 | 1.00 | 100.0% | 13.0 |
| jupyter | _xsrf: train; username-jupyter-localhost-8443: absent | M2 | 1.12 | 1.00 | 100.0% | 13.0 |
| jupyter | _xsrf: train; username-jupyter-localhost-8443: absent | Shipped | 6.12 | 6.00 | 6.0% | 13.0 |
| jupyter | _xsrf: train; username-jupyter-localhost-8443: absent | Rules | 1.08 | 1.00 | 100.0% | 13.0 |
| jupyter | _xsrf: train; username-jupyter-localhost-8443: absent | Random | 7.50 | 7.00 | 22.0% | 13.0 |
| datasette | ds_actor: absent; ds_csrftoken: absent | M1 | 5.30 | 5.00 | 32.0% | 13.0 |
| datasette | ds_actor: absent; ds_csrftoken: absent | M2 | 3.38 | 3.00 | 70.0% | 13.0 |
| datasette | ds_actor: absent; ds_csrftoken: absent | Shipped | 2.98 | 3.00 | 76.0% | 13.0 |
| datasette | ds_actor: absent; ds_csrftoken: absent | Rules | 9.28 | 9.50 | 8.0% | 13.0 |
| datasette | ds_actor: absent; ds_csrftoken: absent | Random | 7.67 | 7.00 | 21.8% | 13.0 |
| code-server | code-server-session: absent | M1 | 1.44 | 1.00 | 96.0% | 12.0 |
| code-server | code-server-session: absent | M2 | 1.42 | 1.00 | 98.0% | 12.0 |
| code-server | code-server-session: absent | Shipped | 1.44 | 1.00 | 100.0% | 12.0 |
| code-server | code-server-session: absent | Rules | 1.84 | 2.00 | 96.0% | 12.0 |
| code-server | code-server-session: absent | Random | 6.98 | 6.50 | 24.0% | 12.0 |
| django-admin | csrftoken: test; sessionid: test | M1 | 1.24 | 1.00 | 100.0% | 13.0 |
| django-admin | csrftoken: test; sessionid: test | M2 | 1.00 | 1.00 | 100.0% | 13.0 |
| django-admin | csrftoken: test; sessionid: test | Shipped | 1.76 | 2.00 | 100.0% | 13.0 |
| django-admin | csrftoken: test; sessionid: test | Rules | 1.02 | 1.00 | 100.0% | 13.0 |
| django-admin | csrftoken: test; sessionid: test | Random | 7.75 | 7.00 | 21.8% | 13.0 |
| overall | — | M1 | 2.12 | 1.00 | 85.2% | 13.0 |
| overall | — | M2 | 1.62 | 1.00 | 93.6% | 13.0 |
| overall | — | Shipped | 3.00 | 2.00 | 71.6% | 13.0 |
| overall | — | Rules | 2.92 | 1.00 | 80.8% | 13.0 |
| overall | — | Random | 7.46 | 7.00 | 22.3% | 13.0 |

## 3. What changed from the shipped model

Most common test names that flipped from wrong to right:

- `_gat`: 5,404
- `lidc`: 2,769
- `_uetsid`: 1,576
- `_uetvid`: 1,237
- `__utmc`: 1,030
- `__utmb`: 1,025
- `hubspotutk`: 304
- `apidts`: 275
- `tapad_ts`: 258
- `maid`: 229
- `clid`: 152
- `rxvt`: 121
- `opt_out`: 114
- `_te_`: 97
- `matchgoogle`: 85

Most common test names that flipped from right to wrong:

- `usermatchhistory`: 2,507
- `hubspotutk`: 668
- `_vwo_uuid_v2`: 218
- `rxvt`: 200
- `__stripe_sid`: 145
- `_gat`: 130
- `sid`: 119
- `__adroll_fpc`: 107
- `cto_bundle`: 82
- `ytrackuser`: 82
- `optimizelydomaintestcookie`: 74
- `_uetvid`: 46
- `ac_enable_tracking`: 44
- `calltrk_session_id`: 36
- `sambapxid`: 36

Prespecified names:

- `_gid`: normalized `_gid`, split `train`.
- `_gat`: normalized `_gat`, split `test`.
- `optanonalertboxclosed`: normalized `optanonalertboxclosed`, split `train`.

## 4. Feature importance

M1 impurity importance (descriptive, not causal):

| Rank | Feature | Importance |
|---:|---|---:|
| 1 | `name_entropy` | 0.1101 |
| 2 | `name_length` | 0.1094 |
| 3 | `name_matches_tracking` | 0.0847 |
| 4 | `value_length` | 0.0748 |
| 5 | `name_has_underscore` | 0.0644 |
| 6 | `exposure_score` | 0.0642 |
| 7 | `cross_site_sendable` | 0.0590 |
| 8 | `name_matches_preference` | 0.0550 |
| 9 | `expiry_days` | 0.0531 |
| 10 | `samesite_level` | 0.0404 |

The shipped artifact contains no training impurity statistics, so exact shipped impurity importance cannot be recovered. Its ONNX split-frequency proxy is shown separately:

| Rank | Feature | Split share |
|---:|---|---:|
| 1 | `name_entropy` | 0.0917 |
| 2 | `value_length` | 0.0785 |
| 3 | `name_length` | 0.0729 |
| 4 | `path_is_root` | 0.0575 |
| 5 | `f_login_behavior_score` | 0.0491 |
| 6 | `exposure_score` | 0.0470 |
| 7 | `f_security_posture_score` | 0.0432 |
| 8 | `name_matches_auth` | 0.0414 |
| 9 | `expiry_days` | 0.0356 |
| 10 | `samesite_level` | 0.0350 |

## 5. Limits

- Consent-banner labels are noisy.
- The data is from 2021.
- Necessary is not login; the run-time deletion test remains necessary.
- M1 has no authentication class and cannot replace the shipped model inside `createOnnxClassifier`.
- M2 requires an engine change.
- Normalized-name grouping cannot remove every semantic similarity.
- Impurity importance and ONNX split frequency are descriptive and are not directly equivalent.

## 6. Draft wording for review

If M1 wins:

- Slide: Training on real cookies made the same Random Forest beat the simple rules on cookie names it never saw.
- Answer: The rules match known strings, while the real-data model combines 38 independent signals and generalized better to held-out normalized names under a test fixed before training.

If M1 does not win:

- Slide: Even after retraining on real cookies, the model did not beat the simple rules on unseen names, so CookieGuard keeps AI as a reviewable suggestion rather than a claim of superiority.
- Answer: For this year, the evidence says the simple rules are the stronger general baseline. The model can still help rank uncertain cases, but the deletion test and user confirmation are what make the workflow trustworthy.

## 7. Citation

Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. CookieBlock dataset, Zenodo record 5838646, CC BY 4.0.

## 8. Privacy check

Serialized cookie values were found in 0 output files. The raw scan also measured long incidental string overlaps in 41 files and short incidental overlaps in 49 files; these are retained in `value_check.json` with their classification reason.
