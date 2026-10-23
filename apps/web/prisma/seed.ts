import { readFileSync } from "node:fs";
import path from "node:path";
import { PrismaPg } from "@prisma/adapter-pg";
import { config as loadEnv } from "dotenv";
import { PrismaClient } from "../src/generated/prisma/client";
import { processTypesFileSchema } from "../src/lib/process-types";

loadEnv({ path: path.resolve(import.meta.dirname, "../../../.env"), quiet: true });

const configPath = path.resolve(import.meta.dirname, "../../../config/process_types.json");

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) throw new Error("DATABASE_URL tanımlı değil");

  const { process_types } = processTypesFileSchema.parse(
    JSON.parse(readFileSync(configPath, "utf8")),
  );
  const prisma = new PrismaClient({ adapter: new PrismaPg({ connectionString }) });

  try {
    for (const pt of process_types) {
      await prisma.processType.upsert({
        where: { code: pt.code },
        update: { name: pt.name, description: pt.description, active: true },
        create: pt,
      });
    }
    console.log(`${process_types.length} işlem türü yüklendi.`);
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
