# MCP release checklist

`@aiscihub/cookieguard-mcp` 0.3.0 was [published to npm](https://www.npmjs.com/package/@aiscihub/cookieguard-mcp)
on 2026-11-08 under the `latest` dist-tag, together with `@aiscihub/cookieguard-core`,
`cookieguard-ci`, and `@aiscihub/cookieguard-playwright` 0.3.0. See the
[0.3.0 publication record](VALIDATION.md#030-publication--2026-11-08). The MCP Registry
still lists 0.2.0. Earlier records: [0.2.0](VALIDATION.md#020-publication--2026-11-06),
[0.1.0](VALIDATION.md#010-publication--2026-11-05), and
[0.1.0-beta.1](VALIDATION.md#npm-publication--2026-11-05). The Python package stays at 0.2.0.

## 1. Review and merge

Review the implementation PR and CI results. Confirm the local stdio scope and
the startup policy/allowlist. Run these checks for the candidate if no passing
evidence already exists for its code:

```bash
npm ci
npm run test:mcp
npm run lint
npm run typecheck
npm run verify:mcp
```

The packaged-consumer check writes a tarball and checksum manifest under
`artifacts/mcp/`. Inspect the package contents and compare `package.json`'s
`mcpName` and version with `server.json`. Preserve the real output, including any
failures. Do not rerun tests merely to commit unchanged, verified code.

**Maintainer approval is required before merging or tagging.**

## 2. Publish the npm beta

Before release, verify package-name availability and the maintainer's npm scope
permissions. Prepare the publishing method using npm Trusted Publishing where
supported; use the
[official npm setup guide](https://docs.npmjs.com/trusted-publishers/).
Do not create, request, or expose API tokens. This implementation does not add an
automatic upload workflow. Any future Actions must be pinned to full commit SHAs.

**Stop for maintainer approval before any npm upload.** Publish only the reviewed
MCP package with public access; do not run a workspace-wide publish. Prereleases
such as `0.1.0-beta.1` use the `beta` dist-tag; final releases use the default `latest`. Check npm metadata, the published integrity, and
an isolated install from npm. Exercise tool discovery and the three fixture
outcomes against that installed binary.

npm uses staged publishing. The first upload of a new package creates a public
`0.0.0-stage` placeholder, and the real version goes live only after 2FA approval:
during the publish, with `npm stage approve <stage-id>`, or under **Staged Packages**
on npmjs.com. A newly published name can return 404 for a few minutes while npm's
CDN still serves an earlier cached lookup.

After a successful upload, users can configure:

```json
{
  "mcpServers": {
    "cookieguard": {
      "command": "npx",
      "args": ["--yes", "@aiscihub/cookieguard-mcp@0.3.0", "--config", "/absolute/path/cookieguard.json"]
    }
  }
}
```

## 3. Register in the MCP Registry

The registry hosts discovery metadata; the runnable package must already exist
on npm. Follow the
[official publishing guide](https://modelcontextprotocol.io/registry/quickstart)
and [npm ownership requirements](https://modelcontextprotocol.io/registry/package-types).
Use a verified `mcp-publisher` release and authenticate as the owner of the
`aiscihub` GitHub namespace. The prepared metadata requires the user to provide
an absolute path for `--config` during installation.

Validate the metadata with the publisher's `validate` command before submission.
Confirm `mcpName` in the *published* npm package matches
`io.github.aiscihub/cookieguard` exactly.

**Stop for maintainer approval before registry publication.** Once approved,
from the repository root:

```bash
mcp-publisher login github
mcp-publisher publish packages/mcp/server.json
```

Verify the registry returns that name, version, package, stdio transport, and
required configuration argument. Test the installation instructions from a
clean client. Registration does not automatically install the server in every
client or grant it access to a browser session.

## 4. Document availability

After both publications are verified, update the package README's development
notice and add the MCP link to the main README. Keep Browser Use first, followed
by the extension and CI tools as the maintainer requested. Record the published
package URL, registry entry, commit, checksums, and verification output.

For a faulty beta, deprecate the affected npm version with a clear explanation,
publish a corrected beta version, and update the registry lifecycle metadata.
Never overwrite a published artifact. Any deprecation or new publication needs
maintainer approval.
