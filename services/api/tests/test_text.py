from app.text import turkish_lower


def test_turkish_lower() -> None:
    assert turkish_lower("İSTANBUL IĞDIR") == "istanbul ığdır"
    assert turkish_lower("HENÜZ KİMLİĞİNİZİ") == turkish_lower("Henüz kimliğinizi")
    assert len(turkish_lower("İ")) == 1
