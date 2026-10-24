import { roadmapRequestSchema, roadmapResponseSchema } from "@/lib/api-schemas";
import { proxyRoute } from "@/lib/server/proxy-route";

export const POST = proxyRoute({
  name: "roadmap",
  apiPath: "/v1/roadmap",
  requestSchema: roadmapRequestSchema,
  responseSchema: roadmapResponseSchema,
  // Yol haritası üretimi pahalıdır; kullanıcı başına daha sıkı sınır.
  limit: { requests: 10, windowSeconds: 600 },
  timeoutMs: 150_000,
});

// Yol haritası üretimi uzun sürebilir (kaynak arama + LLM); barındırma ortamının süre sınırı.
export const maxDuration = 160;
