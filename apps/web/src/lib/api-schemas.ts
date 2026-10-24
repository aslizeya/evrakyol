import { z } from "zod";

// Yapay zekâ servisinin (services/api) yanıt biçimleri. Web, servisten gelen her yanıtı bu
// şemalarla doğrular; beklenmeyen bir yanıt kullanıcıya gösterilmez.

export const TEXT_LIMIT = 2000;

export const answersSchema = z
  .record(z.string().max(64), z.string().max(200))
  .refine((value) => Object.keys(value).length <= 10, "En fazla 10 cevap");

export const understandRequestSchema = z.object({
  text: z.string().trim().min(3).max(TEXT_LIMIT),
  process_code: z.string().max(64).optional(),
  answers: answersSchema.optional(),
});

export const roadmapRequestSchema = z.object({
  text: z.string().trim().min(3).max(TEXT_LIMIT),
  process_code: z.string().min(1).max(64),
  answers: answersSchema.default({}),
});

export const questionSchema = z.object({
  key: z.string(),
  question: z.string(),
  options: z.array(z.string()).min(2),
});

export const understandResponseSchema = z.object({
  status: z.enum(["out_of_scope", "needs_clarification", "ready"]),
  masked_text: z.string(),
  process_code: z.string().nullable().optional(),
  process_name: z.string().nullable().optional(),
  answers: z.record(z.string(), z.string()).default({}),
  questions: z.array(questionSchema).default([]),
  message: z.string().nullable().optional(),
});

export const sourceRefSchema = z.object({
  baslik: z.string(),
  url: z.url({ protocol: /^https$/ }),
  son_kontrol: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
});

export const stepSchema = z.object({
  sira: z.number().int().min(1),
  baslik: z.string(),
  aciklama: z.string(),
  gerekli_evraklar: z.array(z.string()),
  kurum: z.string(),
  tahmini_ucret: z.string().nullable(),
  kaynaklar: z.array(sourceRefSchema).min(1),
});

export const roadmapSchema = z.object({
  islem: z.string(),
  ozet: z.string(),
  adimlar: z.array(stepSchema).min(1),
  uyarilar: z.array(z.string()),
  guven: z.enum(["yuksek", "orta", "dusuk"]),
});

export const roadmapResponseSchema = z.object({
  status: z.enum(["ok", "no_sources"]),
  masked_text: z.string(),
  roadmap: roadmapSchema.nullable().optional(),
  message: z.string().nullable().optional(),
  referral: z.string().nullable().optional(),
});

export type Question = z.infer<typeof questionSchema>;
export type UnderstandResponse = z.infer<typeof understandResponseSchema>;
export type Roadmap = z.infer<typeof roadmapSchema>;
export type RoadmapStep = z.infer<typeof stepSchema>;
export type RoadmapResponse = z.infer<typeof roadmapResponseSchema>;

// --- Sorularla ilerleyen rehber (yapay zekâ gerektirmez) ---

export const guideRequestSchema = z.object({
  islem: z.string().min(1).max(64),
  cevaplar: answersSchema.default({}),
});

export const guideResponseSchema = z.object({
  durum: z.enum(["soru", "tamam", "kaynak_yok"]),
  cevaplar: z.record(z.string(), z.string()),
  soru: z
    .object({ anahtar: z.string(), metin: z.string(), secenekler: z.array(z.string()).min(2) })
    .nullable()
    .optional(),
  ilerleme: z
    .object({ cevaplanan: z.number().int(), toplam: z.number().int() })
    .nullable()
    .optional(),
  yol_haritasi: roadmapSchema.nullable().optional(),
  mesaj: z.string().nullable().optional(),
});

export type GuideResponse = z.infer<typeof guideResponseSchema>;
