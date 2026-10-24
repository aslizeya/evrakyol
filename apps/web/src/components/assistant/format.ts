const dateFormatter = new Intl.DateTimeFormat("tr-TR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

/** "2026-10-24" -> "24 Ekim 2026" */
export function formatDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? isoDate : dateFormatter.format(date);
}

export const CONFIDENCE_LABELS = {
  yuksek: {
    label: "Yüksek güven",
    help: "Resmi kaynaklar bu işlemin adımlarını açık ve tutarlı biçimde kapsıyor.",
  },
  orta: {
    label: "Orta güven",
    help: "Bazı adımlar kaynaklarda eksik ya da belirsiz; ilgili kurumdan teyit etmeniz özellikle önemli.",
  },
  dusuk: {
    label: "Düşük güven",
    help: "Kaynaklar bu durumu sınırlı kapsıyor; yol haritasını yalnızca başlangıç noktası olarak kullanın.",
  },
} as const;
