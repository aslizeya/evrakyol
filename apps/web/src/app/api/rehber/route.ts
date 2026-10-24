import { guideRequestSchema, guideResponseSchema } from "@/lib/api-schemas";
import { proxyRoute } from "@/lib/server/proxy-route";

export const POST = proxyRoute({
  name: "rehber",
  apiPath: "/v1/rehber",
  requestSchema: guideRequestSchema,
  responseSchema: guideResponseSchema,
  // Her soru bir istek olduğundan sınır daha geniştir; yapay zekâ çağrısı yapılmaz.
  limit: { requests: 120, windowSeconds: 600 },
  timeoutMs: 15_000,
});
