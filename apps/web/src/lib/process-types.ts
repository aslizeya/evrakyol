import { z } from "zod";

export const processTypeSchema = z.object({
  code: z.string().regex(/^[a-z_]+$/),
  name: z.string().min(1),
  description: z.string().min(1),
});

export const processTypesFileSchema = z.object({
  process_types: z.array(processTypeSchema).min(1),
});

export type ProcessTypeConfig = z.infer<typeof processTypeSchema>;
