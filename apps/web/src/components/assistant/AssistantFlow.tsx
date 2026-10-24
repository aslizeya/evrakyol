"use client";

import { useEffect, useRef, useState } from "react";
import type { Question, Roadmap } from "@/lib/api-schemas";
import { requestRoadmap, requestUnderstanding } from "./api-client";
import { AskForm } from "./AskForm";
import { ClarifyForm } from "./ClarifyForm";
import { RoadmapView } from "./RoadmapView";

type Stage =
  | { kind: "ask"; error?: string }
  | { kind: "understanding" }
  | {
      kind: "clarify";
      processCode: string;
      processName: string;
      answers: Record<string, string>;
      questions: Question[];
    }
  | { kind: "building"; processName: string }
  | { kind: "roadmap"; roadmap: Roadmap; processName: string }
  | { kind: "out_of_scope"; message: string }
  | { kind: "no_sources"; message: string }
  | { kind: "error"; message: string; retry: () => void };

const HEADINGS: Record<Stage["kind"], string> = {
  ask: "Sorunuzu yazın",
  understanding: "İsteğiniz anlaşılıyor",
  clarify: "Birkaç kısa soru",
  building: "Yol haritanız hazırlanıyor",
  roadmap: "Yol haritanız",
  out_of_scope: "Bu işlem henüz desteklenmiyor",
  no_sources: "Resmi kaynaklarda yeterli bilgi bulunamadı",
  error: "Bir sorun oluştu",
};

export function AssistantFlow() {
  const [stage, setStage] = useState<Stage>({ kind: "ask" });
  const [text, setText] = useState("");
  const [masked, setMasked] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const previousKind = useRef<Stage["kind"]>("ask");

  // Aşama değiştiğinde odak yeni bölümün başlığına taşınır (ekran okuyucu ve klavye kullanıcıları için).
  // İlk açılışta odak taşınmaz; karşılaştırma, efektin geliştirme modunda iki kez çalışmasına da dayanıklıdır.
  useEffect(() => {
    if (previousKind.current === stage.kind) return;
    previousKind.current = stage.kind;
    headingRef.current?.focus();
  }, [stage.kind]);

  async function buildRoadmap(
    question: string,
    processCode: string,
    processName: string,
    answers: Record<string, string>,
  ) {
    setStage({ kind: "building", processName });
    const result = await requestRoadmap(question, processCode, answers);
    if (!result.ok) {
      setStage({
        kind: "error",
        message: result.message,
        retry: () => buildRoadmap(question, processCode, processName, answers),
      });
      return;
    }
    const { data } = result;
    if (data.status === "ok" && data.roadmap) {
      setStage({ kind: "roadmap", roadmap: data.roadmap, processName });
    } else {
      setStage({
        kind: "no_sources",
        message: data.message ?? "Bu işlem için resmi kaynaklarda yeterli bilgi bulunamadı.",
      });
    }
  }

  async function start(question: string) {
    setText(question);
    setStage({ kind: "understanding" });
    const result = await requestUnderstanding(question);
    if (!result.ok) {
      setStage({ kind: "ask", error: result.message });
      return;
    }
    const data = result.data;
    setMasked(data.masked_text !== question);
    if (data.status === "out_of_scope" || !data.process_code) {
      setStage({ kind: "out_of_scope", message: data.message ?? "Bu işlem şu an desteklenmiyor." });
      return;
    }
    const processName = data.process_name ?? "";
    if (data.status === "needs_clarification") {
      setStage({
        kind: "clarify",
        processCode: data.process_code,
        processName,
        answers: data.answers,
        questions: data.questions,
      });
      return;
    }
    await buildRoadmap(question, data.process_code, processName, data.answers);
  }

  function restart() {
    setMasked(false);
    setStage({ kind: "ask" });
  }

  const busy = stage.kind === "understanding" || stage.kind === "building";

  return (
    <section aria-labelledby="asistan-baslik" aria-busy={busy} className="flex flex-col gap-5">
      <h2
        id="asistan-baslik"
        ref={headingRef}
        tabIndex={-1}
        className="text-2xl font-semibold tracking-tight focus:outline-none"
      >
        {HEADINGS[stage.kind]}
      </h2>

      <p role="status" aria-live="polite" className="sr-only">
        {busy ? HEADINGS[stage.kind] : ""}
      </p>

      {masked && stage.kind !== "ask" ? (
        <p className="rounded-lg bg-surface p-3 text-sm">
          Güvenliğiniz için metninizdeki kişisel bilgiler (ör. T.C. kimlik numarası, plaka, adres)
          işlenmeden önce gizlendi.
        </p>
      ) : null}

      {stage.kind === "ask" ? (
        <AskForm initialText={text} error={stage.error} onSubmit={start} />
      ) : null}

      {stage.kind === "understanding" ? <Loading text="İsteğiniz anlaşılıyor…" /> : null}

      {stage.kind === "building" ? (
        <Loading text="Resmi kaynaklar taranıyor ve yol haritanız hazırlanıyor. Bu işlem 1-2 dakika sürebilir." />
      ) : null}

      {stage.kind === "clarify" ? (
        <ClarifyForm
          processName={stage.processName}
          questions={stage.questions}
          onBack={restart}
          onSubmit={(chosen) =>
            buildRoadmap(text, stage.processCode, stage.processName, {
              ...stage.answers,
              ...chosen,
            })
          }
        />
      ) : null}

      {stage.kind === "roadmap" ? (
        <RoadmapView roadmap={stage.roadmap} processName={stage.processName} onRestart={restart} />
      ) : null}

      {stage.kind === "out_of_scope" || stage.kind === "no_sources" ? (
        <div className="flex flex-col gap-4">
          <p className="rounded-lg bg-warning-bg p-4 text-warning-fg">{stage.message}</p>
          <RestartButton onClick={restart} />
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
              onClick={stage.retry}
              className="min-h-11 rounded-lg bg-accent px-5 font-medium text-accent-foreground hover:bg-accent-hover"
            >
              Tekrar dene
            </button>
            <RestartButton onClick={restart} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Loading({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 text-muted">
      <span
        aria-hidden="true"
        className="size-5 animate-spin rounded-full border-2 border-border border-t-accent"
      />
      <p>{text}</p>
    </div>
  );
}

function RestartButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-11 w-fit rounded-lg border border-border px-5 hover:border-accent"
    >
      Yeni soru sor
    </button>
  );
}
