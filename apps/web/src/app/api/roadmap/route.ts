import { roadmapRequestSchema, roadmapResponseSchema } from "@/lib/api-schemas";
import { proxyRoute } from "@/lib/server/proxy-route";

export const POST = proxyRoute({
  name: "roadmap",
  apiPath: "/v1/roadmap",
  requestSchema: roadmapRequestSchema,
  responseSchema: roadmapResponseSchema,
  // Yol haritası üretimi pahalıdır; kullanıcı başına daha sıkı sınır.
  limit: { requests: 10, windowSeconds: 600 },
  // Model yanıt vermeden önce düşünür; tek denemede 1-2 dakika sürebilir.
  timeoutMs: 240_000,
});

// Yol haritası üretimi uzun sürebilir (kaynak arama + LLM); barındırma ortamının süre sınırı.
export const maxDuration = 250;
