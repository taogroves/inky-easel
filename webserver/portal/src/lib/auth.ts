import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { eq, inArray } from "drizzle-orm";

import { db } from "@/lib/db/client";
import * as schema from "@/lib/db/schema";

async function deletePortalUserData(userId: string) {
  await db.transaction(async (tx) => {
    const frames = await tx.select({ id: schema.frame.id }).from(schema.frame).where(eq(schema.frame.userId, userId));
    const frameIds = frames.map((frame) => frame.id);

    if (frameIds.length > 0) {
      await tx.delete(schema.inboxItem).where(inArray(schema.inboxItem.recipientFrameId, frameIds));
      await tx.delete(schema.scheduleItem).where(inArray(schema.scheduleItem.frameId, frameIds));
      await tx.delete(schema.frameState).where(inArray(schema.frameState.frameId, frameIds));
      await tx.delete(schema.frame).where(eq(schema.frame.userId, userId));
    }

    await tx.delete(schema.inboxItem).where(eq(schema.inboxItem.senderUserId, userId));
    await tx.delete(schema.plugin).where(eq(schema.plugin.userId, userId));
    await tx.delete(schema.userSettings).where(eq(schema.userSettings.userId, userId)).catch(() => undefined);
  });
}

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
  user: {
    deleteUser: {
      enabled: true,
      beforeDelete: async (user) => {
        await deletePortalUserData(user.id);
      },
      afterDelete: async (user) => {
        await db.delete(schema.account).where(eq(schema.account.userId, user.id));
      },
    },
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
