from typing import Any

from fastapi import HTTPException
from httpx import AsyncClient

from app.settings import AppSettings


settings = AppSettings()


def _admin_base() -> str:
    return f"{settings.keycloak.url}/admin/realms/{settings.keycloak.realm}"


async def get_service_account_token() -> str:
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.keycloak.admin_client_id,
        "client_secret": settings.keycloak.admin_client_secret,
    }
    async with AsyncClient() as client:
        resp = await client.post(settings.keycloak.token_url, data=data)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail={"admin_token_failed": resp.text})
        token = (resp.json() or {}).get("access_token")
        if not isinstance(token, str) or not token:
            raise HTTPException(status_code=502, detail="Admin token missing from response")
        return token


async def find_user_by_username(*, admin_token: str, username: str) -> dict[str, Any]:
    async with AsyncClient() as client:
        resp = await client.get(
            f"{_admin_base()}/users",
            params={"username": username, "exact": "true"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail={"user_lookup_failed": resp.text})
        users = resp.json() or []
        if not users:
            raise HTTPException(status_code=404, detail="User not found in Keycloak")
        return users[0]


async def get_realm_role(*, admin_token: str, role_name: str) -> dict[str, Any]:
    async with AsyncClient() as client:
        resp = await client.get(
            f"{_admin_base()}/roles/{role_name}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail={"role_lookup_failed": resp.text})
        return resp.json()


async def assign_realm_role(
    *, admin_token: str, user_id: str, role_repr: dict[str, Any]
) -> None:
    async with AsyncClient() as client:
        resp = await client.post(
            f"{_admin_base()}/users/{user_id}/role-mappings/realm",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=[role_repr],
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail={"role_assign_failed": resp.text})


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": settings.keycloak.client_id,
        "refresh_token": refresh_token,
    }
    if settings.keycloak.client_secret:
        data["client_secret"] = settings.keycloak.client_secret

    async with AsyncClient() as client:
        resp = await client.post(settings.keycloak.user_token_url, data=data)
        if resp.status_code >= 400:
            raise HTTPException(status_code=401, detail={"token_refresh_failed": resp.text})
        return resp.json()


async def assign_persona_role(*, username: str, role_name: str) -> None:
    admin_token = await get_service_account_token()
    user = await find_user_by_username(admin_token=admin_token, username=username)
    user_id = user.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=502, detail="Keycloak user id missing")
    role_repr = await get_realm_role(admin_token=admin_token, role_name=role_name)
    await assign_realm_role(admin_token=admin_token, user_id=user_id, role_repr=role_repr)
