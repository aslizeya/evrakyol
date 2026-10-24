import { AssistantFlow } from "@/components/assistant/AssistantFlow";
import { HowItWorks, Principles, ProcessGrid } from "@/components/home/HomeSections";
import { ShieldIcon } from "@/components/icons";

export default function Home() {
  return (
    <>
      <div className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="no-print pointer-events-none absolute inset-x-0 -top-40 h-[34rem] bg-[radial-gradient(ellipse_at_top,var(--hero-glow),transparent_65%)]"
        />
        <div className="relative mx-auto flex w-full max-w-3xl flex-col gap-10 px-4 pt-12 pb-16 sm:px-6 sm:pt-20">
          <header className="no-print flex flex-col items-center gap-5 text-center">
            <p className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-background/70 px-3 py-1 text-sm font-medium text-accent-soft-fg">
              <ShieldIcon className="size-4" />
              Resmi kaynaklara dayalı yol haritası
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
              Resmi işlemlerde <span className="text-accent">ne yapacağınızı</span> adım adım
              öğrenin
            </h1>
            <p className="max-w-2xl text-lg text-pretty text-muted">
              İşleminizi kendi cümlelerinizle anlatın; hangi evrakın gerektiğini, hangi kuruma
              gideceğinizi ve adımların sırasını resmi kaynaklarıyla birlikte gösterelim.
            </p>
          </header>
          <div className="rounded-3xl border border-border bg-background p-5 shadow-card sm:p-8">
            <AssistantFlow />
          </div>
        </div>
      </div>

      <div className="no-print border-t border-border bg-surface/60">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-20 px-4 py-16 sm:px-6 sm:py-20">
          <HowItWorks />
          <ProcessGrid />
          <Principles />
        </div>
      </div>
    </>
  );
}
