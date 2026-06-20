/**
 * Help System - Support Token
 *
 * Manages an anonymous support token for identifying this Augur installation.
 * The token is a random UUID stored in localStorage — no PII, no email,
 * no account required. Users can reset it at any time.
 */

const STORAGE_KEY = "augur_support_token";

/**
 * Get or create the support token for this installation.
 * Returns a random UUID that identifies help requests without PII.
 */
export function getSupportToken(): string {
  if (typeof window === "undefined") return "";

  let token = localStorage.getItem(STORAGE_KEY);
  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, token);
  }
  return token;
}

/**
 * Clear the support token (privacy reset).
 * After clearing, a new token will be generated on next request.
 */
function clearSupportToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Check if a support token exists (user has used the help system before).
 */
function hasSupportToken(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEY) !== null;
}
