/**
 * OAuth PKCE Utilities
 *
 * Implements Proof Key for Code Exchange (PKCE) for secure OAuth flows.
 * Used by Glama and OpenRouter for one-click authentication.
 */

/**
 * Generate a cryptographically random code verifier
 * Must be between 43-128 characters, using unreserved URI characters
 */
export function generateCodeVerifier(length: number = 64): string {
  const charset =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  const randomValues = new Uint8Array(length);
  crypto.getRandomValues(randomValues);

  let result = "";
  for (let i = 0; i < length; i++) {
    result += charset[randomValues[i] % charset.length];
  }
  return result;
}

/**
 * Generate a code challenge from the verifier using S256 method
 * SHA-256 hash, then base64url encode
 */
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);

  // Base64url encode (no padding, URL-safe characters)
  const base64 = btoa(String.fromCharCode(...new Uint8Array(digest)));
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Generate a random state parameter for CSRF protection
 */
export function generateState(): string {
  const randomValues = new Uint8Array(32);
  crypto.getRandomValues(randomValues);
  return Array.from(randomValues, (b) => b.toString(16).padStart(2, "0")).join(
    "",
  );
}

/**
 * OAuth session data stored during the flow
 */
export interface OAuthSession {
  providerId: string;
  codeVerifier: string;
  state: string;
  createdAt: number;
  returnUrl?: string;
}

/**
 * Build the authorization URL for a provider
 */
export function buildAuthorizationUrl(
  provider: "glama" | "openrouter",
  params: {
    codeChallenge: string;
    state: string;
    callbackUrl: string;
  },
): string {
  if (provider === "glama") {
    const url = new URL("https://glama.ai/oauth/authorize");
    url.searchParams.set("callback_url", params.callbackUrl);
    url.searchParams.set("code_challenge", params.codeChallenge);
    url.searchParams.set("code_challenge_method", "S256");
    url.searchParams.set("state", params.state);
    return url.toString();
  }

  if (provider === "openrouter") {
    const url = new URL("https://openrouter.ai/auth");
    url.searchParams.set("callback_url", params.callbackUrl);
    url.searchParams.set("code_challenge", params.codeChallenge);
    url.searchParams.set("code_challenge_method", "S256");
    url.searchParams.set("state", params.state);
    return url.toString();
  }

  throw new Error(`OAuth not supported for provider: ${provider}`);
}

/**
 * Exchange authorization code for API key (Glama)
 */
export async function exchangeCodeGlama(
  code: string,
  codeVerifier: string,
): Promise<{ apiKey: string } | { error: string }> {
  try {
    const response = await fetch(
      "https://glama.ai/api/gateway/v1/auth/exchange-code",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          code,
          code_verifier: codeVerifier,
          code_challenge_method: "S256",
        }),
      },
    );

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return { error: data.error?.message || `HTTP ${response.status}` };
    }

    const data = await response.json();
    if (!data.apiKey) {
      return { error: "No API key in response" };
    }

    return { apiKey: data.apiKey };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "Exchange failed",
    };
  }
}

/**
 * Exchange authorization code for API key (OpenRouter)
 */
export async function exchangeCodeOpenRouter(
  code: string,
  codeVerifier: string,
): Promise<{ apiKey: string } | { error: string }> {
  try {
    const response = await fetch("https://openrouter.ai/api/v1/auth/keys", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        code,
        code_verifier: codeVerifier,
        code_challenge_method: "S256",
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return { error: data.error?.message || `HTTP ${response.status}` };
    }

    const data = await response.json();
    if (!data.key) {
      return { error: "No API key in response" };
    }

    return { apiKey: data.key };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "Exchange failed",
    };
  }
}
