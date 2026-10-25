import "server-only";
import postgres from "postgres";

declare global {
  var __litmusSql: postgres.Sql | undefined;
}

export function hasDatabase(): boolean {
  return Boolean(process.env.DATABASE_URL);
}

/** One pooled client per server instance (reused across hot reloads in dev). */
export function sql(): postgres.Sql {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not configured");
  }
  if (!globalThis.__litmusSql) {
    globalThis.__litmusSql = postgres(process.env.DATABASE_URL, {
      max: 5,
      idle_timeout: 20,
      connect_timeout: 10,
      prepare: false,
      ssl: "require",
    });
  }
  return globalThis.__litmusSql;
}
