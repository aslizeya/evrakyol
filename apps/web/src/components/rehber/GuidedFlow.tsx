"use client";

import { useEffect, useRef, useState } from "react";
import { requestGuideStep } from "@/components/assistant/api-client";
import { RoadmapView } from "@/components/assistant/RoadmapView";
import type { Roadmap } from "@/lib/api-schemas";
import { findGuide, GUIDES } from "@/lib/guides";

type Answer = { key: string; value: string; question: string };
type Guide = (typeof GUIDES)[number];

type Stage =
  | { kind: "choose" }
  | { kind: "loading"; guide: Guide; history: Answer[] }
  | {
      kind: "question";
      guide: Guide;
      history: Answer[];
      question: { anahtar: string; metin: string; secenekler: string[] };
      progress: { cevaplanan: number; toplam: number };
    }
  | { kind: "roadmap"; guide: Guide; history: Answer[]; roadmap: Roadmap }
  | { kind: "no_sources"; guide: Guide; history: Answer[]; message: string }
  | { kind: "error"; guide: Guide; history: Answer[]; message: string };

type Props = { initialProcess?: string };

/**
 * Yapay zekâ olmadan, seçenekli sorularla ilerleyen rehber. Her ekranda tek soru sorulur;
 * kullanıcıdan serbest metin veya kişisel bilgi alınmaz.
 */
export function GuidedFlow({ initialProcess }: Props) {
  const [stage, setStage] = useState<Stage>(() => {
    const guide = findGuide(initialProcess);
    return guide ? { kind: "loading", guide, history: [] } : { kind: "choose" };
  });
  const headingRef = useRef<HTMLHeadingElement>(null);
  const previousKey = useRef("choose");
  const started = useRef(false);

  const stageKey = stage.kind === "question" ? `question:${stage.question.anahtar}` : stage.kind;

  // Ekran değiştiğinde odak yeni başlığa taşınır (ekran okuyucu ve klavye kullanıcıları için).
  useEffect(() => {
    if (stage.kind === "loading" || previousKey.current === stageKey) return;
    previousKey.current = stageKey;
    headingRef.current?.focus();
  }, [stage.kind, stageKey]);

  function load(guide: Guide, history: Answer[]) {
    setStage({ kind: "loading", guide, history });
    void fetchStep(guide, history);
  }

  async function fetchStep(guide: Guide, history: Answer[]) {
    const answers = Object.fromEntries(history.map((a) => [a.key, a.value]));
    const result = await requestGuideStep(guide.code, answers);
    if (!result.ok) {
      setStage({ kind: "error", guide, history, message: result.message });
      return;
    }
    const data = result.data;
    // Sunucunun geçerli saydığı cevaplarla eşitlenir (ör. geri dönülüp cevap değiştirildiğinde).
    const kept = history.filter((a) => data.cevaplar[a.key] === a.value);
    if (data.durum === "soru" && data.soru && data.ilerleme) {
      setStage({
        kind: "question",
        guide,
        history: kept,
        question: data.soru,
        progress: data.ilerleme,
      });
    } else if (data.durum === "tamam" && data.yol_haritasi) {
      setStage({ kind: "roadmap", guide, history: kept, roadmap: data.yol_haritasi });
    } else {
      setStage({
        kind: "no_sources",
        guide,
        history: kept,
        message: data.mesaj ?? "Bu durum için doğrulanmış bilgi bulunamadı.",
      });
    }
  }

  // Bağlantıyla belirli bir işlem açıldıysa (ör. /?islem=...) ilk soru hemen getirilir.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const guide = findGuide(initialProcess);
    if (guide) void fetchStep(guide, []);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- yalnızca ilk açılışta
  }, []);

  function restart() {
    setStage({ kind: "choose" });
  }

  const busy = stage.kind === "loading";
  const heading =
    stage.kind === "choose"
      ? "Hangi işlem için yol haritası istiyorsunuz?"
      : stage.kind === "question"
        ? stage.question.metin
        : stage.kind === "roadmap"
          ? "Yol haritanız"
          : stage.kind === "no_sources"
            ? "Doğrulanmış bilgi bulunamadı"
            : stage.kind === "error"
              ? "Bir sorun oluştu"
              : "Hazırlanıyor";

  return (
    <section aria-labelledby="rehber-baslik" aria-busy={busy} className="flex flex-col gap-5">
      {stage.kind === "question" ? (
        <QuestionProgress guideName={stage.guide.name} {...stage.progress} />
      ) : null}

      <h2
        id="rehber-baslik"
        ref={headingRef}
        tabIndex={-1}
        className="text-2xl font-semibold tracking-tight focus:outline-none"
      >
        {heading}
      </h2>
      <p role="status" aria-live="polite" className="sr-only">
        {busy ? "Hazırlanıyor" : ""}
      </p>

      {stage.kind === "choose" ? (
        <>
          <p className="text-muted">
            Birkaç kısa soruyu seçeneklerden işaretleyerek yanıtlayın. Kişisel bilgi sorulmaz.
          </p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {GUIDES.map((guide) => (
              <li key={guide.code}>
                <button
                  type="button"
                  onClick={() => load(guide, [])}
                  className="flex h-full min-h-11 w-full flex-col gap-1 rounded-2xl border border-border bg-background p-5 text-left hover:border-accent"
                >
                  <span className="font-semibold">{guide.name}</span>
                  <span className="text-sm text-muted">{guide.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {stage.kind === "loading" ? (
        <div className="flex items-center gap-3 text-muted">
          <span
            aria-hidden="true"
            className="size-5 animate-spin rounded-full border-2 border-border border-t-accent"
          />
          <p>Hazırlanıyor…</p>
        </div>
      ) : null}

      {stage.kind === "question" ? (
        <>
          <ul className="flex flex-col gap-2" aria-label="Seçenekler">
            {stage.question.secenekler.map((option) => (
              <li key={option}>
                <button
                  type="button"
                  onClick={() =>
                    load(stage.guide, [
                      ...stage.history,
                      {
                        key: stage.question.anahtar,
                        value: option,
                        question: stage.question.metin,
                      },
                    ])
                  }
                  className="flex min-h-12 w-full items-center justify-between gap-3 rounded-xl border border-border bg-background px-4 py-3 text-left font-medium hover:border-accent hover:bg-surface"
                >
                  {option}
                  <span aria-hidden="true" className="text-muted">
                    →
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-3">
            {stage.history.length > 0 ? (
              <SecondaryButton onClick={() => load(stage.guide, stage.history.slice(0, -1))}>
                Önceki soru
              </SecondaryButton>
            ) : null}
            <SecondaryButton onClick={restart}>İşlemi değiştir</SecondaryButton>
          </div>
        </>
      ) : null}

      {stage.kind === "roadmap" ? (
        <>
          {stage.history.length > 0 ? <AnswerSummary history={stage.history} /> : null}
          <RoadmapView roadmap={stage.roadmap} processName={stage.guide.name} onRestart={restart} />
        </>
      ) : null}

      {stage.kind === "no_sources" ? (
        <div className="flex flex-col gap-4">
          <p className="rounded-lg bg-warning-bg p-4 text-warning-fg">{stage.message}</p>
          <SecondaryButton onClick={restart}>Baştan başla</SecondaryButton>
        </div>
      ) : null}

      {stage.kind === "error" ? (
        <div className="flex flex-col gap-4">
          <p role="alert" className="rounded-lg bg-danger-bg p-4 text-danger-fg">
            {stage.message}
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => load(stage.guide, stage.history)}
              className="min-h-11 rounded-lg bg-accent px-5 font-medium text-accent-foreground hover:bg-accent-hover"
            >
              Tekrar dene
            </button>
            <SecondaryButton onClick={restart}>Baştan başla</SecondaryButton>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function QuestionProgress({
  guideName,
  cevaplanan,
  toplam,
}: {
  guideName: string;
  cevaplanan: number;
  toplam: number;
}) {
  const current = cevaplanan + 1;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted">
        {guideName} · Soru {current} / {toplam}
      </p>
      <div aria-hidden="true" className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${(cevaplanan / Math.max(toplam, 1)) * 100}%` }}
        />
      </div>
    </div>
  );
}

function AnswerSummary({ history }: { history: Answer[] }) {
  return (
    <details className="no-print rounded-lg border border-border p-4 text-sm">
      <summary className="cursor-pointer font-medium">Verdiğiniz cevaplar</summary>
      <ul className="mt-2 flex flex-col gap-1 text-muted">
        {history.map((answer) => (
          <li key={answer.key}>
            {answer.question} <strong className="text-foreground">{answer.value}</strong>
          </li>
        ))}
      </ul>
    </details>
  );
}

function SecondaryButton({ onClick, children }: { onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-11 w-fit rounded-lg border border-border px-5 hover:border-accent"
    >
      {children}
    </button>
  );
}
