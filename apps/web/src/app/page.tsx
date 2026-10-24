import { AssistantFlow } from "@/components/assistant/AssistantFlow";

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-10 px-4 py-10 sm:px-6 sm:py-16">
      <header className="no-print flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Evrakyol</h1>
        <p className="text-lg text-muted">
          Resmi işleminizi kendi cümlelerinizle anlatın; hangi evrakın gerektiğini, hangi kuruma
          gideceğinizi ve adımların sırasını resmi kaynaklarıyla birlikte gösterelim.
        </p>
      </header>
      <AssistantFlow />
    </div>
  );
}
