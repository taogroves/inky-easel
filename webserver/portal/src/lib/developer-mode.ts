import "server-only";

import { eq, sql } from "drizzle-orm";

import { db } from "@/lib/db/client";
import { userSettings } from "@/lib/db/schema";

export async function getDeveloperMode(userId: string): Promise<boolean> {
  try {
    const [settings] = await db
      .select({ developerMode: userSettings.developerMode })
      .from(userSettings)
      .where(eq(userSettings.userId, userId))
      .limit(1);
    return Boolean(settings?.developerMode);
  } catch {
    return false;
  }
}

export async function ensureUserSettingsTable(): Promise<void> {
  await db.execute(sql`
    CREATE TABLE IF NOT EXISTS ie_user_settings (
      user_id varchar(64) NOT NULL,
      developer_mode boolean NOT NULL DEFAULT false,
      updated_at datetime NOT NULL,
      PRIMARY KEY (user_id)
    )
  `);
}
