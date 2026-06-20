import { cookies, headers } from "next/headers";

import { JWT_COOKIE_NAME, verifyToken } from "@/lib/auth/jwt";

export type ServerActionSession = {
  isRemote: boolean;
  role: string;
  scopes: string[];
  userId: string;
};

export async function auth(): Promise<ServerActionSession> {
  const requestHeaders = await headers();
  const isRemote = requestHeaders.get("x-remote-user") === "true";

  if (!isRemote) {
    return {
      isRemote: false,
      role: "admin",
      scopes: ["*"],
      userId: "dev-user",
    };
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(JWT_COOKIE_NAME)?.value;
  if (!token) {
    throw new Error("Authentication required");
  }

  const payload = await verifyToken(token);
  if (!payload) {
    throw new Error("Invalid or expired token");
  }

  return {
    isRemote: true,
    role: payload.role,
    scopes: payload.scopes,
    userId: payload.userId,
  };
}
