import { FormEvent, useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plane, Mail, KeyRound, UserPlus } from 'lucide-react'

type Step = 'email' | 'otp' | 'credentials'

export default function Login() {
  const navigate = useNavigate()

  // OTP flow state
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [maskedEmail, setMaskedEmail] = useState('')
  const [resendCooldown, setResendCooldown] = useState(0)

  // Credentials state
  const [userExists, setUserExists] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [otpToken, setOtpToken] = useState('')

  // Dev OTP display (json transport only)
  const [devOtp, setDevOtp] = useState<string | null>(null)

  useEffect(() => {
    if (resendCooldown <= 0) return
    const t = setTimeout(() => setResendCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [resendCooldown])

  const OTP_SERVICE_URL = import.meta.env.VITE_OTP_SERVICE_URL || '/otp-auth'

  const handleSendOtp = useCallback(async () => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await fetch(`${OTP_SERVICE_URL}/api/auth/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setError(body.detail || body.message || `Failed to send code (${res.status})`)
        return
      }
      const data = await res.json()
      setMaskedEmail(data.maskedEmail || email)
      setResendCooldown(data.resendCooldownSeconds || 45)
      setStep('otp')

      // Fetch dev OTP if using json transport
      try {
        const otpRes = await fetch(`${OTP_SERVICE_URL}/api/auth/dev/last-otp`)
        if (otpRes.ok) {
          const otpData = await otpRes.json()
          if (otpData.otp) setDevOtp(otpData.otp)
        }
      } catch { /* ignore */ }
    } catch {
      setError('Could not reach the OTP service. Is it running on port 4000?')
    } finally {
      setSubmitting(false)
    }
  }, [email])

  async function handleVerifyOtp(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      // Verify OTP with the OTP service
      const verifyRes = await fetch(`${OTP_SERVICE_URL}/api/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, otp: otpCode }),
      })
      if (!verifyRes.ok) {
        const body = await verifyRes.json().catch(() => ({}))
        setError(body.detail || body.message || `Verification failed (${verifyRes.status})`)
        return
      }
      const verifyData = await verifyRes.json()
      setOtpToken(verifyData.token)

      // Check if user exists
      const checkRes = await fetch(`/api/auth/check-user?email=${encodeURIComponent(email)}`, {
        method: 'POST',
      })
      if (checkRes.ok) {
        const checkData = await checkRes.json()
        setUserExists(checkData.exists)
      } else {
        setUserExists(false)
      }

      setStep('credentials')
    } catch {
      setError('Could not reach the API. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCredentialsSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      if (userExists) {
        // Login with password
        const res = await fetch('/api/auth/login-with-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setError(body.detail || `Login failed (${res.status})`)
          return
        }
        const data = await res.json()
        localStorage.setItem('airindex_access_token', data.access_token)
        localStorage.setItem('airindex_refresh_token', data.refresh_token)
        navigate('/', { replace: true })
      } else {
        // Register new user
        if (!username.trim()) {
          setError('Username is required')
          return
        }
        if (password.length < 6) {
          setError('Password must be at least 6 characters')
          return
        }

        const res = await fetch('/api/auth/register-with-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            otp: otpCode,
            username: username.trim(),
            password,
          }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setError(body.detail || `Registration failed (${res.status})`)
          return
        }
        const data = await res.json()
        localStorage.setItem('airindex_access_token', data.access_token)
        localStorage.setItem('airindex_refresh_token', data.refresh_token)
        navigate('/', { replace: true })
      }
    } catch {
      setError('Could not reach the API. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center text-white">
              <Plane size={20} />
            </div>
            <div>
              <div className="text-lg font-bold text-ink">AirIndex India</div>
              <div className="text-xs text-muted">SIH 2026 · PS 26056</div>
            </div>
          </div>

          {/* Step 1: Email */}
          {step === 'email' && (
            <form onSubmit={(e) => { e.preventDefault(); handleSendOtp() }} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="email">
                  Gmail Address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="your-email@gmail.com"
                />
              </div>

              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}

              <button
                type="submit"
                disabled={submitting || !email}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Sending…' : 'Send verification code'}
              </button>
            </form>
          )}

          {/* Step 2: OTP Verification */}
          {step === 'otp' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="text-sm text-slate-600">
                Code sent to <span className="font-medium text-slate-800">{maskedEmail}</span>
              </div>
              {devOtp && (
                <div className="bg-amber-50 border border-amber-200 rounded-md px-3 py-2 text-sm">
                  <span className="font-semibold text-amber-700">Demo mode:</span> Your code is{' '}
                  <span className="font-mono font-bold text-amber-800">{devOtp}</span>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="otp-code">
                  Verification code
                </label>
                <input
                  id="otp-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoComplete="one-time-code"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm tracking-[0.5em] text-center font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="000000"
                />
              </div>

              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}

              <button
                type="submit"
                disabled={submitting || otpCode.length !== 6}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Verifying…' : 'Verify code'}
              </button>

              <div className="text-center">
                {resendCooldown > 0 ? (
                  <span className="text-xs text-slate-400">Resend code in {resendCooldown}s</span>
                ) : (
                  <button
                    type="button"
                    onClick={handleSendOtp}
                    disabled={submitting}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Resend code
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => { setStep('email'); setOtpCode(''); setError(null) }}
                className="w-full text-xs text-slate-500 hover:text-slate-700"
              >
                Use a different email
              </button>
            </form>
          )}

          {/* Step 3: Username/Password */}
          {step === 'credentials' && (
            <form onSubmit={handleCredentialsSubmit} className="space-y-4">
              <div className="text-sm text-slate-600">
                {userExists ? (
                  <span>Logged in as <span className="font-medium text-slate-800">{email}</span></span>
                ) : (
                  <span>Create account for <span className="font-medium text-slate-800">{email}</span></span>
                )}
              </div>

              {!userExists && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="username">
                    Username
                  </label>
                  <input
                    id="username"
                    type="text"
                    required
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Choose a username"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="password">
                  {userExists ? 'Password' : 'Create password'}
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete={userExists ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={userExists ? 'Enter your password' : 'At least 6 characters'}
                />
              </div>

              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}

              <button
                type="submit"
                disabled={submitting || !password}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Please wait…' : userExists ? 'Sign in' : 'Create account & sign in'}
              </button>

              <button
                type="button"
                onClick={() => { setStep('otp'); setPassword(''); setError(null) }}
                className="w-full text-xs text-slate-500 hover:text-slate-700"
              >
                Back to verification
              </button>
            </form>
          )}
        </div>
        <p className="mt-4 text-center text-xs text-muted">
          {userExists ? 'Enter your password to sign in' : 'First time? We\'ll create your account after email verification.'}
        </p>
      </div>
    </div>
  )
}
