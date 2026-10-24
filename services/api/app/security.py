import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def require_internal_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Web uygulamasından gelen servisler arası çağrıları doğrular (Authorization: Bearer <token>).

    Anahtar tanımlı değilse uç noktalar kapalıdır (yanlışlıkla açık kalmasın diye).
    """
    expected = settings.internal_api_token
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "INTERNAL_API_TOKEN tanımlı değil")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Geçersiz servis anahtarı")
