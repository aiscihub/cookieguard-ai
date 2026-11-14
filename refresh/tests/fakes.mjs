import assert from 'node:assert/strict';

export function response(status = 200, body = '', location) {
  return { status: () => status, ok: () => status >= 200 && status < 300,
    headers: () => location ? { location } : {}, text: async () => body, dispose: async () => {} };
}
export function requestContext(handler) {
  const requests = [];
  const context = { request: { async get(url, options) {
    requests.push({ url, options });
    return handler(url, options, requests.length);
  } } };
  return { context, requests };
}
export function siteBrowser({ robots = () => response(), httpsError, httpError, documentResponded = false } = {}) {
  const frame = {}, navigations = [], requests = [];
  let listener = () => {};
  const page = {
    mainFrame: () => frame, setDefaultTimeout() {}, route: async () => {},
    on(event, callback) { assert.equal(event, 'response'); listener = callback; },
    async goto(url) {
      navigations.push(url);
      if (url.startsWith('http:') && httpError) throw new Error(httpError);
      if (url.startsWith('https:') && httpsError) {
        if (documentResponded) listener({ request: () => ({ isNavigationRequest: () => true }), frame: () => frame });
        throw new Error(httpsError);
      }
      return response();
    },
    locator: () => ({ innerText: async () => 'In-memory fixture', evaluateAll: async () => [] }),
    url: () => navigations.at(-1),
  };
  const context = {
    request: { async get(url, options) { requests.push({ url, options }); return robots(url, options); } },
    newPage: async () => page, cookies: async () => [], close: async () => {},
  };
  return { navigations, requests, browser: { async newContext(options) {
    assert.match(options.userAgent, /CookieGuardResearch\/1\.0/);
    return context;
  } } };
}
