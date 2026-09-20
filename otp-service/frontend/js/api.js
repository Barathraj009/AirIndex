/**
 * Thin wrapper around fetch() for the OTP auth API.
 * Centralizes error normalization so UI code never has to think about
 * HTTP status codes or JSON parsing directly.
 */
const OtpAuthApi = (function () {
  function baseUrl() {
    return (window.OtpAuthConfig && window.OtpAuthConfig.apiBaseUrl) || '/api/auth';
  }

  // Bootstraps the double-submit CSRF token once per page load. Returns the
  // token from the /csrf JSON body (works same-origin and cross-origin with
  // CORS). The server also sets a matching cookie; enforcement compares the
  // header to that cookie in constant time. If /csrf is unavailable (e.g. a
  // host that didn't mount it) every state-changing call simply continues
  // without the header — the module server ignores it when CSRF is off.
  let csrfTokenPromise = null;
  function getCsrfToken() {
    if (!csrfTokenPromise) {
      csrfTokenPromise = (async () => {
        try {
          const response = await fetch(`${baseUrl()}/csrf`, {
            method: 'GET',
            credentials: 'include',
          });
          if (!response.ok) return '';
          const data = await response.json().catch(() => ({}));
          return (data && data.csrfToken) || '';
        } catch (e) {
          return '';
        }
      })();
    }
    return csrfTokenPromise;
  }

  async function request(path, body) {
    return doFetch(path, body ? { method: 'POST', body } : {});
  }

  async function doFetch(path, { method = 'POST', body } = {}) {
    let response;
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (method === 'POST') {
        const csrfToken = await getCsrfToken().catch(() => '');
        if (csrfToken) headers['x-csrf-token'] = csrfToken;
      }
      const init = {
        method,
        headers,
        credentials: 'include',
      };
      if (body) init.body = JSON.stringify(body);
      response = await fetch(`${baseUrl()}${path}`, init);
    } catch (networkErr) {
      const err = new Error('We couldn\'t reach the server. Check your connection and try again.');
      err.code = 'NETWORK_ERROR';
      throw err;
    }

    let data = null;
    try {
      data = await response.json();
    } catch (parseErr) {
      const err = new Error('Something went wrong. Please try again.');
      err.code = 'SERVER_ERROR';
      throw err;
    }

    if (!response.ok || !data.success) {
      const err = new Error(data.message || 'Something went wrong. Please try again.');
      err.code = data.error || 'UNKNOWN_ERROR';
      err.meta = data;
      throw err;
    }

    return data;
  }

  return {
    sendOtp: (email) => request('/send-otp', { email }),
    resendOtp: (email) => request('/resend-otp', { email }),
    verifyOtp: (email, otp) => request('/verify-otp', { email, otp }),
    logout: () => request('/logout', {}),
    me: () => doFetch('/me', { method: 'GET' }),
    session: () => doFetch('/session', { method: 'GET' }),
  };
})();
