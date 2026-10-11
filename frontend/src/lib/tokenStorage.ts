// Keeps the access token in localStorage so a page reload does not log the user out.
// Trade-off: readable by any script on the page (XSS risk). Mitigations: short expiry,
// React escapes rendered text by default, no third-party scripts. See docs/phases/01-auth.md.

const KEY = 'goalwise.auth'

interface StoredToken {
  token: string
  expiresAt: number // epoch milliseconds
}

export const tokenStorage = {
  save(token: string, expiresInSeconds: number) {
    const value: StoredToken = { token, expiresAt: Date.now() + expiresInSeconds * 1000 }
    localStorage.setItem(KEY, JSON.stringify(value))
  },

  /** The stored token, or null if missing, unreadable or expired. */
  read(): StoredToken | null {
    try {
      const raw = localStorage.getItem(KEY)
      if (!raw) return null
      const value = JSON.parse(raw) as StoredToken
      if (!value.token || value.expiresAt <= Date.now()) {
        localStorage.removeItem(KEY)
        return null
      }
      return value
    } catch {
      return null
    }
  },

  clear() {
    try {
      localStorage.removeItem(KEY)
    } catch {
      // Storage unavailable (private mode); nothing to clear.
    }
  },
}
