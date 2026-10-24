import type { Metadata } from "next";
import { AssistantFlow } from "@/components/assistant/AssistantFlow";

export const metadata: Metadata = {
  title: "Serbest metinle sor (deneysel)",
  // Yapay zekâ bağlantısı henüz yayında değil; arama motorlarına gösterilmez.
  robots: { index: false },
};

// Serbest metni yapay zekâyla anlayan akış. Yapay zekâ servisi yapılandırıldığında kullanılır;
// ana sayfadaki sorularla ilerleyen rehber yapay zekâ gerektirmez.
export default function AssistantPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6">
      <header className="no-print flex flex-col gap-3">
        <p className="w-fit rounded-full bg-warning-bg px-3 py-1 text-sm font-medium text-warning-fg">
          Deneysel
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Serbest metinle sorun</h1>
        <p className="text-lg text-muted">
          İşleminizi kendi cümlelerinizle anlatın; yapay zekâ isteğinizi anlayıp resmi kaynaklara
          dayanan bir yol haritası hazırlar.
        </p>
      </header>
      <div className="rounded-3xl border border-border bg-background p-5 shadow-card sm:p-8">
        <AssistantFlow />
      </div>
    </div>
  );
}
