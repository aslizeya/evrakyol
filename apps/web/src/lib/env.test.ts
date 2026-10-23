import { describe, expect, it } from "vitest";
import { parseServerEnv } from "./env";

describe("parseServerEnv", () => {
  it("geçerli değerleri kabul eder ve varsayılanları uygular", () => {
    const env = parseServerEnv({ DATABASE_URL: "postgresql://u:p@localhost:5432/db" });
    expect(env.API_BASE_URL).toBe("http://localhost:8000");
    expect(env.NODE_ENV).toBe("development");
  });

  it("eksik DATABASE_URL için alan adını belirten hata verir", () => {
    expect(() => parseServerEnv({})).toThrow(/DATABASE_URL/);
  });

  it("Postgres dışı bağlantı adreslerini reddeder", () => {
    expect(() => parseServerEnv({ DATABASE_URL: "mysql://u:p@localhost/db" })).toThrow(
      /DATABASE_URL/,
    );
  });

  it("hata mesajında değerin kendisini (gizli bilgi) göstermez", () => {
    let message = "";
    try {
      parseServerEnv({ DATABASE_URL: "gizli-sifre-123" });
    } catch (err) {
      message = (err as Error).message;
    }
    expect(message).toContain("DATABASE_URL");
    expect(message).not.toContain("gizli-sifre-123");
  });
});
