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
  {
    code: "pasaport",
    name: "Pasaport başvurusu ve yenileme",
    description: "Yetişkin ve çocuklar için pasaport türüne göre belgeler, ücretler ve teslim.",
  },
  {
    code: "kimlik_karti_yenileme",
    name: "Kimlik kartı yenileme",
    description: "Nüfus cüzdanı değişimi, kayıp kart ve çocuklar için kimlik kartı başvurusu.",
  },
  {
    code: "ehliyet_yenileme",
    name: "Ehliyet yenileme / değişimi",
    description: "Süresi dolan, eski tip, kayıp veya yurt dışından alınan sürücü belgesi.",
  },
  {
    code: "yerlesim_yeri_belgesi",
    name: "İkametgâh / yerleşim yeri belgesi",
    description: "Belgenin e-Devlet'ten alınması ve taşındıysanız adres bildirimi.",
  },
] as const;

export type GuideCode = (typeof GUIDES)[number]["code"];

export function findGuide(code: string | undefined) {
  return GUIDES.find((guide) => guide.code === code);
}
