import { z } from "zod";

// Sunucu tarafı ortam değişkenleri. Eksik veya hatalı değer uygulamayı açılışta durdurur.
export const serverEnvSchema = z.object({
  DATABASE_URL: z.url({ protocol: /^postgres(ql)?$/ }),
  API_BASE_URL: z.url().default("http://localhost:8000"),
  INTERNAL_API_TOKEN: z.string().optional(),
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
});

export type ServerEnv = z.infer<typeof serverEnvSchema>;

export function parseServerEnv(source: Record<string, string | undefined>): ServerEnv {
  const result = serverEnvSchema.safeParse(source);
  if (!result.success) {
    const fields = result.error.issues.map((i) => i.path.join(".")).join(", ");
    throw new Error(`Geçersiz veya eksik ortam değişkenleri: ${fields}`);
  }
  return result.data;
}
