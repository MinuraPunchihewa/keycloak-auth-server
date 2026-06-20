import asyncio

from fastapi import HTTPException
from keycloak.exceptions import KeycloakAuthenticationError, KeycloakGetError

from app.auth.clients.keycloak import get_keycloak_admin, get_user_openid


def _refresh_access_token_sync(refresh_token: str) -> dict:
    try:
        return get_user_openid().refresh_token(refresh_token)
    except (KeycloakAuthenticationError, KeycloakGetError) as exc:
        raise HTTPException(status_code=401, detail={"token_refresh_failed": str(exc)}) from exc


async def refresh_access_token(refresh_token: str) -> dict:
    return await asyncio.to_thread(_refresh_access_token_sync, refresh_token)


def _assign_persona_role_sync(*, username: str, role_name: str) -> None:
    admin = get_keycloak_admin()
    try:
        users = admin.get_users(query={"username": username, "exact": True})
        if not users:
            raise HTTPException(status_code=404, detail="User not found in Keycloak")

        user_id = users[0].get("id")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(status_code=502, detail="Keycloak user id missing")

        role = admin.get_realm_role(role_name)
        admin.assign_realm_roles(user_id=user_id, roles=[role])
    except KeycloakGetError as exc:
        raise HTTPException(status_code=502, detail={"keycloak_admin_failed": str(exc)}) from exc


async def assign_persona_role(*, username: str, role_name: str) -> None:
    await asyncio.to_thread(_assign_persona_role_sync, username=username, role_name=role_name)
