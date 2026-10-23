import "server-only";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@/generated/prisma/client";
import { parseServerEnv } from "./env";

// Geliştirme ortamında hot reload her seferinde yeni bağlantı havuzu açmasın diye istemci global'de tutulur.
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

function createClient() {
  const { DATABASE_URL } = parseServerEnv(process.env);
  return new PrismaClient({ adapter: new PrismaPg({ connectionString: DATABASE_URL }) });
}

export const db = globalForPrisma.prisma ?? createClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = db;
