// App versions. `fixed` is the fixture as committed; every other version applies a
// minimal edit that introduces exactly one flaw. Each `find` must match exactly once.
// Decoys present in every version: a readable `theme` preference cookie and a readable
// double-submit `csrf_token` cookie, both correct by design.
export const APP_FILES = ['app.js', 'server.js', 'public/app.js', 'public/style.css'];

export const VERSIONS = {
  fixed: { flaw: null, checkedByTool: null, edits: [] },
  'no-httponly': {
    flaw: 'Session cookie `sid` is set without HttpOnly',
    checkedByTool: true,
    edits: [{
      file: 'app.js',
      find: "res.cookie('sid', sid, { httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: SESSION_TTL_MS });",
      replace: "res.cookie('sid', sid, { secure: true, sameSite: 'lax', path: '/', maxAge: SESSION_TTL_MS });",
    }],
  },
  // Every version issues an API token after sign-in. The fixed app sets it from the
  // server as HttpOnly; this version hands it to page script, which stores it in a cookie.
  'js-token': {
    flaw: 'The API token is returned to page script and stored in a JavaScript-readable `api_token` cookie',
    checkedByTool: true,
    edits: [
      {
        file: 'app.js',
        find: "    res.cookie('api_token', token, { httpOnly: true, secure: true, sameSite: 'strict', path: '/', maxAge: API_TOKEN_TTL_MS });\n    res.json({ ok: true });\n",
        replace: '    res.json({ token, maxAge: API_TOKEN_TTL_MS / 1000 });\n',
      },
      {
        file: 'public/app.js',
        find: "  await fetch('/api/token', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken() } });\n",
        replace: [
          "  const response = await fetch('/api/token', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken() } });",
          '  if (!response.ok) return;',
          '  const { token, maxAge } = await response.json();',
          '  document.cookie = `api_token=${token}; path=/; max-age=${maxAge}; samesite=strict; secure`;',
          '',
        ].join('\n'),
      },
    ],
  },
  'open-redirect': {
    flaw: 'Sign-in redirects to any `next` URL, including other origins',
    checkedByTool: false,
    edits: [{
      file: 'app.js',
      find: "  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\\\')) return '/notes';",
      replace: "  if (typeof next !== 'string' || !next) return '/notes';",
    }],
  },
};

export const FLAWED = Object.keys(VERSIONS).filter(version => VERSIONS[version].flaw);

// Returns the content of each app file for a version, from the pristine fixture files.
export function versionFiles(pristine, version) {
  const spec = VERSIONS[version];
  if (!spec) throw new Error(`Unknown version ${version}`);
  const files = { ...pristine };
  for (const { file, find, replace } of spec.edits) {
    const count = files[file].split(find).length - 1;
    if (count !== 1) throw new Error(`${version}: edit to ${file} matched ${count} times`);
    files[file] = files[file].replace(find, () => replace);
  }
  return files;
}
