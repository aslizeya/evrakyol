// Uçtan uca testler için sahte yapay zekâ servisi. Gerçek web sunucusu (Next.js) bu servise
// gerçek servis anahtarıyla bağlanır; böylece tarayıcı -> /api/* -> servis zinciri baştan sona sınanır.
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_API_PORT ?? 8799);
const TOKEN = "e2e-servis-anahtari";

const source = (baslik, url) => ({ baslik, url, son_kontrol: "2026-10-24" });

const ROADMAP = {
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
        source("Mirasçılık Belgesi", "https://portal.tnb.org.tr/Sayfalar/MirascilikHiz.aspx"),
      ],
    },
    {
      sira: 2,
      baslik: "Aracı trafik tescil kuruluşunda adınıza tescil ettirin",
      aciklama: "Belgelerle yerleşim yerinizdeki trafik tescil kuruluşuna başvurun.",
      gerekli_evraklar: ["Mirasçılık belgesi", "Zorunlu mali sorumluluk sigorta poliçesi"],
      kurum: "Trafik tescil kuruluşu",
      tahmini_ucret: null,
      kaynaklar: [
        source("Trafik Tescil Hakkında", "https://www.egm.gov.tr/trafik-tescil-hakkinda"),
      ],
    },
  ],
  uyarilar: ["Vefat tarihinden itibaren 90 gün içinde tescil kuruluşuna başvurulmalıdır."],
  guven: "yuksek",
};

function understand({ text }) {
  if (/tapu|evi /i.test(text)) {
    return {
      status: "out_of_scope",
      masked_text: text,
      message: "Bu işlem şu an desteklenen işlemler arasında değil.",
    };
  }
  return {
    status: "needs_clarification",
    masked_text: text.replace(/\b\d{11}\b/g, "[TC_KIMLIK]"),
    process_code: "miras_arac_devri",
    process_name: "Miras yoluyla araç devri",
    answers: {},
    questions: [
      {
        key: "mirascilik_belgesi",
        question: "Mirasçılık belgesi (veraset ilamı) alındı mı?",
        options: ["Evet", "Hayır", "Bilmiyorum"],
      },
    ],
  };
}

function roadmap({ text }) {
  if (/kaynaksız/i.test(text)) {
    return {
      status: "no_sources",
      masked_text: text,
      message:
        "Bu işlem için resmi kaynaklarda yeterli bilgi bulunamadı. Lütfen Noterlik ile iletişime geçin.",
      referral: "Noterlik",
    };
  }
  return { status: "ok", masked_text: text, roadmap: ROADMAP };
}

const routes = { "/v1/understand": understand, "/v1/roadmap": roadmap };

createServer((req, res) => {
  const send = (status, payload) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(payload));
  };
  if (req.headers.authorization !== `Bearer ${TOKEN}`) return send(401, { detail: "yetkisiz" });
  const handler = routes[req.url];
  if (req.method !== "POST" || !handler) return send(404, { detail: "yok" });
  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => send(200, handler(JSON.parse(body))));
}).listen(PORT, "127.0.0.1");
