import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from httpx import AsyncClient
from jose import jwk, jwt
from pydantic import BaseModel

from app.settings import AppSettings


settings = AppSettings()
keycloak_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.keycloak.auth_url,
    tokenUrl=settings.keycloak.token_url,
    auto_error=False,
)


class User(BaseModel):
    id: str | None = None
    username: str
    roles: list[str]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_verifier() -> str:
    # 43-128 chars; URL-safe
    return _b64url(secrets.token_bytes(64))


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _b64url(digest)


def build_authorize_url(*, state: str, code_challenge: str) -> str:
    query = urlencode(
        {
            "client_id": settings.keycloak.client_id,
            "response_type": "code",
            "scope": settings.keycloak.scope,
            "redirect_uri": settings.keycloak.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{settings.keycloak.auth_url}?{query}"


def build_end_session_url(*, id_token_hint: str | None) -> str:
    params: dict[str, str] = {
        "client_id": settings.keycloak.client_id,
        "post_logout_redirect_uri": settings.keycloak.post_logout_redirect_uri,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    return f"{settings.keycloak.end_session_url}?{urlencode(params)}"


async def exchange_code_for_tokens(*, code: str, code_verifier: str) -> dict[str, Any]:
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "client_id": settings.keycloak.client_id,
        "code": code,
        "redirect_uri": settings.keycloak.redirect_uri,
        "code_verifier": code_verifier,
    }
    if settings.keycloak.client_secret:
        data["client_secret"] = settings.keycloak.client_secret

    async with AsyncClient() as client:
        resp = await client.post(settings.keycloak.user_token_url, data=data)
        if resp.status_code >= 400:
            raise HTTPException(status_code=401, detail={"token_exchange_failed": resp.text})
        return resp.json()


def _extract_roles(payload: dict[str, Any]) -> list[str]:
    roles: set[str] = set()

    realm_roles = (payload.get("realm_access") or {}).get("roles") or []
    roles.update([r for r in realm_roles if isinstance(r, str)])

    resource_access = payload.get("resource_access") or {}
    client_access = resource_access.get(settings.keycloak.client_id) or {}
    client_roles = client_access.get("roles") or []
    roles.update([r for r in client_roles if isinstance(r, str)])

    return sorted(roles)


def _extract_username(payload: dict[str, Any]) -> str:
    for key in ("preferred_username", "email"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return "unknown"


def _extract_user_id(payload: dict[str, Any]) -> str:
    return payload.get("sub")


async def verify_token(token: str | None) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")

    async with AsyncClient() as client:
        jwks_resp = await client.get(settings.keycloak.jwks_url)
        jwks_resp.raise_for_status()
        keys = (jwks_resp.json() or {}).get("keys") or []

    key_data = None
    if kid:
        for k in keys:
            if k.get("kid") == kid:
                key_data = k
                break
    if key_data is None and keys:
        key_data = keys[0]
    if key_data is None:
        raise HTTPException(status_code=401, detail="No JWKS keys available")

    public_key = jwk.construct(key_data)
    payload = jwt.decode(
        token,
        public_key.to_pem().decode("utf-8"),
        algorithms=[header.get("alg", "RS256")],
        issuer=settings.keycloak.issuer,
        options={"verify_aud": False},
    )

    return User(id=_extract_user_id(payload), username=_extract_username(payload), roles=_extract_roles(payload))
