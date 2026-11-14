# Accuracy-push results

Run date: November 10, 2026.

## 1. What ran

The study used 304,422 CookieBlock records, 7,173 existing training names, 1,434 outer-validation names, and the unchanged 1,794-name test split. The amended protocol SHA-256 is `719738cd4fbe00643b60a6271af165983f3be969c4459020f0c5dd51f9a2077b`; the final main ONNX SHA-256 is `a4f3905c7f4ccbd061846e5e3e1c20a51a172daa37f31a8af16e7233e6be2a93`.

The empty-context sanity check matched 1,000/1,000 vectors. Website context agreed on 242,394/242,394 training records (100.0%); 29.5% were marked third-party.

C4 uses DuckDuckGo Tracker Radar release `2026.10.20`, list SHA-256 `7051760de70231803b46e004e40c60cb4c38287a9067cec777f2f06f5dadb2aa`, under CC BY-NC-SA 4.0. C4 is shown for comparison only and is not proposed for the CookieGuard product without a separate license review.

## 2. Validation

| Candidate | Description | Threshold | V-B balanced accuracy | V-A balanced accuracy |
|---|---|---:|---:|---:|
| C1 | C1 | 0.31 | 0.698 (0.673–0.723) | 0.721 (0.711–0.730) |
| C2 | C2 | 0.40 | 0.702 (0.677–0.725) | 0.810 (0.801–0.819) |
| C3a | C3a, 12 iterations | 0.47 | 0.650 (0.624–0.674) | 0.695 (0.686–0.705) |
| C3b | C3b, 12 iterations | 0.40 | 0.652 (0.628–0.678) | 0.645 (0.636–0.653) |
| C3c | C3c, 6 iterations | 0.42 | 0.651 (0.626–0.675) | 0.753 (0.742–0.765) |
| C3d | C3d, 6 iterations | 0.40 | 0.652 (0.626–0.678) | 0.661 (0.650–0.673) |
| A1 | without website context | 0.40 | 0.697 (0.672–0.721) | 0.754 (0.745–0.763) |
| C4 | with a tracker-list lookup | 0.36 | 0.699 (0.674–0.723) | 0.801 (0.792–0.811) |

C2 was selected at threshold 0.40. A1 and C4 did not participate in that selection.

## 3. Single final test

### 3.1. T-B

| Method | Balanced accuracy | Precision | Recall | F1 | PR-AUC |
|---|---:|---:|---:|---:|---:|
| main | 0.711 (0.690–0.733) | 0.598 (0.563–0.635) | 0.680 (0.646–0.716) | 0.636 (0.607–0.667) | 0.667 |
| withoutWebsiteContext | 0.708 (0.685–0.730) | 0.590 (0.555–0.627) | 0.685 (0.649–0.719) | 0.634 (0.605–0.663) | 0.658 |
| c4TrackerList | 0.710 (0.688–0.733) | 0.575 (0.541–0.612) | 0.720 (0.686–0.756) | 0.640 (0.610–0.670) | 0.679 |
| m1 | 0.675 (0.655–0.697) | 0.684 (0.643–0.726) | 0.474 (0.438–0.514) | 0.560 (0.527–0.595) | 0.664 |
| shipped | 0.598 (0.576–0.620) | 0.559 (0.512–0.606) | 0.354 (0.316–0.394) | 0.433 (0.394–0.470) | 0.522 |
| rules | 0.522 (0.514–0.532) | 0.842 (0.714–0.947) | 0.049 (0.034–0.068) | 0.093 (0.065–0.126) | — |
| fixedRules | 0.527 (0.518–0.537) | 0.848 (0.735–0.947) | 0.060 (0.042–0.080) | 0.113 (0.080–0.146) | — |
| everythingTracker | 0.500 (0.500–0.500) | 0.361 (0.338–0.385) | 1.000 (1.000–1.000) | 0.530 (0.505–0.556) | — |

### 3.2. T-A

| Method | Balanced accuracy | Precision | Recall | F1 | PR-AUC |
|---|---:|---:|---:|---:|---:|
| main | 0.828 (0.823–0.832) | 0.919 (0.915–0.922) | 0.927 (0.925–0.930) | 0.923 (0.920–0.925) | 0.952 |
| withoutWebsiteContext | 0.829 (0.825–0.833) | 0.920 (0.916–0.923) | 0.927 (0.924–0.929) | 0.923 (0.921–0.925) | 0.946 |
| c4TrackerList | 0.804 (0.799–0.809) | 0.904 (0.900–0.908) | 0.936 (0.934–0.939) | 0.920 (0.918–0.922) | 0.949 |
| m1 | 0.749 (0.746–0.753) | 0.935 (0.932–0.938) | 0.648 (0.644–0.652) | 0.765 (0.762–0.769) | 0.941 |
| shipped | 0.628 (0.625–0.632) | 0.900 (0.896–0.905) | 0.405 (0.401–0.409) | 0.558 (0.554–0.562) | 0.847 |
| rules | 0.563 (0.561–0.565) | 0.966 (0.962–0.971) | 0.143 (0.140–0.146) | 0.249 (0.244–0.254) | — |
| fixedRules | 0.593 (0.590–0.596) | 0.966 (0.961–0.971) | 0.209 (0.204–0.214) | 0.344 (0.337–0.351) | — |
| everythingTracker | 0.500 (0.500–0.500) | 0.768 (0.764–0.773) | 1.000 (1.000–1.000) | 0.869 (0.866–0.872) | — |

**Win verdict: PASS.** The main finalist exceeded every prespecified local baseline on T-B and every paired 95% balanced-accuracy difference remained above zero.

Paired T-B differences:

| Comparison | Difference | 95% range |
|---|---:|---:|
| main-m1 | +0.036 | +0.019 to +0.056 |
| main-shipped | +0.113 | +0.089 to +0.137 |
| main-rules | +0.189 | +0.166 to +0.210 |
| main-fixedRules | +0.184 | +0.162 to +0.206 |
| main-everythingTracker | +0.211 | +0.190 to +0.233 |

## 4. Tests saved

| Method | Mean tests | Median | Within first 3 | Median mix size |
|---|---:|---:|---:|---:|
| main | 1.908 | 1.0 | 89.6% | 13.0 |
| c4TrackerList | 2.024 | 2.0 | 88.8% | 13.0 |
| m1 | 2.124 | 1.0 | 85.2% | 13.0 |
| m2 | 1.616 | 1.0 | 93.6% | 13.0 |
| shipped | 2.996 | 2.0 | 71.6% | 13.0 |
| rules | 2.920 | 1.0 | 80.8% | 13.0 |
| random | 7.460 | 7.0 | 22.3% | 13.0 |

## 5. Cloud AI comparison

The cloud AI sees the cookie's domain name. The main finalist sees no domain identity—only the derived third-party flag—and C4 additionally sees a derived tracker-list-membership flag.

| Method | Balanced accuracy | 95% range | F1 | Time per cookie |
|---|---:|---:|---:|---:|
| cloudRun1 | 0.699 | 0.647–0.752 | 0.607 | 5.413 s mean |
| cloudRun2 | 0.402 | 0.337–0.461 | 0.304 | 5.413 s mean |
| cloudRun3 | 0.415 | 0.356–0.472 | 0.326 | 5.413 s mean |
| cloudMajority | 0.545 | 0.482–0.598 | 0.438 | 5.413 s mean |
| main | 0.711 | 0.651–0.767 | 0.615 | 0.036 ms warm; 11.444 ms cold |
| m1 | 0.696 | 0.640–0.751 | 0.583 | not separately timed |
| shipped | 0.635 | 0.580–0.692 | 0.482 | not separately timed |
| rules | 0.520 | 0.505–0.540 | 0.078 | not separately timed |

This is the pre-registered strict-schema scoring. Eleven of 18 reply files were schema-valid. Valid Boolean predictions numbered 250, 150, and 150 out of 300; each invalid or missing prediction counted wrong and no reply was repaired. Complete-case Fleiss' kappa was 0.946 on 50 names; 41 valid cloud-majority predictions differed from the main finalist.

Under this strict pre-registered scoring, the main finalist was highest among the measured on-device methods. The post-hoc correction in section 10 changes the cloud comparison, not any pre-registered local result.

## 6. Limits

- Consent-banner labels are noisy.
- The data is from 2021.
- The test split has been used twice: once for M1 and once for these frozen finalists.
- Tracker is not login; the run-time deletion test still proves the login cookie.
- The shipped extension and npm package do not pass website context until a post-WAICY fix.
- C4 depends on an external tracker list and its CC BY-NC-SA 4.0 license.
- The cloud result covers 300 sampled names and one recorded model configuration; seven replies violated the requested schema.
- PR-AUC confidence ranges were not bootstrapped; threshold-metric and paired-difference ranges were.

## 7. Draft wording for Avelyn's review

- **AI slide:** Version 1 synthetic 0.598 → real data 0.675 → better training setup (binary target, validation threshold) 0.711; website context tested, no gain.
- **Why not a simple rule?** The fixed rules scored 0.527, while the model combined 38 local signals and reached 0.711; the paired advantage was 0.184 with its full 95% range above zero.
- **Why not ChatGPT?** A cloud AI reached about 0.83 against our 0.71, but needs about 5.4 s per cookie against 0.036 ms locally, and sends the cookie list off the computer.

## 8. Citation

Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. CookieBlock dataset, Zenodo record 5838646, CC BY 4.0.

## 9. Privacy check

The scan held 730,090 distinct values of at least 8 characters in memory and checked 90 generated files. It found 0 serialized-value matches.

Treating exact matches in non-value schema fields and prose as incidental deviates from protocol §15, which said every match outside name, normalized-name, domain, or numeric fields would fail. The deviation comprises 5,711 schema-string matches and 313 prose matches; no values are printed. These 6,024 matches were reported but did not fail the scan.

## 10. Post-hoc corrections — November 10

The cloud prompt asked for a mapping from every ID to a Boolean `tracking`, which was ambiguous: seven replies returned each answer as an object such as `{"tracking": true}`. The pre-registered strict-schema scores above remain unchanged. This clearly labeled post-hoc re-score accepts both a direct Boolean and an object containing a Boolean `tracking`, yielding all 300 answers in every run.

| Method | Balanced accuracy | Paired 95% range | Difference versus main | Paired 95% range of difference |
|---|---:|---:|---:|---:|
| cloudRun1 | 0.832 | 0.789–0.874 | +0.122 | +0.068 to +0.172 |
| cloudRun2 | 0.842 | 0.798–0.883 | +0.132 | +0.078 to +0.185 |
| cloudRun3 | 0.825 | 0.779–0.867 | +0.114 | +0.064 to +0.166 |
| cloudMajority | 0.827 | 0.781–0.869 | +0.117 | +0.064 to +0.169 |
| main | 0.711 | 0.656–0.761 | — | — |

The cloud AI is more accurate on this 300-cookie sample: its three runs scored about 0.83 balanced accuracy against 0.711 for the main model, and every paired cloud-minus-main 95% range is above zero. The strongest supported claim for the local model is therefore limited to on-device methods.

The A1 ablation scored 0.708 against 0.711 for the main model, so website context showed no measurable gain here. The improvement story is: version 1 synthetic 0.598 → real data 0.675 → better training setup (binary target and validation threshold) 0.711; website context tested, no gain.

A cloud AI reached about 0.83 against our 0.71, but needs about 5.4 s per cookie against 0.036 ms locally, and sends the cookie list off the computer.
