import "server-only";
import Redis from "ioredis";

// Sabit pencereli hız sınırı. REDIS_URL tanımlıysa Redis (birden çok sunucu örneğinde ortak),
// değilse süreç içi bellek (yerel geliştirme) kullanılır.

export type RateLimitResult = { allowed: boolean; retryAfterSeconds: number };

export interface RateLimiter {
  hit(key: string, limit: number, windowSeconds: number): Promise<RateLimitResult>;
}

export class MemoryRateLimiter implements RateLimiter {
  private windows = new Map<string, { count: number; resetAt: number }>();

  constructor(private now: () => number = Date.now) {}

  async hit(key: string, limit: number, windowSeconds: number): Promise<RateLimitResult> {
    const now = this.now();
    let window = this.windows.get(key);
    if (!window || window.resetAt <= now) {
      window = { count: 0, resetAt: now + windowSeconds * 1000 };
      this.windows.set(key, window);
    }
    window.count += 1;
    const retryAfterSeconds = Math.ceil((window.resetAt - now) / 1000);
    return { allowed: window.count <= limit, retryAfterSeconds };
  }
}

export class RedisRateLimiter implements RateLimiter {
  constructor(private redis: Redis) {}

  async hit(key: string, limit: number, windowSeconds: number): Promise<RateLimitResult> {
    const redisKey = `ratelimit:${key}`;
    const [[, count], [, ttl]] = (await this.redis.multi().incr(redisKey).ttl(redisKey).exec()) as [
      [null, number],
      [null, number],
    ];
    if (ttl < 0) await this.redis.expire(redisKey, windowSeconds);
    return { allowed: count <= limit, retryAfterSeconds: ttl > 0 ? ttl : windowSeconds };
  }
}

let limiter: RateLimiter | undefined;

export function getRateLimiter(): RateLimiter {
  if (!limiter) {
    const url = process.env.REDIS_URL;
    limiter = url
      ? new RedisRateLimiter(new Redis(url, { maxRetriesPerRequest: 1, lazyConnect: false }))
      : new MemoryRateLimiter();
  }
  return limiter;
}

/** İstemci IP'si: yayında (Vercel) güvenilir proxy'nin eklediği ilk x-forwarded-for değeri. */
export function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  return forwarded?.split(",")[0]?.trim() || request.headers.get("x-real-ip") || "yerel";
}
