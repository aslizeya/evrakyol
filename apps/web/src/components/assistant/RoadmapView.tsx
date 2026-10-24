"use client";

import { useId, useState } from "react";
import type { Roadmap } from "@/lib/api-schemas";
import { CONFIDENCE_LABELS, formatDate } from "./format";

type Props = {
  roadmap: Roadmap;
  processName: string;
  onRestart: () => void;
};

export function RoadmapView({ roadmap, processName, onRestart }: Props) {
  const [done, setDone] = useState<Set<number>>(new Set());
  const id = useId();
  const total = roadmap.adimlar.length;
  const confidence = CONFIDENCE_LABELS[roadmap.guven];

  function toggle(step: number) {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(step)) next.delete(step);
      else next.add(step);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby={`${id}-summary`} className="rounded-lg bg-surface p-4">
        <h3 id={`${id}-summary`} className="sr-only">
          Özet
        </h3>
        <p className="text-sm text-muted">{processName}</p>
        <p className="mt-1">{roadmap.ozet}</p>
        <p className="mt-3 text-sm">
          <strong>{confidence.label}:</strong> {confidence.help}
        </p>
      </section>

      <div className="no-print flex flex-col gap-2">
        <label htmlFor={`${id}-progress`} className="text-sm font-medium">
          {done.size} / {total} adım tamamlandı
        </label>
        <progress
          id={`${id}-progress`}
          value={done.size}
          max={total}
          className="h-3 w-full overflow-hidden rounded-full accent-accent"
        />
      </div>

      <ol className="flex flex-col gap-4">
        {roadmap.adimlar.map((step) => {
          const checkId = `${id}-step-${step.sira}`;
          const isDone = done.has(step.sira);
          return (
            <li
              key={step.sira}
              data-step
              className={`rounded-lg border p-4 ${isDone ? "border-success" : "border-border"}`}
            >
              <h3 className="text-lg font-semibold">
                <span className="mr-2 text-accent">{step.sira}.</span>
                {step.baslik}
              </h3>
              <p className="mt-2">{step.aciklama}</p>

              {step.gerekli_evraklar.length ? (
                <div className="mt-3">
                  <h4 className="font-medium">Gerekli evraklar</h4>
                  <ul className="mt-1 list-disc pl-6">
                    {step.gerekli_evraklar.map((doc) => (
                      <li key={doc}>{doc}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <dl className="mt-3 grid gap-1 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-3">
                <dt className="font-medium">Kurum</dt>
                <dd>{step.kurum}</dd>
                <dt className="font-medium">Tahmini ücret</dt>
                <dd>
                  {step.tahmini_ucret ?? "Kaynakta belirtilmemiş; ilgili kurumdan öğreniniz."}
                </dd>
              </dl>

              <div className="mt-3 text-sm">
                <h4 className="font-medium">Kaynak</h4>
                <ul className="mt-1 flex flex-col gap-1">
                  {step.kaynaklar.map((source) => (
                    <li key={source.url}>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-print-url
                        className="text-accent underline underline-offset-2"
                      >
                        {source.baslik}
                        <span className="sr-only"> (yeni sekmede açılır)</span>
                      </a>{" "}
                      <span className="text-muted">
                        · son kontrol {formatDate(source.son_kontrol)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <label
                htmlFor={checkId}
                className="no-print mt-4 flex min-h-11 w-fit cursor-pointer items-center gap-3"
              >
                <input
                  id={checkId}
                  type="checkbox"
                  checked={isDone}
                  onChange={() => toggle(step.sira)}
                  className="size-5 accent-accent"
                />
                Bu adımı tamamladım
              </label>
            </li>
          );
        })}
      </ol>

      {roadmap.uyarilar.length ? (
        <section
          aria-labelledby={`${id}-warnings`}
          className="rounded-lg bg-warning-bg p-4 text-warning-fg"
        >
          <h3 id={`${id}-warnings`} className="font-semibold">
            Dikkat edilmesi gerekenler
          </h3>
          <ul className="mt-2 list-disc pl-6">
            {roadmap.uyarilar.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="no-print flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => window.print()}
          className="min-h-11 rounded-lg bg-accent px-5 font-medium text-accent-foreground hover:bg-accent-hover"
        >
          Yazdır / PDF olarak kaydet
        </button>
        <button
          type="button"
          onClick={onRestart}
          className="min-h-11 rounded-lg border border-border px-5 hover:border-accent"
        >
          Yeni soru sor
        </button>
      </div>
    </div>
  );
}
