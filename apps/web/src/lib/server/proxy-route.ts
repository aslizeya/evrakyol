import "server-only";
import type { z } from "zod";
import { callApi } from "../evrakyol-api";
import { clientKey, getRateLimiter } from "../rate-limit";

type ProxyOptions<Req, Res> = {
  name: string;
  apiPath: string;
  requestSchema: z.ZodType<Req>;
  responseSchema: z.ZodType<Res>;
  limit: { requests: number; windowSeconds: number };
  timeoutMs?: number;
};

/**
 * Tarayıcıdan gelen isteği doğrulayıp hız sınırı uygular ve yapay zekâ servisine iletir.
 * Kullanıcı metni hiçbir koşulda loglanmaz.
 */
export function proxyRoute<Req, Res>(options: ProxyOptions<Req, Res>) {
  return async function POST(request: Request): Promise<Response> {
    const { allowed, retryAfterSeconds } = await getRateLimiter().hit(
      `${options.name}:${clientKey(request)}`,
      options.limit.requests,
      options.limit.windowSeconds,
    );
    if (!allowed) {
      return Response.json(
        { detail: "Çok fazla istek gönderildi. Lütfen biraz bekleyip tekrar deneyin." },
        { status: 429, headers: { "Retry-After": String(retryAfterSeconds) } },
      );
    }

    const body = options.requestSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) {
      return Response.json({ detail: "Geçersiz istek." }, { status: 400 });
    }

    const result = await callApi(options.apiPath, body.data, options.responseSchema, {
      timeoutMs: options.timeoutMs,
    });
    return result.ok
      ? Response.json(result.data)
      : Response.json({ detail: result.detail }, { status: result.status });
  };
}
