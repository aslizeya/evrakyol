import type { Roadmap } from "@/lib/api-schemas";

export const ROADMAP: Roadmap = {
  islem: "miras_arac_devri",
  ozet: "Önce noterden mirasçılık belgesi alınır, ardından araç trafik tescil kuruluşunda tescil edilir.",
  adimlar: [
    {
      sira: 1,
      baslik: "Noterden mirasçılık belgesi alın",
      aciklama: "Kimlik belgenizle herhangi bir noterliğe başvurun.",
      gerekli_evraklar: ["T.C. kimlik numaralı kimlik belgesi"],
      kurum: "Noterlik",
      tahmini_ucret: null,
      kaynaklar: [
        {
          baslik: "Mirasçılık Belgesi",
          url: "https://portal.tnb.org.tr/Sayfalar/MirascilikHiz.aspx",
          son_kontrol: "2026-10-24",
        },
      ],
    },
    {
      sira: 2,
      baslik: "Aracı adınıza tescil ettirin",
      aciklama: "Belgelerle trafik tescil kuruluşuna başvurun.",
      gerekli_evraklar: ["Mirasçılık belgesi", "Zorunlu mali sorumluluk sigorta poliçesi"],
      kurum: "Trafik tescil kuruluşu",
      tahmini_ucret: "1.250,50 TL",
      kaynaklar: [
        {
          baslik: "Trafik Tescil Hakkında",
          url: "https://www.egm.gov.tr/trafik-tescil-hakkinda",
          son_kontrol: "2026-10-20",
        },
      ],
    },
  ],
  uyarilar: ["Vefat tarihinden itibaren 90 gün içinde tescil kuruluşuna başvurulmalıdır."],
  guven: "yuksek",
};

type Route = { status?: number; body: unknown };

/** Yol bazında sırayla yanıt veren sahte fetch; çağrıları kaydeder. */
export function fakeFetch(routes: Record<string, Route[]>) {
  const calls: { url: string; body: unknown }[] = [];
  const fn = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const queue = routes[url];
    const next = queue?.shift();
    if (!next) throw new TypeError("network");
    return new Response(JSON.stringify(next.body), {
      status: next.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  return { fn, calls };
}
