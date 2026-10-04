from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _jwk_client(issuer: str) -> PyJWKClient:
    return PyJWKClient(f"{issuer.rstrip('/')}/.well-known/jwks.json")


def _decode(token: str, settings: Settings) -> dict[str, Any]:
    issuer = settings.CLERK_ISSUER
    try:
        signing_key = _jwk_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": settings.CLERK_AUDIENCE is not None},
            audience=settings.CLERK_AUDIENCE,
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired session token") from exc
    except Exception as exc:
        logger.warning("Clerk JWKS unavailable: %s", exc)
        raise AuthenticationError("Could not verify session token") from exc

    authorized_party = claims.get("azp")
    if settings.CLERK_ALLOWED_ORIGINS and authorized_party not in settings.CLERK_ALLOWED_ORIGINS:
        raise AuthenticationError("Token origin is not allowed")

    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise AuthenticationError("Token is missing a subject")
    return claims


def clerk_user_id_from_token(token: str) -> str:
    return str(_decode(token, get_settings())["sub"])