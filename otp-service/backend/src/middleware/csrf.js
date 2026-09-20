/**
 * Double-submit CSRF protection for the public state-changing auth
 * endpoints.
 *
 * Flow:
 *   1. Client GET /api/auth/csrf -> server sets a random `csrf_token`
 *      cookie (non-httpOnly, so the owning JS can read it) and returns the
 *      same value in the JSON body.
 *   2. Client sends the value back as the `x-csrf-token` header on every
 *      non-safe method.
 *   3. Middleware compares the header against the cookie in constant time.
 *
 * A cross-site attacker cannot read the cookie or a cross-origin JSON
 * response (SameSite cookie + CORS allowlist gate the both), so a forged
 * form/fetch cannot supply the matching header.
 *
 * Enforced only when config.csrf.enabled (production by default) and only
 * on state-changing methods. Safe methods are explicitly exempt so GET
 * /api/auth/csrf and /session /me keep working.
 */
const crypto = require('crypto');
const config = require('../config/env');

const STATE_CHANGING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function tokensEqual(a, b) {
  const left = Buffer.from(String(a));
  const right = Buffer.from(String(b));
  if (left.length !== right.length) return false;
  return crypto.timingSafeEqual(left, right);
}

function csrfEnforcer() {
  return function requireCsrf(req, res, next) {
    if (!config.csrf.enabled) return next();
    if (!STATE_CHANGING_METHODS.has(req.method)) return next();

    const cookieToken = req.cookies && req.cookies[config.csrf.cookieName];
    const headerToken = req.get('x-csrf-token');

    if (!cookieToken || !headerToken || !tokensEqual(cookieToken, headerToken)) {
      return res.status(403).json({
        success: false,
        error: 'csrf_failed',
        message: 'CSRF token missing or invalid. Refresh the page and try again.',
      });
    }

    return next();
  };
}

module.exports = { csrfEnforcer, tokensEqual };