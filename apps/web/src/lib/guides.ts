// Sorularla ilerleyen rehberi hazır olan işlemler (config/rehber/*.yaml ile aynı kodlar).
export const GUIDES = [
  {
    code: "miras_arac_devri",
    name: "Miras yoluyla araç devri",
    description: "Vefat eden yakınınızın adına kayıtlı aracın mirasçılar adına tescili.",
  },
  {
    code: "mirascilik_belgesi",
    name: "Mirasçılık belgesi (veraset ilamı)",
    description: "Mirasçıları gösteren belgenin noterden veya mahkemeden alınması.",
  },
] as const;

export type GuideCode = (typeof GUIDES)[number]["code"];

export function findGuide(code: string | undefined) {
  return GUIDES.find((guide) => guide.code === code);
}
