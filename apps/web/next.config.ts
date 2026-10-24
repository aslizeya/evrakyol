import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Tek bir `.env` dosyası kök klasörde tutulur (web, API ve Docker Compose ortak kullanır).
const repoRoot = path.resolve(import.meta.dirname, "../..");
loadEnvConfig(repoRoot);

const nextConfig: NextConfig = {
  // Docker imajı için yalnızca gerekli dosyaları içeren bağımsız çıktı (Dockerfile açar).
  // Vercel ve `next start` (uçtan uca testler) için gerekmez.
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,
  outputFileTracingRoot: repoRoot,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    root: repoRoot,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
