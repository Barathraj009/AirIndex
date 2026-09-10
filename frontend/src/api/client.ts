const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://airindex-backend.onrender.com/api'

function getToken(): string | null {
  return localStorage.getItem('airindex_access_token')
}

function getRefreshToken(): string | null {
  return localStorage.getItem('airindex_refresh_token')
}

function storeTokens(access: string, refresh: string) {
  localStorage.setItem('airindex_access_token', access)
  localStorage.setItem('airindex_refresh_token', refresh)
}

function clearTokens() {
  localStorage.removeItem('airindex_access_token')
  localStorage.removeItem('airindex_refresh_token')
}

function redirectToLogin() {
  clearTokens()
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

let refreshInFlight: Promise<boolean> | null = null

async function refreshSession(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  // De-duplicate concurrent refresh attempts across parallel requests.
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) return false
      const data = await res.json()
      storeTokens(data.access_token, data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

async function request<T>(path: string, options: RequestInit = {}, retryOn401 = true): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (res.status === 401 && retryOn401) {
    const refreshed = await refreshSession()
    if (refreshed) {
      return request<T>(path, options, false)
    }
    redirectToLogin()
    throw new Error('API 401 Not authenticated')
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T,>(path: string) => request<T>(path, { method: 'DELETE' }),
}