import express from 'express';
import { randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import { fileURLToPath } from 'node:url';

// Demo account for local development and tests.
export const DEMO_USER = { username: 'alice', password: 'correct-horse-battery' };

const SESSION_TTL_MS = 60 * 60 * 1000;
const API_TOKEN_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const salt = randomBytes(16);
const users = new Map([[DEMO_USER.username, { name: 'Alice', hash: scryptSync(DEMO_USER.password, salt, 32) }]]);

function parseCookies(header = '') {
  const cookies = {};
  for (const part of header.split(';')) {
    const index = part.indexOf('=');
    if (index > 0) cookies[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
  }
  return cookies;
}

function checkPassword(username, password) {
  const user = users.get(username);
  const hash = scryptSync(String(password ?? ''), salt, 32);
  return Boolean(user) && timingSafeEqual(hash, user.hash);
}

// Where to go after signing in.
function safeNext(next) {
  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/notes';
  return next;
}

const escapeHtml = value => String(value).replace(/[&<>"']/g, char => `&#${char.charCodeAt(0)};`);

function page(title, body) {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>${title} · Acme Notes</title><link rel="stylesheet" href="/style.css"></head>
<body><main>${body}</main></body>
</html>`;
}

function loginPage({ csrf, next = '', error = '' }) {
  return page('Sign in', `<h1>Acme Notes</h1>
<form method="post" action="/login">
  <input type="hidden" name="csrf" value="${escapeHtml(csrf)}">
  <input type="hidden" name="next" value="${escapeHtml(next)}">
  <label>Username <input name="username" autocomplete="username" required></label>
  <label>Password <input name="password" type="password" autocomplete="current-password" required></label>
  <button type="submit">Sign in</button>
</form>
${error ? `<p role="alert">${escapeHtml(error)}</p>` : ''}`);
}

export function createApp() {
  const sessions = new Map();
  const apiTokens = new Map();
  const notes = new Map([[DEMO_USER.username, [{ text: 'Welcome to Acme Notes' }]]]);
  const app = express();
  app.disable('x-powered-by');
  app.use(express.urlencoded({ extended: false }));
  app.use(express.json());
  app.use(express.static(fileURLToPath(new URL('./public', import.meta.url))));

  app.use((req, res, next) => {
    req.cookies = parseCookies(req.headers.cookie);
    const session = sessions.get(req.cookies.sid);
    if (session && session.expires > Date.now()) req.user = session.username;
    else if (session) sessions.delete(req.cookies.sid);
    // Display preference only.
    if (!req.cookies.theme) res.cookie('theme', 'light', { path: '/', sameSite: 'lax', maxAge: 365 * 24 * 60 * 60 * 1000 });
    next();
  });

  // Double-submit CSRF token. The page script sends it back in a header, so it is readable.
  function csrfToken(req, res) {
    if (req.cookies.csrf_token) return req.cookies.csrf_token;
    const token = randomBytes(18).toString('base64url');
    res.cookie('csrf_token', token, { path: '/', sameSite: 'strict', secure: true });
    return token;
  }
  const validCsrf = (req, value) => Boolean(req.cookies.csrf_token) && value === req.cookies.csrf_token;

  // The signed-in user for API requests: the page session or an API token.
  function apiUser(req) {
    return req.user ?? apiTokens.get(req.cookies.api_token);
  }

  app.get('/health', (req, res) => res.type('text').send('ok'));
  app.get('/', (req, res) => res.redirect(303, req.user ? '/notes' : '/login'));

  app.get('/login', (req, res) => {
    if (req.user) return res.redirect(303, '/notes');
    res.send(loginPage({ csrf: csrfToken(req, res), next: typeof req.query.next === 'string' ? req.query.next : '' }));
  });

  app.post('/login', (req, res) => {
    if (!validCsrf(req, req.body.csrf)) return res.status(403).send(page('Forbidden', '<p>Invalid form token. Reload and try again.</p>'));
    if (!checkPassword(req.body.username, req.body.password)) {
      return res.status(401).send(loginPage({ csrf: req.cookies.csrf_token, next: req.body.next, error: 'Invalid username or password.' }));
    }
    sessions.delete(req.cookies.sid);
    const sid = 'sess_' + randomBytes(16).toString('hex');
    sessions.set(sid, { username: req.body.username, expires: Date.now() + SESSION_TTL_MS });
    res.cookie('sid', sid, { httpOnly: true, secure: true, sameSite: 'lax', path: '/', maxAge: SESSION_TTL_MS });
    res.redirect(303, safeNext(req.body.next));
  });

  app.get('/notes', (req, res) => {
    if (!req.user) return res.redirect(303, '/login?next=/notes');
    res.send(page('Notes', `<h1>Notes for ${escapeHtml(users.get(req.user).name)}</h1>
<ul id="notes"></ul>
<form id="add-note"><label>New note <input name="text" required></label> <button type="submit">Add</button></form>
<form method="post" action="/logout"><input type="hidden" name="csrf" value="${escapeHtml(csrfToken(req, res))}"><button type="submit">Sign out</button></form>
<script type="module" src="/app.js"></script>`));
  });

  // A longer-lived token for the notes API, issued to the page after sign-in.
  app.post('/api/token', (req, res) => {
    if (!req.user) return res.status(401).json({ error: 'Not signed in.' });
    if (!validCsrf(req, req.get('X-CSRF-Token'))) return res.status(403).json({ error: 'Invalid CSRF token.' });
    const token = 'tok_' + randomBytes(16).toString('hex');
    apiTokens.set(token, req.user);
    res.cookie('api_token', token, { httpOnly: true, secure: true, sameSite: 'strict', path: '/', maxAge: API_TOKEN_TTL_MS });
    res.json({ ok: true });
  });

  app.get('/api/notes', (req, res) => {
    const user = apiUser(req);
    if (!user) return res.status(401).json({ error: 'Not signed in.' });
    res.json({ notes: notes.get(user) ?? [] });
  });

  app.post('/api/notes', (req, res) => {
    const user = apiUser(req);
    if (!user) return res.status(401).json({ error: 'Not signed in.' });
    if (!validCsrf(req, req.get('X-CSRF-Token'))) return res.status(403).json({ error: 'Invalid CSRF token.' });
    const text = String(req.body?.text ?? '').trim().slice(0, 500);
    if (!text) return res.status(400).json({ error: 'Note text is required.' });
    if (!notes.has(user)) notes.set(user, []);
    notes.get(user).push({ text });
    res.status(201).json({ ok: true });
  });

  app.post('/logout', (req, res) => {
    if (!validCsrf(req, req.body.csrf)) return res.status(403).send(page('Forbidden', '<p>Invalid form token.</p>'));
    sessions.delete(req.cookies.sid);
    apiTokens.delete(req.cookies.api_token);
    res.clearCookie('sid', { httpOnly: true, secure: true, sameSite: 'lax', path: '/' });
    res.clearCookie('api_token', { httpOnly: true, secure: true, sameSite: 'strict', path: '/' });
    res.redirect(303, '/login');
  });

  return app;
}
