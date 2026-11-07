// App versions for the security-gate comparison. Each is the auth-testing fixture
// (Acme Notes) with exact edits; `count` is how many times `find` must match.
// `expected` is the correct CI decision and verdict for the configured requirements:
// both credential cookies HttpOnly, Secure, SameSite Lax or Strict; logout revokes them.
const SID = "res.cookie('sid', sid, { httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: SESSION_TTL_MS });";
const sid = replace => [{ file: 'app.js', find: SID, replace }];

export const VARIANTS = {
  fixed: { expected: 'PASS', kind: 'secure', edits: [] },
  'strict-samesite': { expected: 'PASS', kind: 'secure', note: 'sid uses SameSite=Strict, also allowed',
    edits: sid(SID.replace("sameSite: 'lax'", "sameSite: 'strict'")) },
  'malformed-header': { expected: 'PASS', kind: 'secure', note: 'extra malformed Set-Cookie headers that carry the session value; not a configured credential',
    edits: [{ file: 'app.js', find: SID, replace: `${SID}
    res.append('Set-Cookie', \`legacy_sid=\${sid}; HttpOnly; Secure; SameSite=Bogus; Max-Age=abc; Path\`);
    res.append('Set-Cookie', \`=\${sid}; Secure\`);
    res.append('Set-Cookie', \`sid_backup\${sid}\`);` }] },
  'no-httponly': { expected: 'FAIL', kind: 'flaw', edits: sid(SID.replace('httpOnly: true, ', '')) },
  'no-secure': { expected: 'FAIL', kind: 'flaw', edits: sid(SID.replace('secure: true, ', '')) },
  'samesite-none': { expected: 'FAIL', kind: 'flaw', edits: sid(SID.replace("sameSite: 'lax'", "sameSite: 'none'")) },
  'js-token': { expected: 'FAIL', kind: 'flaw', note: 'the API token is stored by page script in a readable cookie',
    edits: [
      { file: 'app.js',
        find: "    res.cookie('api_token', token, { httpOnly: true, secure: true, sameSite: 'strict', path: '/', maxAge: API_TOKEN_TTL_MS });\n    res.json({ ok: true });\n",
        replace: '    res.json({ token, maxAge: API_TOKEN_TTL_MS / 1000 });\n' },
      { file: 'public/app.js',
        find: "  await fetch('/api/token', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken() } });\n",
        replace: "  const response = await fetch('/api/token', { method: 'POST', headers: { 'X-CSRF-Token': csrfToken() } });\n  if (!response.ok) return;\n  const { token, maxAge } = await response.json();\n  document.cookie = `api_token=${token}; path=/; max-age=${maxAge}; samesite=strict; secure`;\n" },
    ] },
  'logout-kept': { expected: 'FAIL', kind: 'flaw', note: 'logout clears the cookie but keeps the server session',
    edits: [{ file: 'app.js', find: '    sessions.delete(req.cookies.sid);\n    apiTokens.delete(req.cookies.api_token);\n',
      replace: '    apiTokens.delete(req.cookies.api_token);\n' }] },
  'renamed-cookie': { expected: 'INCOMPLETE', kind: 'evidence', note: 'secure app whose session cookie is now session_id; the configured name sid is never observed',
    edits: [
      { file: 'app.js', find: 'req.cookies.sid', replace: 'req.cookies.session_id', count: 4 },
      { file: 'app.js', find: "res.cookie('sid',", replace: "res.cookie('session_id',", count: 1 },
      { file: 'app.js', find: "res.clearCookie('sid',", replace: "res.clearCookie('session_id',", count: 1 },
    ] },
  'login-broken': { expected: 'INCOMPLETE', kind: 'evidence', note: 'sign-in rejects the valid password, so no session is created',
    edits: [{ file: 'app.js', find: '  return Boolean(user) && timingSafeEqual(hash, user.hash);', replace: '  return false && Boolean(user) && timingSafeEqual(hash, user.hash);' }] },
  'replay-error': { expected: 'INCOMPLETE', kind: 'evidence', note: 'requests to the protected API without a valid session drop the connection, so revocation cannot be checked',
    edits: [{ file: 'app.js', find: "    const user = apiUser(req);\n    if (!user) return res.status(401).json({ error: 'Not signed in.' });\n    res.json({ notes: notes.get(user) ?? [] });",
      replace: "    const user = apiUser(req);\n    if (!user) return req.socket.destroy();\n    res.json({ notes: notes.get(user) ?? [] });" }] },
};

export const APP_FILES = ['app.js', 'server.js', 'public/app.js', 'public/style.css'];

export function variantFiles(pristine, name) {
  const variant = VARIANTS[name];
  if (!variant) throw new Error(`Unknown variant ${name}`);
  const files = { ...pristine };
  for (const { file, find, replace, count = 1 } of variant.edits) {
    const found = files[file].split(find).length - 1;
    if (found !== count) throw new Error(`${name}: edit to ${file} matched ${found} times, expected ${count}`);
    files[file] = files[file].split(find).join(replace);
  }
  return files;
}
