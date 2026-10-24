import { z } from "zod";

// Sunucu tarafı ortam değişkenleri, kullanıldıkları yere göre ayrı doğrulanır: yapay zekâ
// servisine istek iletmek veritabanı gerektirmez, veritabanı erişimi servis anahtarı gerektirmez.

export const apiEnvSchema = z.object({
  API_BASE_URL: z.url().default("http://127.0.0.1:8000"),
  INTERNAL_API_TOKEN: z.string().optional(),
});

export const dbEnvSchema = z.object({
  DATABASE_URL: z.url({ protocol: /^postgres(ql)?$/ }),
});

export type ApiEnv = z.infer<typeof apiEnvSchema>;
export type DbEnv = z.infer<typeof dbEnvSchema>;

function parse<T>(schema: z.ZodType<T>, source: Record<string, string | undefined>): T {
  const result = schema.safeParse(source);
  if (!result.success) {
    // Değerlerin kendisi (gizli bilgi olabilir) hata mesajına yazılmaz; yalnızca alan adları.
    const fields = result.error.issues.map((i) => i.path.join(".")).join(", ");
    throw new Error(`Geçersiz veya eksik ortam değişkenleri: ${fields}`);
  }
  return result.data;
}

export function parseApiEnv(source: Record<string, string | undefined>): ApiEnv {
  return parse(apiEnvSchema, source);
}

export function parseDbEnv(source: Record<string, string | undefined>): DbEnv {
  return parse(dbEnvSchema, source);
}
