import asyncio
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from keycloak.exceptions import KeycloakAuthenticationError, KeycloakGetError
from keycloak.pkce_utils import generate_code_challenge, generate_code_verifier
from pydantic import BaseModel

from app.auth.clients.keycloak import get_internal_openid, get_user_openid
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


# Re-export library PKCE helpers under the names used by server.py.
generate_pkce_verifier = generate_code_verifier


def pkce_challenge(verifier: str) -> str:
    challenge, _method = generate_code_challenge(verifier)
    return challenge


def build_authorize_url(*, state: str, code_challenge: str) -> str:
    return get_user_openid().auth_url(
        redirect_uri=settings.keycloak.redirect_uri,
        scope=settings.keycloak.scope,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )


def build_end_session_url(*, id_token_hint: str | None) -> str:
    """
    Required to end the SSO session at Keycloak.
    """
    params: dict[str, str] = {
        "client_id": settings.keycloak.client_id,
        "post_logout_redirect_uri": settings.keycloak.post_logout_redirect_uri,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    return f"{settings.keycloak.end_session_url}?{urlencode(params)}"


def _extract_roles(payload: dict[str, Any]) -> list[str]:
    roles: set[str] = set()

    realm_roles = (payload.get("realm_access") or {}).get("roles") or []
    roles.update(r for r in realm_roles if isinstance(r, str))

    resource_access = payload.get("resource_access") or {}
    client_access = resource_access.get(settings.keycloak.client_id) or {}
    client_roles = client_access.get("roles") or []
    roles.update(r for r in client_roles if isinstance(r, str))

    return sorted(roles)


def _extract_username(payload: dict[str, Any]) -> str:
    for key in ("preferred_username", "email"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return "unknown"


def _extract_user_id(payload: dict[str, Any]) -> str | None:
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def _claims_to_user(payload: dict[str, Any]) -> User:
    return User(
        id=_extract_user_id(payload),
        username=_extract_username(payload),
        roles=_extract_roles(payload),
    )


def _verify_token_sync(token: str) -> User:
    try:
        payload = get_internal_openid().decode_token(token, validate=True)
    except KeycloakAuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    except KeycloakGetError as exc:
        raise HTTPException(status_code=401, detail="Token validation failed") from exc
    return _claims_to_user(payload)


async def verify_token(token: str | None) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return await asyncio.to_thread(_verify_token_sync, token)


def _exchange_code_for_tokens_sync(*, code: str, code_verifier: str) -> dict[str, Any]:
    try:
        return get_user_openid().token(
            grant_type="authorization_code",
            code=code,
            redirect_uri=settings.keycloak.redirect_uri,
            code_verifier=code_verifier,
        )
    except (KeycloakAuthenticationError, KeycloakGetError) as exc:
        raise HTTPException(status_code=401, detail={"token_exchange_failed": str(exc)}) from exc


async def exchange_code_for_tokens(*, code: str, code_verifier: str) -> dict[str, Any]:
    return await asyncio.to_thread(
        _exchange_code_for_tokens_sync,
        code=code,
        code_verifier=code_verifier,
    )
