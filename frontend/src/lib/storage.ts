/**
 * localStorage wrappers that never throw.
 *
 * localStorage is missing during prerender/SSR and can throw in private mode,
 * when storage is full, or when a stored value is not valid JSON. Each helper
 * returns a fallback instead. Still call the getters from an effect (not during
 * render) so server and client markup match.
 */

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Parse a JSON value, or return `fallback` if missing, unreadable, or invalid JSON. */
export function safeGetJSON<T>(key: string, fallback: T): T {
  const storage = getStorage();
  if (!storage) return fallback;
  try {
    const raw = storage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

/** Store a value as JSON. Returns false if storage is unavailable or full. */
export function safeSetJSON(key: string, value: unknown): boolean {
  const storage = getStorage();
  if (!storage) return false;
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

/** Read a raw string (for values not stored as JSON), or null. */
export function safeGetString(key: string): string | null {
  const storage = getStorage();
  if (!storage) return null;
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

/** Store a raw string. Returns false if storage is unavailable or full. */
export function safeSetString(key: string, value: string): boolean {
  const storage = getStorage();
  if (!storage) return false;
  try {
    storage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

/** Remove one or more keys. Silently does nothing if storage is unavailable. */
export function safeRemove(...keys: string[]): void {
  const storage = getStorage();
  if (!storage) return;
  for (const key of keys) {
    try {
      storage.removeItem(key);
    } catch {
      // Removal failure leaves a stale value; nothing more useful to do.
    }
  }
}
