import "server-only";
import type { z } from "zod";
import { parseServerEnv } from "./env";

// Yapay zekâ servisine sunucu tarafından yapılan çağrılar. Servis anahtarı tarayıcıya hiç ulaşmaz.

export type ApiResult<T> =
  { ok: true; status: number; data: T } | { ok: false; status: number; detail: string };

const GENERIC_ERROR = "Şu anda yanıt verilemiyor. Lütfen biraz sonra tekrar deneyin.";

export async function callApi<T>(
  path: string,
  body: unknown,
  schema: z.ZodType<T>,
  { timeoutMs = 150_000 }: { timeoutMs?: number } = {},
): Promise<ApiResult<T>> {
  const env = parseServerEnv(process.env);
  if (!env.INTERNAL_API_TOKEN) {
    return { ok: false, status: 503, detail: "Servis yapılandırılmamış." };
  }

  let response: Response;
  try {
    response = await fetch(new URL(path, env.API_BASE_URL), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.INTERNAL_API_TOKEN}`,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
  } catch {
    return { ok: false, status: 503, detail: GENERIC_ERROR };
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : GENERIC_ERROR;
    // Doğrulama hataları (422) kullanıcıya 400 olarak döner; ayrıntılı alan listesi gösterilmez.
    if (response.status === 422) return { ok: false, status: 400, detail: "Geçersiz istek." };
    return { ok: false, status: response.status >= 500 ? response.status : 400, detail };
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    return { ok: false, status: 502, detail: "Servisten beklenmeyen bir yanıt alındı." };
  }
  return { ok: true, status: 200, data: parsed.data };
}
