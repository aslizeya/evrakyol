"""RAG testleri için ortak örnek veriler (gerçek kaynaklardan kısaltılmış metinler)."""

import json
from datetime import UTC, datetime, timedelta

from app.process_types import ProcessType, Slot
from app.rag.retrieval import RetrievedChunk

NOW = datetime.now(UTC)

MIRAS_ARAC = ProcessType(
    code="miras_arac_devri",
    name="Miras yoluyla araç devri",
    description="Vefat eden kişinin aracının mirasçılara devri.",
    referral="Noterlik veya trafik tescil kuruluşu",
    slots=[
        Slot(key="mirascilik_belgesi", question="Mirasçılık belgesi alındı mı?",
             options=["Evet", "Hayır", "Bilmiyorum"]),
        Slot(key="mirasci_sayisi", question="Kaç mirasçı var?",
             options=["Tek mirasçı", "Birden fazla mirasçı", "Bilmiyorum"]),
    ],
)  # fmt: skip

PASAPORT = ProcessType(
    code="pasaport",
    name="Pasaport başvurusu",
    description="Pasaport başvurusu ve yenileme.",
    referral="Nüfus müdürlüğü",
)

PROCESS_TYPES = [MIRAS_ARAC, PASAPORT]


def chunk(
    chunk_id: int,
    content: str,
    *,
    source_id: int = 1,
    title: str = "Mirasçılık Belgesi",
    url: str = "https://portal.tnb.org.tr/Sayfalar/MirascilikHiz.aspx",
    heading: str | None = None,
    fetched: datetime | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        source_title=title,
        url=url,
        institution="Türkiye Noterler Birliği",
        heading_path=heading,
        content=content,
        last_fetched_at=fetched or NOW - timedelta(days=1),
        score=1.0,
    )


TNB = chunk(
    1,
    "Aşağıdaki belgeler ile bir noterliğe gidiniz:\nT.C. Kimlik Numarası yazılı olan kimlik "
    "belgesi,\nMirasçılık Belgesi sistem tarafından yaklaşık üç dakika içerisinde hazırlanacaktır.",
    heading="MİRASÇILIK BELGESİ > Noterden Mirasçılık Belgesi Nasıl Alınır?",
)
EGM = chunk(
    2,
    "1- Veraset ilamı veya mirasçılık belgesinin,\n2- Nüfus cüzdanı aslının (varislerin),\n"
    "3- Vergi dairesinden alınan veraset intikali yönünden borcu olmadığına dair belgenin,\n"
    "Varisler tarafından yerleşim yeri adresinin bulunduğu trafik tescil kuruluşuna ibraz "
    "edilmesi gerekmektedir. Harç tutarı 1.250,50 TL olarak tahsil edilir.",
    source_id=2,
    title="Trafik Tescil Hakkında",
    url="https://www.egm.gov.tr/trafik-tescil-hakkinda",
    heading="Trafik Tescil Hakkında > E- VERASET YOLUYLA İNTİKAL EDEN ARAÇLAR",
)
TRAFIK = chunk(
    3,
    "Araç sahiplerinin vefat etmesi halinde mirasçılar, gerekli bilgi ve belgeleri sağlayarak "
    "vefat tarihinden itibaren 90 gün içinde ilgili tescil kuruluşuna müracaat etmek ve "
    "adlarına tescil belgesi almak zorunda olacak.",
    source_id=3,
    title="Karayolları Trafik Kanunu değişikliği (27.02.2026)",
    url="https://www.trafik.gov.tr/x",
    fetched=NOW - timedelta(days=45),
)
CHUNKS = [TNB, EGM, TRAFIK]


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]):
        self.chunks = chunks
        self.queries: list[tuple[str, str]] = []

    def search(self, query: str, process_code: str, limit: int = 10) -> list[RetrievedChunk]:
        self.queries.append((query, process_code))
        return self.chunks[:limit]


def step(baslik: str, dayanaklar: list[tuple[str, str]], ucret: str | None = None) -> dict:
    return {
        "baslik": baslik,
        "aciklama": f"{baslik} açıklaması",
        "gerekli_evraklar": ["Kimlik belgesi"],
        "kurum": "Noterlik",
        "tahmini_ucret": ucret,
        "dayanaklar": [{"kaynak": k, "alinti": a} for k, a in dayanaklar],
    }


def roadmap_json(steps: list[dict], warnings: list[dict] | None = None, **overrides) -> str:
    data = {
        "yeterli_kaynak": True,
        "ozet": "Önce noterden mirasçılık belgesi alınır, sonra araç tescil edilir.",
        "adimlar": steps,
        "uyarilar": warnings or [],
        "guven": "yuksek",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


GOOD_STEPS = [
    step("Noterden mirasçılık belgesi alın", [("K1", "bir noterliğe gidiniz")]),
    step(
        "Aracı trafik tescil kuruluşunda adınıza tescil ettirin",
        [("K2", "Veraset ilamı veya mirasçılık belgesinin")],
    ),
]
