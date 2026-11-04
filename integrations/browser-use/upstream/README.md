# Browser Use contribution review bundle

Prepared on November 4, 2026 for the optional Browser Use integration proposal.
This bundle records local verification; hosted PR checks are separate.

- [Investigation and measured results](INVESTIGATION.md)
- [Reproducible synthetic comparison](../validation/README.md)
- [Proposed PR description](PR_DESCRIPTION.md)
- [Demo and community-list patch](runnable-example.patch)
- [Listing-only fallback patch](community-list.patch)
- [Runnable example and its tests](example/README.md)
- [Stable-release verification](../validation/evidence/stable-release.json)
- [Recorded beta demo command outcomes](../validation/evidence/example-cli.json)

The selected proposal is the existing insecure-login versus secure-login demo,
plus a community-list entry. Its positioning is **CookieGuard AI: Independent
authentication-cookie security auditing for Browser Use workflows.** The small
example imports the published package's existing demo app and uses the real
Browser Use Agent loop. The listing-only patch is a fallback if maintainers
prefer an external pointer. Apply only one patch. Both target upstream commit
`b49a68e4060acb226da8f784194fef301c53a6d7`.

The example pins CookieGuard **0.1.0** and Browser Use **0.13.14**. The original
benchmark remains labeled **0.1.0b1**; stable verification records the wheel
comparison and fresh demo checks separately. Original patch hashes in the beta
provenance describe the earlier preparation; current hashes are in the stable
verification record.

From a clean Browser Use checkout:

```bash
git apply --check /path/to/cookieguard-ai/integrations/browser-use/upstream/runnable-example.patch
git apply /path/to/cookieguard-ai/integrations/browser-use/upstream/runnable-example.patch
uv run --no-sync pre-commit run --files examples/integrations/README.md \
  examples/integrations/cookieguard/cookie_policy.py \
  examples/integrations/cookieguard/test_cookie_policy.py \
  examples/integrations/cookieguard/README.md
```

Then follow the resulting `examples/integrations/cookieguard/README.md`. It adds no runtime
dependency or optional extra to Browser Use, and does not change its internals.
The example tests are opt-in; the broader benchmark remains in CookieGuard.

The submission uses a published CookieGuard evidence commit, a fresh check of
the target release and main branch, and upstream checks on the chosen patch.
The PR text distinguishes local validation from upstream hosted CI. A community
listing is not an official endorsement or support commitment.
