import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { roadmapRequestSchema, roadmapResponseSchema } from "../api-schemas";
import { proxyRoute } from "./proxy-route";

const VALID = { text: "Babamdan kalan arabayı almak", process_code: "miras_arac_devri" };

function makeRoute(requests = 100) {
  return proxyRoute({
    name: `test-${Math.random()}`,
    apiPath: "/v1/roadmap",
    requestSchema: roadmapRequestSchema,
    responseSchema: roadmapResponseSchema,
    limit: { requests, windowSeconds: 60 },
  });
}

function post(body: unknown, ip = "1.2.3.4") {
  return new Request("http://localhost/api/roadmap", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-forwarded-for": `${ip}, 10.0.0.1` },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function apiReturns(status: number, body: unknown) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => {
  vi.stubEnv("DATABASE_URL", "postgresql://u:p@localhost:5432/db");
  vi.stubEnv("API_BASE_URL", "http://api.internal:8000");
  vi.stubEnv("INTERNAL_API_TOKEN", "gizli-servis-anahtari");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("proxyRoute", () => {
  it("geçerli isteği servis anahtarıyla iletir ve yanıtı döndürür", async () => {
    const fetchMock = apiReturns(200, { status: "no_sources", masked_text: "x", message: "m" });
    const response = await makeRoute()(post(VALID));

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ status: "no_sources" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(String(url)).toBe("http://api.internal:8000/v1/roadmap");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer gizli-servis-anahtari",
    );
    expect(JSON.parse(String(init.body))).toEqual({ ...VALID, answers: {} });
  });

  it("geçersiz gövdeyi servise göndermeden reddeder", async () => {
    const fetchMock = apiReturns(200, {});
    for (const body of [
      "{bozuk",
      { text: "ab", process_code: "x" },
      { ...VALID, text: "x".repeat(2001) },
    ]) {
      const response = await makeRoute()(post(body));
      expect(response.status).toBe(400);
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("hız sınırını aşan istemciye 429 döner", async () => {
    apiReturns(200, { status: "no_sources", masked_text: "x" });
    const route = makeRoute(2);
    expect((await route(post(VALID))).status).toBe(200);
    expect((await route(post(VALID))).status).toBe(200);
    const limited = await route(post(VALID));
    expect(limited.status).toBe(429);
    expect(limited.headers.get("Retry-After")).toBeTruthy();
    expect((await route(post(VALID, "5.6.7.8"))).status).toBe(200); // başka istemci etkilenmez
  });

  it("servis hatalarını kullanıcı mesajıyla iletir; doğrulama ayrıntısı sızdırmaz", async () => {
    apiReturns(502, { detail: "Yanıt doğrulanamadı." });
    let response = await makeRoute()(post(VALID));
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ detail: "Yanıt doğrulanamadı." });

    apiReturns(422, { detail: [{ loc: ["body", "text"], msg: "iç ayrıntı" }] });
    response = await makeRoute()(post(VALID));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ detail: "Geçersiz istek." });
  });

  it("servisten beklenmeyen biçimde yanıt gelirse göstermez", async () => {
    apiReturns(200, { status: "ok", masked_text: "x", roadmap: { adimlar: [] } });
    const response = await makeRoute()(post(VALID));
    expect(response.status).toBe(502);
  });

  it("servis anahtarı tanımlı değilse 503 döner", async () => {
    vi.stubEnv("INTERNAL_API_TOKEN", "");
    const fetchMock = apiReturns(200, {});
    const response = await makeRoute()(post(VALID));
    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("servise ulaşılamazsa 503 döner", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new TypeError("ECONNREFUSED"))),
    );
    expect((await makeRoute()(post(VALID))).status).toBe(503);
  });
});
