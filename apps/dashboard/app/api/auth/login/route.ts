import { NextResponse, type NextRequest } from "next/server";
import { validatePassword, findUser, getUserScopes } from "@/lib/auth/users";
import { issueToken, buildSetCookieHeader } from "@/lib/auth/jwt";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { username, password } = body;

    if (!username || !password) {
      return NextResponse.json(
        { error: "Username and password required" },
        { status: 400 },
      );
    }

    const valid = await validatePassword(username, password);
    if (!valid) {
      return NextResponse.json(
        { error: "Invalid credentials" },
        { status: 401 },
      );
    }

    const user = findUser(username);
    if (!user) {
      return NextResponse.json(
        { error: "Invalid credentials" },
        { status: 401 },
      );
    }

    const scopes = getUserScopes(user.role);
    const token = await issueToken({
      userId: user.id,
      role: user.role,
      scopes,
    });

    // Set Secure flag when request arrived over HTTPS (via Caddy TLS proxy)
    const isSecure = request.headers.get("x-forwarded-proto") === "https";
    const response = NextResponse.json({
      ok: true,
      user: { id: user.id, name: user.name, role: user.role },
    });
    response.headers.set("Set-Cookie", buildSetCookieHeader(token, isSecure));
    return response;
  } catch {
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
