"use client";

import { useId, useState, type FormEvent } from "react";
import type { Question } from "@/lib/api-schemas";

type Props = {
  processName: string;
  questions: Question[];
  onSubmit: (answers: Record<string, string>) => void;
  onBack: () => void;
};

export function ClarifyForm({ processName, questions, onSubmit, onBack }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [showErrors, setShowErrors] = useState(false);
  const id = useId();
  const missing = questions.filter((q) => !answers[q.key]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (missing.length) {
      setShowErrors(true);
      document.getElementById(`${id}-${missing[0].key}-0`)?.focus();
      return;
    }
    onSubmit(answers);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
      <p>
        İşleminiz: <strong>{processName}</strong>. Size doğru adımları gösterebilmemiz için{" "}
        {questions.length === 1 ? "bir soruyu" : `${questions.length} soruyu`} yanıtlayın.
      </p>
      {questions.map((question) => {
        const invalid = showErrors && !answers[question.key];
        const errorId = `${id}-${question.key}-error`;
        return (
          <fieldset
            key={question.key}
            className="rounded-lg border border-border p-4"
            aria-describedby={invalid ? errorId : undefined}
          >
            <legend className="px-1 font-medium">{question.question}</legend>
            <div className="mt-2 flex flex-col gap-2">
              {question.options.map((option, index) => {
                const optionId = `${id}-${question.key}-${index}`;
                return (
                  <label
                    key={option}
                    htmlFor={optionId}
                    className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-surface"
                  >
                    <input
                      id={optionId}
                      type="radio"
                      name={`${id}-${question.key}`}
                      value={option}
                      checked={answers[question.key] === option}
                      onChange={() => setAnswers((prev) => ({ ...prev, [question.key]: option }))}
                      className="size-5 accent-accent"
                    />
                    {option}
                  </label>
                );
              })}
            </div>
            {invalid ? (
              <p id={errorId} className="mt-2 text-sm text-danger-fg">
                Lütfen bir seçenek belirleyin.
              </p>
            ) : null}
          </fieldset>
        );
      })}
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          className="min-h-11 rounded-lg bg-accent px-5 font-medium text-accent-foreground hover:bg-accent-hover"
        >
          Devam et
        </button>
        <button
          type="button"
          onClick={onBack}
          className="min-h-11 rounded-lg border border-border px-5 hover:border-accent"
        >
          Soruyu değiştir
        </button>
      </div>
    </form>
  );
}
