import pytest

from app.privacy import mask_pii


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("TC kimlik numaram 12345678901 dir", "TC_KIMLIK"),
        ("Plakası 34 ABC 123 olan araç", "PLAKA"),
        ("plaka 06abc1234", "PLAKA"),
        ("Telefonum 0532 123 45 67", "TELEFON"),
        ("+90 (212) 555 12 34 numarasını arayın", "TELEFON"),
        ("e-postam ali.veli@example.com", "E_POSTA"),
        ("IBAN: TR33 0006 1005 1978 6457 8413 26", "IBAN"),
        ("Atatürk Mahallesi Gül Sokak No: 5 Daire 3 adresinde", "ADRES"),
    ],
)
def test_masks_personal_data(text: str, label: str) -> None:
    result = mask_pii(text)
    assert f"[{label}]" in result.text
    assert result.found.get(label, 0) >= 1


def test_masked_values_do_not_survive() -> None:
    text = "Babam 12345678901 vefat etti, 34 ABC 123 plakalı aracı üzerime almak istiyorum."
    masked = mask_pii(text).text
    assert "12345678901" not in masked
    assert "34 ABC 123" not in masked
    assert "vefat etti" in masked and "üzerime almak istiyorum" in masked


@pytest.mark.parametrize(
    "text",
    [
        "Babamdan kalan arabayı üzerime almak istiyorum",
        "2918 sayılı Karayolları Trafik Kanunu",
        "Ücret 1.250 TL",
        "10 TL 500 kuruş",
        "Mirasçılık belgesi için 3 kardeşiz",
    ],
)
def test_ordinary_text_is_untouched(text: str) -> None:
    result = mask_pii(text)
    assert result.text == text
    assert not result.had_personal_data


def test_consecutive_same_labels_are_merged() -> None:
    assert mask_pii("Gül Sokak No: 5").text.count("[ADRES]") == 1
