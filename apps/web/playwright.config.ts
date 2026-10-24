import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = 3100;
const API_PORT = 8799;
const CHANNEL = process.env.PW_CHANNEL ?? "chromium";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  // Her test kendi tarayıcısını açar; düşük çekirdekli makinelerde paralellik zaman aşımına yol açıyor.
  workers: process.env.CI ? 2 : 1,
  timeout: 60_000,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  expect: { timeout: 15_000 },
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    locale: "tr-TR",
    trace: "retain-on-failure",
  },
  // Varsayılan `chromium`: ayrı "headless shell" yerine tam Chromium (yeni headless kipi).
  // Yerelde yüklü bir tarayıcı da kullanılabilir: PW_CHANNEL=msedge npm run test:e2e
  projects: [
    { name: "masaustu", use: { ...devices["Desktop Chrome"], channel: CHANNEL } },
    { name: "mobil", use: { ...devices["Pixel 7"], channel: CHANNEL } },
  ],
  webServer: [
    {
      command: "node e2e/mock-api.mjs",
      port: API_PORT,
      env: { MOCK_API_PORT: String(API_PORT) },
      reuseExistingServer: false,
    },
    {
      // Üretim derlemesi: yayındaki davranışa yakın ve ilk istekte derleme beklemesi yok.
      command: `npx next build && npx next start --hostname 127.0.0.1 --port ${WEB_PORT}`,
      port: WEB_PORT,
      timeout: 300_000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: "postgresql://e2e:e2e@localhost:5432/e2e",
        API_BASE_URL: `http://127.0.0.1:${API_PORT}`,
        INTERNAL_API_TOKEN: "e2e-servis-anahtari",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
