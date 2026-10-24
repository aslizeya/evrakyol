"""Türkçe metin yardımcıları."""


def turkish_lower(text: str) -> str:
    """Türkçe küçük harf: İ->i, I->ı. (str.casefold "İ"yi "i" + birleştirici noktaya çevirir.)"""
    return text.replace("İ", "i").replace("I", "ı").lower().replace("̇", "")
