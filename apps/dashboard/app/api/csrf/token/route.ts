import { NextResponse } from "next/server";
import { setCSRFToken } from "@/lib/csrf";

/**
 * GET /api/csrf/token
 *
 * Returns a new CSRF token and sets it in a cookie.
 * Call this endpoint when the app loads or when token is missing.
 */
export async function GET() {
  const token = await setCSRFToken();

  return NextResponse.json({ token });
}
