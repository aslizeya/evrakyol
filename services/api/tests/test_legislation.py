from app.ingest.legislation import parse_ranges, split_articles

# Mevzuat Bilgi Sistemi PDF biçimleri: eski "Madde 598 -" ve yeni "MADDE 20 –".
TMK_LIKE = [
    "TÜRK MEDENİ KANUNU",
    "Kanun Numarası : 4721",
    "I. Kan hısımları",
    "1. Altsoy",
    "Madde 495- Mirasbırakanın mirasçıları, öncelikle altsoyudur.",
    "Çocuklar, mirasçı olarak eşit paylar alırlar.",
    "Madde 496- Altsoyu bulunmayan mirasbırakanın mirasçıları ana ve babasıdır.",
    "B. Mirasçılık belgesi",
    "Madde 598- Yasal mirasçılara, istemleri üzerine sulh mahkemesince veya noterlikçe",
    "mirasçılık sıfatlarını gösteren bir belge verilir.",
    "Madde 599- Mirasçılar, mirasbırakanın ölümüyle mirası bir bütün olarak kazanırlar.",
    "Geçici Madde 1- Bu Kanunun yürürlüğe girmesinden önce...",
]

NOTERLIK_LIKE = [
    "Mirasçılık belgesi düzenlenmesi:",
    "MADDE 71/B – (Ek: 31/3/2011-6217/9 md.) Noterler, mirasçılık belgesi düzenler.",
    "MADDE 72 – Noter, kimliğini tespit eder.",
]


def test_splits_articles_and_moves_side_titles_to_their_article() -> None:
    preamble, articles = split_articles(TMK_LIKE)
    labels = [a.label for a in articles]
    assert labels == ["495", "496", "598", "599", "Geçici 1"]
    assert articles[0].heading == "Madde 495 – I. Kan hısımları / 1. Altsoy"
    assert articles[2].heading == "Madde 598 – B. Mirasçılık belgesi"
    # Kenar başlığı bir önceki maddenin metninde kalmamalı
    assert "B. Mirasçılık belgesi" not in articles[1].lines
    assert preamble == ["TÜRK MEDENİ KANUNU", "Kanun Numarası : 4721"]


def test_article_text_includes_continuation_lines() -> None:
    _, articles = split_articles(TMK_LIKE)
    assert articles[2].lines == [
        "Yasal mirasçılara, istemleri üzerine sulh mahkemesince veya noterlikçe",
        "mirasçılık sıfatlarını gösteren bir belge verilir.",
    ]


def test_filters_by_article_ranges_and_excludes_supplementary_articles() -> None:
    _, articles = split_articles(TMK_LIKE, ["495-496", "598"])
    assert [a.label for a in articles] == ["495", "496", "598"]


def test_new_style_articles_with_letter_suffix() -> None:
    _, articles = split_articles(NOTERLIK_LIKE, ["71"])
    assert len(articles) == 1
    assert articles[0].label == "71/B"
    assert articles[0].heading == "Madde 71/B – Mirasçılık belgesi düzenlenmesi"


def test_parse_ranges() -> None:
    assert parse_ranges(["495-501", "598"]) == [(495, 501), (598, 598)]
