import { understandRequestSchema, understandResponseSchema } from "@/lib/api-schemas";
import { proxyRoute } from "@/lib/server/proxy-route";

export const POST = proxyRoute({
  name: "understand",
  apiPath: "/v1/understand",
  requestSchema: understandRequestSchema,
  responseSchema: understandResponseSchema,
  limit: { requests: 30, windowSeconds: 600 },
  timeoutMs: 60_000,
});
