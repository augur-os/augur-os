/**
 * User store reader for remote access authentication.
 * Reads user definitions from config/remote/users.yaml.
 */

import fs from "fs";
import path from "path";
import bcrypt from "bcryptjs";
import yaml from "js-yaml";
import { AUGUR_ROOT } from "@/lib/paths";

export interface UserRecord {
  id: string;
  name: string;
  role: "admin" | "user" | "readonly";
  password_hash: string;
  api_keys: Array<{
    name: string;
    key_hash: string;
    scopes: string[];
    created: string;
  }>;
}

interface RolesMap {
  [role: string]: string[];
}

interface UsersConfig {
  users: UserRecord[];
  roles: RolesMap;
}

let cachedConfig: UsersConfig | null = null;
let cachedMtime: number = 0;

function getUsersFilePath(): string {
  return path.join(AUGUR_ROOT, "config", "remote", "users.yaml");
}

function loadUsersConfig(): UsersConfig | null {
  const filePath = getUsersFilePath();
  try {
    const stat = fs.statSync(filePath);
    if (cachedConfig && stat.mtimeMs === cachedMtime) {
      return cachedConfig;
    }
    const content = fs.readFileSync(filePath, "utf-8");
    const parsed = yaml.load(content) as UsersConfig;
    if (!parsed?.users || !parsed?.roles) {
      return null;
    }
    cachedConfig = parsed;
    cachedMtime = stat.mtimeMs;
    return parsed;
  } catch {
    return null;
  }
}

export function findUser(userId: string): UserRecord | null {
  const config = loadUsersConfig();
  if (!config) return null;
  return config.users.find((u) => u.id === userId) || null;
}

export async function validatePassword(
  userId: string,
  password: string,
): Promise<boolean> {
  const user = findUser(userId);
  if (!user) return false;
  return bcrypt.compare(password, user.password_hash);
}

export function getUserScopes(role: string): string[] {
  const config = loadUsersConfig();
  if (!config) return [];
  return config.roles[role] || [];
}

function hasScope(userScopes: string[], requiredScope: string): boolean {
  return userScopes.some((scope) => {
    if (scope === requiredScope) return true;
    // Wildcard matching: "mcp:*" matches "mcp:read", "mcp:tools", etc.
    if (scope.endsWith(":*")) {
      const prefix = scope.slice(0, -1); // "mcp:"
      return requiredScope.startsWith(prefix);
    }
    return false;
  });
}

function isRemoteAccessConfigured(): boolean {
  const filePath = getUsersFilePath();
  return fs.existsSync(filePath);
}
