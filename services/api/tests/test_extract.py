from app.ingest.extract import Block, Document, _drop_repeated_lines, extract_html, lines_to_blocks

# Gerçek sayfalardaki yapıları taklit eden küçük örnekler (EGM, TNB, ASP.NET form sarmalı).
EGM_LIKE = """
<html><head><title>EGM - Trafik Tescil Hakkında</title></head><body>
<form id="aspnetForm">
  <nav><a href="/">Ana Sayfa</a><a href="/x">Hizmetler</a></nav>
  <div class="cookie-modal">Sitemizde çerezler kullanılmaktadır.</div>
  <main>
    <h1>Trafik Tescil Hakkında</h1>
    <div><span style="font-weight:bold"><font>A- YENİ KAYIT (FATURALI) TESCİL İŞLEMİ:</font>
    </span></div>
    <div><span style="font-weight:bold">1- Fatura,</span></div>
    <div><span style="font-weight:bold">2- Uygunluk belgesi,</span></div>
    <div><b>İbraz edilmesi gerekmektedir.</b></div>
    <div><span style="font-weight:bold">E- VERASET YOLUYLA İNTİKAL EDEN ARAÇLAR:</span></div>
    <div><span style="font-weight:bold">1- Veraset ilamı veya mirasçılık belgesinin,</span></div>
    <div><span style="font-weight:bold">2- Nüfus cüzdanı aslının (varislerin),</span></div>
    <div>Varisler tarafından yerleşim yeri adresinin bulunduğu trafik tescil kuruluşuna ibraz
      edilmesi gerekmektedir. Bu paragraf ana sayfa içeriğinin yeterince uzun olması için
      biraz daha metin içerir ve gerçek sayfadaki açıklamaları temsil eder.</div>
    <ul><li><a href="/a">Bağlantı 1</a></li><li><a href="/b">Bağlantı 2</a></li></ul>
  </main>
  <footer>Tüm hakları saklıdır.</footer>
</form>
</body></html>
"""


def test_html_recognises_bold_and_uppercase_pseudo_headings() -> None:
    doc = extract_html(EGM_LIKE.encode())
    headings = [b.text for b in doc.blocks if b.kind == "heading"]
    assert headings == [
        "Trafik Tescil Hakkında",
        "A- YENİ KAYIT (FATURALI) TESCİL İŞLEMİ",
        "E- VERASET YOLUYLA İNTİKAL EDEN ARAÇLAR",
    ]


def test_html_keeps_numbered_list_items_and_bold_sentences_as_text() -> None:
    texts = [b.text for b in extract_html(EGM_LIKE.encode()).blocks if b.kind == "text"]
    assert "1- Veraset ilamı veya mirasçılık belgesinin," in texts
    assert "İbraz edilmesi gerekmektedir." in texts


def test_html_drops_navigation_cookie_notice_footer_and_link_lists() -> None:
    text = extract_html(EGM_LIKE.encode()).plain_text()
    for noise in ("Ana Sayfa", "çerez", "Tüm hakları saklıdır", "Bağlantı 1"):
        assert noise not in text


def test_html_title_and_whitespace_normalisation() -> None:
    doc = extract_html(EGM_LIKE.encode())
    assert doc.title == "EGM - Trafik Tescil Hakkında"
    assert all("  " not in b.text and "\n" not in b.text for b in doc.blocks)


def test_html_block_inside_inline_wrapper_is_not_flattened() -> None:
    page = """<html><body><div><span>
        <p><strong>Noterden Mirasçılık Belgesi Nasıl Alınır?</strong></p>
        <ol><li>Kimlik belgesi,</li><li>Başvuru formu,</li></ol>
    </span></div></body></html>""".encode()
    blocks = extract_html(page).blocks
    assert blocks[0] == Block("heading", "Noterden Mirasçılık Belgesi Nasıl Alınır?", 4)
    assert Block("text", "- Kimlik belgesi,") in blocks


def test_html_table_rows_become_text_lines() -> None:
    page = (
        "<html><body><table><tr><th>Belge</th><th>Kurum</th></tr>"
        "<tr><td>Mirasçılık belgesi</td><td>Noter</td></tr></table></body></html>"
    )
    texts = [b.text for b in extract_html(page.encode()).blocks]
    assert texts == ["Belge | Kurum", "Mirasçılık belgesi | Noter"]


def test_content_hash_ignores_boilerplate_changes() -> None:
    changed_footer = EGM_LIKE.replace("Tüm hakları saklıdır.", "© 2027 Yeni altbilgi")
    assert (
        extract_html(EGM_LIKE.encode()).content_hash()
        == extract_html(changed_footer.encode()).content_hash()
    )
    changed_content = EGM_LIKE.replace("2- Nüfus cüzdanı", "2- Kimlik kartı")
    assert (
        extract_html(EGM_LIKE.encode()).content_hash()
        != extract_html(changed_content.encode()).content_hash()
    )


def test_pdf_repeated_headers_and_page_numbers_are_removed() -> None:
    pages = [["GİB Broşürü", f"İçerik {i}", str(i)] for i in range(1, 5)]
    assert _drop_repeated_lines(pages) == ["İçerik 1", "İçerik 2", "İçerik 3", "İçerik 4"]


def test_pdf_lines_merge_into_paragraphs_with_uppercase_headings() -> None:
    lines = [
        "VERASET VE İNTİKAL VERGİSİ NE ZAMAN VERİLİR?",
        "Beyanname ölüm tarihini takip eden 4 ay",
        "içinde verilir.",
        "• Veraset ilamı (mirasçılık belgesi),",
        "• Vasiyetname,",
    ]
    assert lines_to_blocks(lines) == [
        Block("heading", "VERASET VE İNTİKAL VERGİSİ NE ZAMAN VERİLİR?", 3),
        Block("text", "Beyanname ölüm tarihini takip eden 4 ay içinde verilir."),
        Block("text", "• Veraset ilamı (mirasçılık belgesi),"),
        Block("text", "• Vasiyetname,"),
    ]


def test_document_plain_text() -> None:
    doc = Document(title=None, blocks=[Block("heading", "Başlık", 2), Block("text", "Metin")])
    assert doc.plain_text() == "Başlık\nMetin"
