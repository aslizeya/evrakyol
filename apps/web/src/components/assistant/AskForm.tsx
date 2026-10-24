"use client";

import { useId, useState, type FormEvent } from "react";
import { TEXT_LIMIT } from "@/lib/api-schemas";

export const EXAMPLE_QUESTIONS = [
  "Babamdan kalan arabayı üzerime almak istiyorum.",
  "Veraset ilamını nereden ve nasıl alabilirim?",
  "Annemin vefatından sonra aracını satmak istiyoruz, ne yapmalıyız?",
  "Rahmetli babamın vasiyetnamesi var, mirasçılık belgesini noterden alabilir miyim?",
];

type Props = {
  initialText?: string;
  error?: string;
  onSubmit: (text: string) => void;
};

export function AskForm({ initialText = "", error, onSubmit }: Props) {
  const [text, setText] = useState(initialText);
  const id = useId();
  const hintId = `${id}-hint`;
  const countId = `${id}-count`;
  const errorId = `${id}-error`;
  const trimmed = text.trim();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (trimmed.length >= 3) onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
      <label htmlFor={id} className="text-lg font-medium">
        Hangi resmi işlemi yapmak istiyorsunuz?
      </label>
      <p id={hintId} className="text-sm text-muted">
        Durumunuzu kendi cümlelerinizle anlatın. T.C. kimlik numarası, plaka veya adres gibi kişisel
        bilgileri yazmanıza gerek yok.
      </p>
      <textarea
        id={id}
        value={text}
        onChange={(event) => setText(event.target.value.slice(0, TEXT_LIMIT))}
        rows={4}
        maxLength={TEXT_LIMIT}
        required
        aria-describedby={`${hintId} ${countId}${error ? ` ${errorId}` : ""}`}
        aria-invalid={error ? true : undefined}
        placeholder="Ör. Babamdan kalan arabayı üzerime almak istiyorum."
        className="w-full rounded-lg border border-border bg-background p-3 text-base"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span id={countId} className="text-sm text-muted">
          {text.length} / {TEXT_LIMIT} karakter
        </span>
        <button
          type="submit"
          disabled={trimmed.length < 3}
          className="min-h-11 rounded-lg bg-accent px-5 font-medium text-accent-foreground hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          Yol haritamı çıkar
        </button>
      </div>
      {error ? (
        <p id={errorId} role="alert" className="rounded-lg bg-danger-bg p-3 text-danger-fg">
          {error}
        </p>
      ) : null}

      <div className="mt-2">
        <p className="mb-2 text-sm font-medium" id={`${id}-examples`}>
          Örnek sorular
        </p>
        <ul className="flex flex-wrap gap-2" aria-labelledby={`${id}-examples`}>
          {EXAMPLE_QUESTIONS.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => setText(example)}
                className="min-h-11 rounded-full border border-border bg-surface px-4 py-2 text-left text-sm hover:border-accent"
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </form>
  );
}
