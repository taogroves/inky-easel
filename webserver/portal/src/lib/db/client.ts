import mysql from "mysql2/promise";
import { drizzle } from "drizzle-orm/mysql2";

import * as schema from "./schema";

const url = process.env.DATABASE_URL;
if (!url) {
  throw new Error("DATABASE_URL is required (mysql://user:pass@host:3306/db)");
}

const pool = mysql.createPool({ uri: url, connectionLimit: 10 });

export const db = drizzle(pool, { schema, mode: "default" });
