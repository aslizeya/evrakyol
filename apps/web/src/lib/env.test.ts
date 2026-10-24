import { describe, expect, it } from "vitest";
import { parseApiEnv, parseDbEnv } from "./env";

describe("parseApiEnv", () => {
  it("varsayılan servis adresini uygular ve veritabanı istemez", () => {
    expect(parseApiEnv({}).API_BASE_URL).toBe("http://127.0.0.1:8000");
  });

  it("geçersiz servis adresini reddeder", () => {
    expect(() => parseApiEnv({ API_BASE_URL: "adres değil" })).toThrow(/API_BASE_URL/);
  });
});

describe("parseDbEnv", () => {
  it("geçerli Postgres adresini kabul eder", () => {
    const env = parseDbEnv({ DATABASE_URL: "postgresql://u:p@localhost:5432/db" });
    expect(env.DATABASE_URL).toContain("localhost");
  });

  it("eksik DATABASE_URL için alan adını belirten hata verir", () => {
    expect(() => parseDbEnv({})).toThrow(/DATABASE_URL/);
  });

  it("Postgres dışı bağlantı adreslerini reddeder", () => {
    expect(() => parseDbEnv({ DATABASE_URL: "mysql://u:p@localhost/db" })).toThrow(/DATABASE_URL/);
  });

  it("hata mesajında değerin kendisini (gizli bilgi) göstermez", () => {
    let message = "";
    try {
      parseDbEnv({ DATABASE_URL: "gizli-sifre-123" });
    } catch (err) {
      message = (err as Error).message;
    }
    expect(message).toContain("DATABASE_URL");
    expect(message).not.toContain("gizli-sifre-123");
  });
});
