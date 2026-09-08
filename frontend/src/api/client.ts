const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function getToken(): string | null {
  return localStorage.getItem('airindex_access_token')
}

function redirectToLogin() {
  localStorage.removeItem('airindex_access_token')
  localStorage.removeItem('airindex_refresh_token')
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (res.status === 401) {
    // Token missing/expired — clear session and send the user to login.
    redirectToLogin()
    throw new Error(`API 401 Not authenticated`)
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
