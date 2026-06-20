/**
 * Next.js Proxy — Authentication & Remote Access Gate
 *
 * Handles:
 * - Local requests: pass through (preserves dev-mode, no auth required)
 * - Remote requests: require valid JWT in `augur-session` cookie
 * - Public paths: always pass through (/login, /api/auth/*, /_next/*, etc.)
 * - CLI PTY blocking: /api/cli is forbidden for remote users (RCE surface)
 * - Rate limiting: auth endpoints throttled to prevent brute-force
 *
 * JWT verification uses `jose` (Edge Runtime compatible).
 * Secret from AUGUR_JWT_SECRET env var. If not set, proxy checks cookie
 * presence only — API routes verify server-side with file-based secret.
 */

import { NextResponse, type NextRequest } from "next/server";
import { jwtVerify } from "jose";

const JWT_COOKIE_NAME = "augur-session";

/** Paths that never require authentication.
 * Note: /_next/static and /_next/image are excluded from the matcher entirely,
 * so only /_next/data (page data fetches) reaches this check. */
const PUBLIC_PATH_PREFIXES = [
  "/login",
  "/api/auth/",
  "/api/health",
  "/_next/",
  "/favicon.ico",
];

/** Paths blocked for remote users (security-critical) */
const REMOTE_BLOCKED_PREFIXES = [
  "/api/cli", // PTY shell — remote code execution surface
];

/**
 * Detect whether the request originates from localhost.
 * When behind Caddy, x-forwarded-for contains the real client IP.
 * Direct localhost access has no forwarded header.
 */
const LOCAL_IPS: ReadonlySet<string> = new Set([
  "127.0.0.1",
  "::1",
  "localhost",
  "::ffff:127.0.0.1",
]);

function isLocalRequest(request: NextRequest): boolean {
  const host = request.headers.get("host") || "";
  if (
    host.includes("localhost") ||
    host.startsWith("127.0.0.1") ||
    host.startsWith("[::1]")
  ) {
    // Direct localhost access — check x-forwarded-for to catch proxy scenarios
    const forwarded = request.headers.get("x-forwarded-for");
    if (forwarded) {
      const clientIp = forwarded.split(",")[0].trim();
      return LOCAL_IPS.has(clientIp);
    }
    return true; // No proxy, host is localhost
  }

  return false;
}

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function isRemoteBlocked(pathname: string): boolean {
  return REMOTE_BLOCKED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

// In-memory rate limit for auth endpoints (5 attempts per minute per IP).
// Expired entries are pruned opportunistically on each call to bound memory
// under burst traffic from many distinct IPs.
const authAttempts = new Map<string, { count: number; resetTime: number }>();
let lastAuthAttemptsPrune = 0;
const AUTH_ATTEMPTS_PRUNE_INTERVAL_MS = 60_000;

function pruneAuthAttempts(now: number): void {
  if (now - lastAuthAttemptsPrune < AUTH_ATTEMPTS_PRUNE_INTERVAL_MS) return;
  lastAuthAttemptsPrune = now;
  for (const [ip, entry] of authAttempts) {
    if (now > entry.resetTime) authAttempts.delete(ip);
  }
}

function checkAuthRateLimit(ip: string): boolean {
  const now = Date.now();
  pruneAuthAttempts(now);
  const entry = authAttempts.get(ip);

  if (!entry || now > entry.resetTime) {
    authAttempts.set(ip, { count: 1, resetTime: now + 60_000 });
    return true;
  }

  if (entry.count >= 5) {
    return false;
  }

  entry.count++;
  return true;
}

/**
 * Verify JWT token using jose (Edge Runtime compatible).
 * Returns payload if valid, null otherwise.
 */
async function verifyJWT(
  token: string,
): Promise<{ userId: string; role: string; scopes: string[] } | null> {
  const secret = process.env.AUGUR_JWT_SECRET;
  if (!secret) return null;

  try {
    const { payload } = await jwtVerify(
      token,
      new TextEncoder().encode(secret),
      { issuer: "augur" },
    );
    return payload as unknown as {
      userId: string;
      role: string;
      scopes: string[];
    };
  } catch {
    return null;
  }
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // ── Local requests: pass through (preserves current dev-mode behavior) ──
  if (isLocalRequest(request)) {
    return NextResponse.next();
  }

  // ── Remote request detected ──

  // Public paths: always accessible
  if (isPublicPath(pathname)) {
    // Rate-limit login attempts
    if (pathname === "/api/auth/login" && request.method === "POST") {
      const ip =
        request.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
        "unknown";
      if (!checkAuthRateLimit(ip)) {
        return NextResponse.json(
          {
            error: "Too many login attempts. Try again in 1 minute.",
            code: "RATE_LIMITED",
          },
          { status: 429, headers: { "Retry-After": "60" } },
        );
      }
    }
    return NextResponse.next();
  }

  // Blocked paths: forbidden for remote users regardless of auth
  if (isRemoteBlocked(pathname)) {
    return NextResponse.json(
      {
        error: "This endpoint is not available for remote access",
        code: "REMOTE_BLOCKED",
      },
      { status: 403 },
    );
  }

  // ── Require authentication for all other remote requests ──

  const token = request.cookies.get(JWT_COOKIE_NAME)?.value;

  if (!token) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { error: "Authentication required", code: "AUTH_REQUIRED" },
        { status: 401 },
      );
    }
    // Page requests → redirect to login
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Verify JWT if AUGUR_JWT_SECRET is available (set by start script or Caddy env)
  const hasSecret = !!process.env.AUGUR_JWT_SECRET;

  if (hasSecret) {
    const payload = await verifyJWT(token);

    if (!payload) {
      if (pathname.startsWith("/api/")) {
        return NextResponse.json(
          { error: "Invalid or expired token", code: "INVALID_TOKEN" },
          { status: 401 },
        );
      }
      return NextResponse.redirect(new URL("/login", request.url));
    }

    // Add verified user context to headers for downstream handlers
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("x-user-id", payload.userId);
    requestHeaders.set("x-user-role", payload.role);
    requestHeaders.set("x-user-scopes", payload.scopes.join(","));
    requestHeaders.set("x-remote-user", "true");

    return NextResponse.next({ request: { headers: requestHeaders } });
  }

  // No AUGUR_JWT_SECRET configured — accept cookie presence as gate.
  // API routes still verify JWT server-side with file-based secret.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-remote-user", "true");
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
