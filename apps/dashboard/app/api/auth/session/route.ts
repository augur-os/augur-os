import { NextResponse, type NextRequest } from "next/server";
import { verifyToken, getTokenFromCookies } from "@/lib/auth/jwt";
import { findUser, getUserScopes } from "@/lib/auth/users";

function isRemoteRequest(request: NextRequest): boolean {
  const forwarded = request.headers.get("x-forwarded-for");
  const host = request.headers.get("host") || "";
  const localIPs = ["127.0.0.1", "::1", "localhost"];

  if (
    host.includes("localhost") ||
    host.startsWith("127.0.0.1") ||
    host.startsWith("[::1]")
  )
    return false;
  if (forwarded) {
    const firstIp = forwarded.split(",")[0].trim();
    if (localIPs.includes(firstIp)) return false;
    return true;
  }
  return false;
}

export async function GET(request: NextRequest) {
  const isRemote = isRemoteRequest(request);
  const cookieHeader = request.headers.get("cookie");
  const token = getTokenFromCookies(cookieHeader);

  if (!token) {
    // Localhost without token = dev mode
    if (!isRemote) {
      return NextResponse.json({
        authenticated: true,
        isRemote: false,
        user: { id: "dev-user", name: "Developer", role: "admin" },
        scopes: getUserScopes("admin"),
      });
    }
    return NextResponse.json(
      { authenticated: false, isRemote: true },
      { status: 401 },
    );
  }

  const payload = await verifyToken(token);
  if (!payload) {
    return NextResponse.json(
      { authenticated: false, isRemote, error: "Invalid or expired token" },
      { status: 401 },
    );
  }

  const user = findUser(payload.userId);
  if (!user) {
    return NextResponse.json(
      { authenticated: false, isRemote, error: "User not found" },
      { status: 401 },
    );
  }

  return NextResponse.json({
    authenticated: true,
    isRemote,
    user: { id: user.id, name: user.name, role: user.role },
    scopes: payload.scopes,
  });
}
