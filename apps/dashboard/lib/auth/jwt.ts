/**
 * JWT issue/verify for remote access authentication.
 * Signs with secret from config/remote/.jwt-secret (auto-generated if missing).
 */

import { SignJWT, jwtVerify, type JWTPayload } from "jose";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import { AUGUR_ROOT } from "@/lib/paths";

export interface AugurJWTPayload extends JWTPayload {
  userId: string;
  role: string;
  scopes: string[];
}

const JWT_COOKIE_NAME = "augur-session";
const JWT_EXPIRY = "24h";

function getSecretPath(): string {
  return path.join(AUGUR_ROOT, "config", "remote", ".jwt-secret");
}

let cachedSecret: Uint8Array | null = null;

function getOrCreateSecret(): Uint8Array {
  if (cachedSecret) return cachedSecret;

  const secretPath = getSecretPath();
  try {
    const raw = fs.readFileSync(secretPath, "utf-8").trim();
    cachedSecret = new TextEncoder().encode(raw);
    return cachedSecret;
  } catch {
    // Auto-generate a 256-bit random secret
    const secret = crypto.randomBytes(32).toString("hex");
    const dir = path.dirname(secretPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(secretPath, secret, { mode: 0o600 });
    cachedSecret = new TextEncoder().encode(secret);
    return cachedSecret;
  }
}

export async function issueToken(payload: {
  userId: string;
  role: string;
  scopes: string[];
}): Promise<string> {
  const secret = getOrCreateSecret();
  return new SignJWT({
    userId: payload.userId,
    role: payload.role,
    scopes: payload.scopes,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(JWT_EXPIRY)
    .setIssuer("augur")
    .sign(secret);
}

export async function verifyToken(
  token: string,
): Promise<AugurJWTPayload | null> {
  try {
    const secret = getOrCreateSecret();
    const { payload } = await jwtVerify(token, secret, { issuer: "augur" });
    return payload as AugurJWTPayload;
  } catch {
    return null;
  }
}

export function getTokenFromCookies(
  cookieHeader: string | null,
): string | null {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(new RegExp(`${JWT_COOKIE_NAME}=([^;]+)`));
  return match ? match[1] : null;
}

export function buildSetCookieHeader(
  token: string,
  secure: boolean = false,
): string {
  const maxAge = 24 * 60 * 60; // 24 hours in seconds
  const securePart = secure ? " Secure;" : "";
  return `${JWT_COOKIE_NAME}=${token}; Path=/; HttpOnly; SameSite=Lax;${securePart} Max-Age=${maxAge}`;
}

export function buildClearCookieHeader(secure: boolean = false): string {
  const securePart = secure ? " Secure;" : "";
  return `${JWT_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax;${securePart} Max-Age=0`;
}

export { JWT_COOKIE_NAME };
