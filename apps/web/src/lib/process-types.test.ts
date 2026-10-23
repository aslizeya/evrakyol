import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { processTypesFileSchema } from "./process-types";

const configPath = path.resolve(import.meta.dirname, "../../../../config/process_types.json");

describe("config/process_types.json", () => {
  const { process_types } = processTypesFileSchema.parse(
    JSON.parse(readFileSync(configPath, "utf8")),
  );

  it("MVP kapsamındaki 8 işlemi içerir", () => {
    expect(process_types).toHaveLength(8);
  });

  it("işlem kodları benzersizdir", () => {
    const codes = process_types.map((p) => p.code);
    expect(new Set(codes).size).toBe(codes.length);
  });
});
