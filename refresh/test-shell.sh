#!/bin/sh
set -eu
# Inject the candidate into npm's test command and Node test workers. Do not use
# NODE_OPTIONS: it also alters child CLI/Action processes that test opt-in semantics.
test "${npm_lifecycle_event:-}" = test
test "${npm_lifecycle_script:-}" = 'node --import ./tests/fixtures/disable-usage.mjs --test --test-timeout=30000 tests/*.test.js'
exec node --import "$COOKIEGUARD_REFRESH_PRELOAD" --import ./tests/fixtures/disable-usage.mjs --test --test-timeout=30000 tests/*.test.js
