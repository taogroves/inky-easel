import "server-only";

import { createHmac, timingSafeEqual } from "crypto";
import { cookies } from "next/headers";

const COOKIE_NAME = "inky_admin_sudo";

function adminPassword(): string | null {
  const password = process.env.ADMIN_DASHBOARD_PASSWORD?.trim();
  return password || null;
}

function cookieSecret(): string {
  return process.env.BETTER_AUTH_SECRET || process.env.ADMIN_DASHBOARD_PASSWORD || "dev-admin-secret";
}

function signPassword(password: string): string {
  return createHmac("sha256", cookieSecret()).update(password).digest("hex");
}

function safeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function isAdminPasswordConfigured(): boolean {
  return adminPassword() !== null;
}

export function verifyAdminPassword(password: string): boolean {
  const expected = adminPassword();
  if (!expected) return false;
  return safeEqual(password, expected);
}

export async function grantAdminDashboardAccess(): Promise<void> {
  const password = adminPassword();
  if (!password) return;
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, signPassword(password), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/dashboard/admin",
    maxAge: 60 * 60 * 8,
  });
}

export async function hasAdminDashboardAccess(): Promise<boolean> {
  const password = adminPassword();
  if (!password) return false;
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  if (!token) return false;
  return safeEqual(token, signPassword(password));
}

export async function requireAdminDashboardAccess(): Promise<void> {
  if (!(await hasAdminDashboardAccess())) {
    throw new Error("Admin dashboard password required");
  }
}
