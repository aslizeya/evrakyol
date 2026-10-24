import type { z } from "zod";
import {
  guideResponseSchema,
  roadmapResponseSchema,
  understandResponseSchema,
  type GuideResponse,
  type RoadmapResponse,
  type UnderstandResponse,
} from "@/lib/api-schemas";

export type ClientResult<T> = { ok: true; data: T } | { ok: false; message: string };

const NETWORK_ERROR = "Bağlantı kurulamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.";

async function post<T>(url: string, body: unknown, schema: z.ZodType<T>): Promise<ClientResult<T>> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, message: NETWORK_ERROR };
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Bir sorun oluştu. Lütfen tekrar deneyin.";
    return { ok: false, message: detail };
  }
  const parsed = schema.safeParse(payload);
  return parsed.success
    ? { ok: true, data: parsed.data }
    : { ok: false, message: "Beklenmeyen bir yanıt alındı. Lütfen tekrar deneyin." };
}

export function requestUnderstanding(text: string): Promise<ClientResult<UnderstandResponse>> {
  return post("/api/understand", { text }, understandResponseSchema);
}

export function requestRoadmap(
  text: string,
  processCode: string,
  answers: Record<string, string>,
): Promise<ClientResult<RoadmapResponse>> {
  return post("/api/roadmap", { text, process_code: processCode, answers }, roadmapResponseSchema);
}

export function requestGuideStep(
  islem: string,
  cevaplar: Record<string, string>,
): Promise<ClientResult<GuideResponse>> {
  return post("/api/rehber", { islem, cevaplar }, guideResponseSchema);
}
