| Metric | A | B |
| --- | --- | --- |
| Runs (scored) | 8 (8) | 8 (8) |
| Agent finished normally | 8/8 | 8/8 |
| Suite passes on the fixed app | 7/8 | 7/8 |
| Caught the flaw it was shown: no-httponly | 0/2 | 0/2 |
| Caught the flaw it was shown: js-token | 0/2 | 0/2 |
| Caught the flaw it was shown: open-redirect | 0/2 | 0/2 |
| Suite catches no-httponly (any run) | 5/8 | 5/8 |
| Suite catches js-token (any run) | 6/8 | 6/8 |
| Suite catches open-redirect (any run) | 5/8 | 5/8 |
| Runs where a real credential reached the model | 2/8 | 2/8 |
| Used the tool under test | 0/8 | 0/8 |
| Tool check enforced in the tests | 0/8 | 0/8 |
| Runs that edited app source | 0 | 0 |
| Cost reported by the CLI (USD) | 0.96 | 0.94 |
| Agent minutes | 7.21 | 6.62 |

| Run | Shown | Passes fixed | Caught (no-httponly, js-token, open-redirect) | Credential to model | Tool used | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| fixed-A-1 | fixed | yes | ✓ ✓ ✓ | 0 | no | 0.10 |
| fixed-A-2 | fixed | yes | ✓ ✓ ✓ | 0 | no | 0.10 |
| fixed-B-1 | fixed | yes | ✓ ✓ ✓ | 0 | no | 0.11 |
| fixed-B-2 | fixed | yes | ✓ ✓ ✓ | 0 | no | 0.12 |
| js-token-A-1 | js-token | yes | ✓ · ✓ | 0 | no | 0.10 |
| js-token-A-2 | js-token | no | · · · | 0 | no | 0.11 |
| js-token-B-1 | js-token | yes | ✓ · ✓ | 0 | no | 0.13 |
| js-token-B-2 | js-token | no | · · · | 0 | no | 0.13 |
| no-httponly-A-1 | no-httponly | yes | · ✓ ✓ | 1 | no | 0.14 |
| no-httponly-A-2 | no-httponly | yes | · ✓ ✓ | 1 | no | 0.13 |
| no-httponly-B-1 | no-httponly | yes | · ✓ ✓ | 1 | no | 0.12 |
| no-httponly-B-2 | no-httponly | yes | · ✓ ✓ | 1 | no | 0.11 |
| open-redirect-A-1 | open-redirect | yes | ✓ ✓ · | 0 | no | 0.15 |
| open-redirect-A-2 | open-redirect | yes | ✓ ✓ · | 0 | no | 0.12 |
| open-redirect-B-1 | open-redirect | yes | ✓ ✓ · | 0 | no | 0.11 |
| open-redirect-B-2 | open-redirect | yes | ✓ ✓ · | 0 | no | 0.11 |
