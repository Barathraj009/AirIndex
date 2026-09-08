const express = require('express');
const authController = require('../controllers/authController');
const validateEmail = require('../middleware/validateEmail');
const { requireSession } = require('../middleware/auth');
const { sendOtpLimiter, verifyOtpLimiter } = require('../middleware/rateLimiter');
const { getLastTestMessage } = require('../services/emailService');
const config = require('../config/env');

const router = express.Router();

// Auth responses (OTP status, session, cookies) must never be cached by
// the browser or any intermediary — stale copies of session data or OTP
// state can mislead a client or leak state across users on a shared proxy.
router.use((req, res, next) => {
  res.set('Cache-Control', 'no-store');
  next();
});

router.post('/send-otp', sendOtpLimiter, validateEmail, authController.sendOtp);
router.post('/resend-otp', sendOtpLimiter, validateEmail, authController.resendOtp);
router.post('/verify-otp', verifyOtpLimiter, validateEmail, authController.verifyOtp);
router.post('/logout', authController.logout);

// Integration-layer endpoints: any host app (or this demo) can call these
// with the session token to confirm "who is currently authenticated".
// `/session` and `/me` are aliases.
router.get('/session', requireSession, authController.session);
router.get('/me', requireSession, authController.session);

// Dev-only endpoint: returns the last OTP when using json transport
// (for demo/testing when SMTP is blocked, e.g. on Render free tier)
if (config.email.transport === 'json') {
  router.get('/dev/last-otp', (req, res) => {
    const msg = getLastTestMessage();
    if (!msg) {
      return res.json({ otp: null, message: 'No OTP sent yet.' });
    }
    // Extract OTP from the message body (format: "Your verification code is: 123456")
    const match = msg.text && msg.text.match(/code is: (\d{6})/);
    const otp = match ? match[1] : null;
    return res.json({ otp, message: otp ? 'Use this code to verify.' : 'Could not extract OTP.' });
  });
}

module.exports = router;