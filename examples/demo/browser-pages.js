// Presentation for the opt-in browser demo. No cookie values or policy verdicts
// are rendered here; the real CookieGuard result comes from the Playwright test.
export function browserDemoPage(authenticated = false) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CookieGuard CI — ${authenticated ? 'Login succeeded' : 'Local login demo'}</title>
  <link rel="icon" href="data:,">
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f6fa; color: #14243a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { height: 92px; padding: 0 68px; display: flex; align-items: center; justify-content: space-between; background: #14243a; color: white; }
    .brand { font-size: 25px; font-weight: 750; letter-spacing: -.5px; }
    .local { color: #b9c8dc; font-size: 14px; letter-spacing: 1.5px; }
    main { max-width: 1060px; margin: 38px auto; }
    .steps { display: flex; gap: 30px; margin-bottom: 26px; color: #536880; font-size: 16px; }
    .steps strong { color: #14243a; }
    .card { background: white; border: 1px solid #dbe3ee; border-radius: 18px; padding: 40px 48px; box-shadow: 0 12px 30px #14243a08; }
    .badge { display: inline-block; border-radius: 30px; background: #e9effa; color: #2859a1; padding: 8px 13px; font-size: 13px; font-weight: 700; letter-spacing: 1px; }
    .success { background: #e1f5ed; color: #146441; }
    h1 { font-size: 44px; line-height: 1.15; letter-spacing: -1.5px; margin: 22px 0 16px; }
    p { font-size: 20px; line-height: 1.5; color: #536880; max-width: 800px; margin: 0 0 24px; }
    .login { display: inline-block; padding: 17px 26px; background: #275ed4; color: white; border-radius: 9px; text-decoration: none; font-size: 20px; font-weight: 650; }
    .login:hover, .login:focus-visible { background: #1946aa; outline: 4px solid #c4d5ff; outline-offset: 4px; }
    .session { display: flex; gap: 44px; padding: 18px 0 0; border-top: 1px solid #e2e8f0; font-size: 17px; }
    .session span { color: #536880; margin-right: 10px; }
    footer { margin-top: 26px; font-size: 17px; color: #536880; }
    footer strong { color: #14243a; }
  </style>
</head>
<body>
  <header><span class="brand">CookieGuard CI</span><span class="local">LOCAL BROWSER DEMO</span></header>
  <main>
    <nav class="steps" aria-label="Demo workflow"><span>1 &nbsp; Login</span><span>2 &nbsp; Session</span><strong>3 &nbsp; Cookie policy</strong></nav>
    <section class="card">
      <span class="badge${authenticated ? ' success' : ''}">${authenticated ? 'AUTHENTICATED' : 'PLAYWRIGHT LOGIN'}</span>
      <h1>${authenticated ? 'Login succeeded.' : 'Sign in to the demo'}</h1>
      <p>${authenticated
    ? 'The server accepted the session cookie. A successful login still needs a cookie security check.'
    : 'Playwright will click the login link and create a local session. No passwords or external services.'}</p>
      ${authenticated
    ? '<div class="session"><div><span>Session cookie</span><strong>session_id</strong></div><div><span>Signed in as</span><strong>Demo user</strong></div></div>'
    : '<a class="login" href="/session">Create demo session &rarr;</a>'}
    </section>
    <footer><strong>Login success ≠ cookie security.</strong> Watch the terminal for the CookieGuard policy result.</footer>
  </main>
</body>
</html>`;
}
