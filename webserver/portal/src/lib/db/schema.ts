/**
 * Drizzle schema for the Inky Easel portal.
 *
 * The `user`, `session`, `account`, `verification` tables match the schema
 * better-auth expects. Everything prefixed `ie_*` is owned by the portal.
 * The FastAPI service reads these same tables via SQLAlchemy.
 */

import {
  boolean,
  customType,
  datetime,
  double,
  index,
  int,
  json,
  mediumtext,
  mysqlTable,
  text,
  uniqueIndex,
  varchar,
} from "drizzle-orm/mysql-core";

/** LONGBLOB — removed from drizzle-orm/mysql-core exports; keep SQL type for MariaDB */
const longblob = customType<{
  data: Buffer | null;
  driverData: Buffer | null;
}>({
  dataType() {
    return "longblob";
  },
  toDriver(value) {
    return value;
  },
  fromDriver(value) {
    if (value == null) return null;
    if (Buffer.isBuffer(value)) return value;
    return Buffer.from(value as Uint8Array);
  },
});

// ---------- better-auth tables ----------

export const user = mysqlTable("user", {
  id: varchar("id", { length: 64 }).primaryKey(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  emailVerified: boolean("emailVerified").default(false),
  name: varchar("name", { length: 255 }),
  image: text("image"),
  createdAt: datetime("createdAt").notNull(),
  updatedAt: datetime("updatedAt").notNull(),
});

export const session = mysqlTable("session", {
  id: varchar("id", { length: 64 }).primaryKey(),
  expiresAt: datetime("expiresAt").notNull(),
  token: varchar("token", { length: 255 }).notNull().unique(),
  createdAt: datetime("createdAt").notNull(),
  updatedAt: datetime("updatedAt").notNull(),
  ipAddress: varchar("ipAddress", { length: 64 }),
  userAgent: text("userAgent"),
  userId: varchar("userId", { length: 64 }).notNull(),
});

export const account = mysqlTable("account", {
  id: varchar("id", { length: 64 }).primaryKey(),
  accountId: varchar("accountId", { length: 255 }).notNull(),
  providerId: varchar("providerId", { length: 64 }).notNull(),
  userId: varchar("userId", { length: 64 }).notNull(),
  accessToken: text("accessToken"),
  refreshToken: text("refreshToken"),
  idToken: text("idToken"),
  accessTokenExpiresAt: datetime("accessTokenExpiresAt"),
  refreshTokenExpiresAt: datetime("refreshTokenExpiresAt"),
  scope: text("scope"),
  password: text("password"),
  createdAt: datetime("createdAt").notNull(),
  updatedAt: datetime("updatedAt").notNull(),
});

export const verification = mysqlTable("verification", {
  id: varchar("id", { length: 64 }).primaryKey(),
  identifier: varchar("identifier", { length: 255 }).notNull(),
  value: text("value").notNull(),
  expiresAt: datetime("expiresAt").notNull(),
  createdAt: datetime("createdAt"),
  updatedAt: datetime("updatedAt"),
});

// ---------- Portal-owned tables (mirrored by FastAPI / SQLAlchemy) ----------

export const userSettings = mysqlTable("ie_user_settings", {
  userId: varchar("user_id", { length: 64 }).primaryKey(),
  developerMode: boolean("developer_mode").default(false).notNull(),
  updatedAt: datetime("updated_at").notNull(),
});

export const frame = mysqlTable(
  "ie_frame",
  {
    id: varchar("id", { length: 36 }).primaryKey(),
    userId: varchar("user_id", { length: 64 }).notNull(),
    name: varchar("name", { length: 64 }).notNull(),
    displayName: varchar("display_name", { length: 120 }).notNull(),
    secret: varchar("secret", { length: 128 }).notNull(),
    latitude: double("latitude"),
    longitude: double("longitude"),
    timezone: varchar("timezone", { length: 64 }),
    displayType: varchar("display_type", { length: 40 }).default("inky_frame_7_spectra").notNull(),
    scheduleMode: varchar("schedule_mode", { length: 16 }).default("relative").notNull(),
    inboxMode: varchar("inbox_mode", { length: 16 }).default("open").notNull(),
    inboxPassword: varchar("inbox_password", { length: 120 }),
    inboxRepeatEnabled: boolean("inbox_repeat_enabled").default(false).notNull(),
    inboxDeleteAfterDisplays: int("inbox_delete_after_displays"),
    lastSeenAt: datetime("last_seen_at"),
    nextExpectedPollAt: datetime("next_expected_poll_at"),
    disconnectedAfter: datetime("disconnected_after"),
    lastBatteryPercent: int("last_battery_percent"),
    lastBatteryVoltage: double("last_battery_voltage"),
    lastHasSdCard: boolean("last_has_sd_card"),
    firmwareVersion: varchar("firmware_version", { length: 64 }),
    targetFirmwareVersion: varchar("target_firmware_version", { length: 64 }),
    lastFirmwareStatus: varchar("last_firmware_status", { length: 32 }),
    lastFirmwareUpdateAt: datetime("last_firmware_update_at"),
    createdAt: datetime("created_at").notNull(),
    updatedAt: datetime("updated_at").notNull(),
  },
  (t) => ({
    uniqName: uniqueIndex("uq_ie_frame_name").on(t.name),
    byUser: index("ix_ie_frame_user").on(t.userId),
  }),
);

export const frameState = mysqlTable("ie_frame_state", {
  frameId: varchar("frame_id", { length: 36 }).primaryKey(),
  currentIndex: int("current_index").default(0).notNull(),
  lastAdvanceAt: datetime("last_advance_at"),
  scheduleHash: varchar("schedule_hash", { length: 64 }),
});

export const scheduleItem = mysqlTable(
  "ie_schedule_item",
  {
    id: varchar("id", { length: 36 }).primaryKey(),
    frameId: varchar("frame_id", { length: 36 }).notNull(),
    position: int("position").notNull(),
    itemType: varchar("item_type", { length: 32 }).notNull(),
    itemRef: varchar("item_ref", { length: 255 }),
    config: json("config"),
    sleepMinutes: int("sleep_minutes").default(60).notNull(),
    startMinute: int("start_minute"),
  },
  (t) => ({
    uniqPos: uniqueIndex("uq_schedule_position").on(t.frameId, t.position),
  }),
);

export const plugin = mysqlTable("ie_plugin", {
  id: varchar("id", { length: 36 }).primaryKey(),
  userId: varchar("user_id", { length: 64 }).notNull(),
  name: varchar("name", { length: 120 }).notNull(),
  description: text("description"),
  code: mediumtext("code").notNull(),
  createdAt: datetime("created_at").notNull(),
  updatedAt: datetime("updated_at").notNull(),
});

export const inboxItem = mysqlTable(
  "ie_inbox_item",
  {
    id: varchar("id", { length: 36 }).primaryKey(),
    recipientFrameId: varchar("recipient_frame_id", { length: 36 }).notNull(),
    senderUserId: varchar("sender_user_id", { length: 64 }),
    senderLabel: varchar("sender_label", { length: 120 }),
    kind: varchar("kind", { length: 16 }).notNull(),
    textBody: text("text_body"),
    imageMime: varchar("image_mime", { length: 64 }),
    imageBytes: longblob("image_bytes"),
    createdAt: datetime("created_at").notNull(),
    displayedAt: datetime("displayed_at"),
    displayCount: int("display_count").default(0).notNull(),
    archived: boolean("archived").default(false).notNull(),
  },
  (t) => ({ byRecipient: index("ix_inbox_recipient").on(t.recipientFrameId) }),
);

export const contentCache = mysqlTable("ie_content_cache", {
  token: varchar("token", { length: 64 }).primaryKey(),
  mime: varchar("mime", { length: 64 }).default("image/jpeg").notNull(),
  payload: longblob("payload").notNull(),
  expiresAt: datetime("expires_at").notNull(),
  createdAt: datetime("created_at").notNull(),
});
