import "server-only";
import postgres from "postgres";
let connection: ReturnType<typeof postgres> | undefined;
export function db() { if (!connection) { if (!process.env.DATABASE_URL) throw new Error("Database is not configured"); connection = postgres(process.env.DATABASE_URL, { max: 3, prepare: false, idle_timeout: 20, connect_timeout: 10 }); } return connection; }
