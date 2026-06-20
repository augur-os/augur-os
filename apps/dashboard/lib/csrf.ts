/**
 * CSRF Protection Utilities
 *
 * Provides CSRF token generation and validation for state-changing operations.
 * Uses double-submit cookie pattern for SPA compatibility.
 */

import { cookies } from "next/headers";
import { nanoid } from "nanoid";

const CSRF_COOKIE_NAME = "csrf_token";
const CSRF_HEADER_NAME = "x-csrf-token";

/**
 * Generate a new CSRF token
 */
export function generateCSRFToken(): string {
  return nanoid(32);
}

/**
 * Set CSRF token in cookie and return it
 * Call this in server components or API routes
 */
export async function setCSRFToken(): Promise<string> {
  const token = generateCSRFToken();
  const cookieStore = await cookies();

  cookieStore.set(CSRF_COOKIE_NAME, token, {
    httpOnly: false, // Must be readable by JavaScript for SPA
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24, // 24 hours
  });

  return token;
}

/**
 * Get CSRF token from cookie
 */
export async function getCSRFToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(CSRF_COOKIE_NAME)?.value;
}

/**
 * Get CSRF token from request (header or body)
 * Used in middleware to extract token from incoming requests
 */
export function getCSRFTokenFromRequest(request: Request): string | null {
  // Check header first
  const headerToken = request.headers.get(CSRF_HEADER_NAME);
  if (headerToken) {
    return headerToken;
  }

  // Check for token in query params (for GET requests that need CSRF)
  const url = new URL(request.url);
  const queryToken = url.searchParams.get("csrf_token");
  if (queryToken) {
    return queryToken;
  }

  return null;
}

/**
 * Validate CSRF token from request
 * Call this in API routes that modify state
 */
export async function validateCSRFToken(request: Request): Promise<boolean> {
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(CSRF_COOKIE_NAME)?.value;

  if (!cookieToken) {
    return false;
  }

  // Get token from header
  const headerToken = request.headers.get(CSRF_HEADER_NAME);

  if (!headerToken) {
    return false;
  }

  // Constant-time comparison to prevent timing attacks
  return timingSafeEqual(cookieToken, headerToken);
}

/**
 * Validate CSRF token directly (for middleware usage)
 * Compares provided token with stored token
 */
export function validateCSRFTokenDirect(
  providedToken: string | null,
  storedToken: string | undefined,
): boolean {
  if (!providedToken || !storedToken) {
    return false;
  }

  return timingSafeEqual(providedToken, storedToken);
}

/**
 * Constant-time string comparison
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }

  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }

  return result === 0;
}

/**
 * CSRF protection middleware for API routes
 * Usage: export const POST = withCSRFProtection(handler);
 */
export function withCSRFProtection(
  handler: (request: Request) => Promise<Response>,
): (request: Request) => Promise<Response> {
  return async (request: Request) => {
    // Only validate for state-changing methods
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
      const isValid = await validateCSRFToken(request);

      if (!isValid) {
        return new Response(JSON.stringify({ error: "Invalid CSRF token" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    return handler(request);
  };
}

export { CSRF_COOKIE_NAME, CSRF_HEADER_NAME };
