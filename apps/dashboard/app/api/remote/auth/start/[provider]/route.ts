import { NextResponse } from "next/server";
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  buildAuthorizationUrl,
  type OAuthSession,
} from "@/lib/remote/oauth";

const OAUTH_COOKIE_NAME = "oauth_session";
const OAUTH_COOKIE_MAX_AGE = 60 * 10; // 10 minutes
const OAUTH_DEFAULT_RETURN_URL = "/settings/providers";
const CANONICAL_PROVIDERS_PATHS = new Set([
  "/settings/providers",
  "/settings/providers/",
]);

function resolveOAuthReturnUrl(referer: string | null): string {
  if (!referer) {
    return OAUTH_DEFAULT_RETURN_URL;
  }

  if (CANONICAL_PROVIDERS_PATHS.has(referer)) {
    return OAUTH_DEFAULT_RETURN_URL;
  }

  try {
    const refererUrl = new URL(referer);
    if (CANONICAL_PROVIDERS_PATHS.has(refererUrl.pathname)) {
      return OAUTH_DEFAULT_RETURN_URL;
    }
  } catch {
    // Preserve non-URL referer values that are not known canonical paths.
  }

  return referer;
}

function isSameOriginPost(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) {
    return true;
  }

  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}

/**
 * POST /api/remote/auth/start/[provider]
 *
 * Initiates OAuth flow for a provider (Glama or OpenRouter).
 * Generates PKCE parameters, stores session, and returns the provider URL.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ provider: string }> },
) {
  try {
    if (!isSameOriginPost(request)) {
      return NextResponse.json(
        { error: "Invalid request origin" },
        { status: 403 },
      );
    }

    const { provider } = await params;

    // Validate provider supports OAuth
    if (provider !== "glama" && provider !== "openrouter") {
      return NextResponse.json(
        { error: `OAuth not supported for provider: ${provider}` },
        { status: 400 },
      );
    }

    // Generate PKCE parameters
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    const state = generateState();

    // Determine callback URL
    const url = new URL(request.url);
    const callbackUrl = `${url.origin}/api/remote/auth/callback/${provider}`;

    // Store session in cookie (encrypted in production)
    const session: OAuthSession = {
      providerId: provider,
      codeVerifier,
      state,
      createdAt: Date.now(),
      returnUrl: resolveOAuthReturnUrl(request.headers.get("referer")),
    };

    // Build authorization URL and attach the session cookie to this response.
    const authUrl = buildAuthorizationUrl(provider, {
      codeChallenge,
      state,
      callbackUrl,
    });

    const response = NextResponse.json({ url: authUrl });
    response.cookies.set(OAUTH_COOKIE_NAME, JSON.stringify(session), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: OAUTH_COOKIE_MAX_AGE,
      path: "/",
    });

    return response;
  } catch (error) {
    console.error("Error starting OAuth flow:", error);
    return NextResponse.json(
      { error: "Failed to start OAuth flow" },
      { status: 500 },
    );
  }
}

export function GET() {
  return NextResponse.json(
    { error: "Use POST to start OAuth" },
    { status: 405, headers: { Allow: "POST" } },
  );
}
