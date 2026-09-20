// CSRF double-submit protection.
// NOTE: this file must set its env overrides BEFORE requiring anything
// that pulls in src/config/env.js (each test file runs in its own process).
process.env.NODE_ENV = 'test';
process.env.CSRF_ENABLED = 'true';
process.env.CSRF_COOKIE_NAME = 'csrf_token';

const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer, stopServer, post, get } = require('../testlib/helpers');

let baseUrl;
const GMAIL = 'user@gmail.com';

test.before(async () => {
  baseUrl = await startServer();
});

test.after(async () => {
  await stopServer();
});

async function fetchCsrfPair() {
  const res = await get(baseUrl, '/api/auth/csrf');
  assert.equal(res.status, 200, 'GET /api/auth/csrf should be 200');
  assert.ok(res.body.csrfToken, 'response body should carry the csrf token');
  const cookies = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  const csrfCookie = cookies.find((c) => c.startsWith('csrf_token='));
  return {
    token: res.body.csrfToken,
    cookie: csrfCookie ? csrfCookie.split(';')[0] : null,
  };
}

function browserHeaders(pair) {
  const headers = { Cookie: pair.cookie };
  if (pair.token) headers['x-csrf-token'] = pair.token;
  return headers;
}

test('GET /api/auth/csrf issues a token and sets the cookie', async () => {
  const res = await get(baseUrl, '/api/auth/csrf');
  assert.equal(res.status, 200);
  assert.ok(res.body.csrfToken && typeof res.body.csrfToken === 'string');
  assert.ok(res.body.csrfToken.length >= 32);
  const cookies = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  const csrfCookie = cookies.find((c) => c.startsWith('csrf_token='));
  assert.ok(csrfCookie, 'server should set a csrf_token cookie');
  assert.equal(csrfCookie.includes('HttpOnly'), false, 'cookie must be readable by JS (no HttpOnly)');
});

test('state-changing calls are rejected without a token when CSRF is on', async () => {
  const res = await post(baseUrl, '/api/auth/send-otp', { email: GMAIL });
  assert.equal(res.status, 403, 'send-otp without a token should be 403');
  assert.equal(res.body.error, 'csrf_failed');
});

test('state-changing calls are rejected when the header does not match', async () => {
  const pair = await fetchCsrfPair();
  const res = await post(baseUrl, '/api/auth/send-otp', { email: GMAIL }, {
    Cookie: pair.cookie,
    'x-csrf-token': 'not-the-token',
  });
  assert.equal(res.status, 403, 'mismatched header should be 403');
  assert.equal(res.body.error, 'csrf_failed');
});

test('state-changing calls proceed when the token matches', async () => {
  const pair = await fetchCsrfPair();
  const res = await post(baseUrl, '/api/auth/send-otp', { email: GMAIL }, browserHeaders(pair));
  assert.equal(res.status, 200, 'matched token should pass CSRF and reach send-otp');
  assert.equal(res.body.success, true);
});

test('safe methods stay open with CSRF on', async () => {
  const res = await get(baseUrl, '/api/auth/session');
  assert.equal(res.status, 401, '/session is safe + requires a session, but must NOT be a 403');
  assert.notEqual(res.body.error, 'csrf_failed');
});