import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";

import { db } from "@/lib/db/client";
import * as schema from "@/lib/db/schema";

export const auth = betterAuth({
  appName: "Inky Easel",
  baseURL: process.env.BETTER_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  trustedOrigins: (process.env.BETTER_AUTH_TRUSTED_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  emailAndPassword: {
    enabled: true,
    autoSignIn: true,
    minPasswordLength: 8,
  },
  database: drizzleAdapter(db, {
    provider: "mysql",
    schema: {
      user: schema.user,
      session: schema.session,
      account: schema.account,
      verification: schema.verification,
    },
  }),
});

export type AuthSession = Awaited<ReturnType<typeof auth.api.getSession>>;
