// Kök klasördeki `.env` dosyasını yükleyip Next.js'i başlatır.
// Next.js yalnızca kendi klasöründeki .env dosyalarını okur; tek bir ortak `.env` kullandığımız için
// değişkenler burada yüklenir ve Next.js'in tüm alt süreçlerine (istek işleyenler dahil) aktarılır.
// Ortamda zaten tanımlı değişkenlerin üzerine yazılmaz.
import { spawn } from "node:child_process";
import path from "node:path";
import { config } from "dotenv";

const webDir = path.resolve(import.meta.dirname, "..");
config({ path: path.resolve(webDir, "../../.env"), quiet: true });

const nextBin = path.resolve(webDir, "node_modules/next/dist/bin/next");
const child = spawn(process.execPath, [nextBin, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
  cwd: webDir,
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
