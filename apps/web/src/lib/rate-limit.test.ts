import { describe, expect, it } from "vitest";
import { clientKey, FallbackRateLimiter, MemoryRateLimiter, type RateLimiter } from "./rate-limit";

describe("MemoryRateLimiter", () => {
  it("pencere içinde sınırı uygular, pencere bitince sıfırlar", async () => {
    let now = 0;
    const limiter = new MemoryRateLimiter(() => now);
    expect((await limiter.hit("k", 2, 60)).allowed).toBe(true);
    expect((await limiter.hit("k", 2, 60)).allowed).toBe(true);
    const third = await limiter.hit("k", 2, 60);
    expect(third).toEqual({ allowed: false, retryAfterSeconds: 60 });
    now = 61_000;
    expect((await limiter.hit("k", 2, 60)).allowed).toBe(true);
  });

  it("anahtarlar birbirinden bağımsızdır", async () => {
    const limiter = new MemoryRateLimiter(() => 0);
    await limiter.hit("a", 1, 60);
    expect((await limiter.hit("a", 1, 60)).allowed).toBe(false);
    expect((await limiter.hit("b", 1, 60)).allowed).toBe(true);
  });
});

describe("clientKey", () => {
  it("x-forwarded-for zincirindeki ilk adresi kullanır", () => {
    const request = new Request("http://x", { headers: { "x-forwarded-for": "1.1.1.1, 2.2.2.2" } });
    expect(clientKey(request)).toBe("1.1.1.1");
    expect(clientKey(new Request("http://x"))).toBe("yerel");
  });
});

describe("FallbackRateLimiter", () => {
  it("birincil sınırlayıcı hata verirse yedekle sınırlamaya devam eder", async () => {
    const broken: RateLimiter = { hit: async () => Promise.reject(new Error("ECONNREFUSED")) };
    const limiter = new FallbackRateLimiter(broken, new MemoryRateLimiter(() => 0));
    expect((await limiter.hit("k", 1, 60)).allowed).toBe(true);
    expect((await limiter.hit("k", 1, 60)).allowed).toBe(false);
  });
});
