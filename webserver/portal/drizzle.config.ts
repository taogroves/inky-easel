import type { Config } from "drizzle-kit";

export default {
  schema: "./src/lib/db/schema.ts",
  out: "./drizzle",
  dialect: "mysql",
  dbCredentials: {
    url: process.env.DATABASE_URL ?? "mysql://inky:inky@localhost:3306/inky_easel",
  },
} satisfies Config;
