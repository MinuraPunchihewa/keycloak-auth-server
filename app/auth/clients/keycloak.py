"""Cached python-keycloak client singletons."""

from functools import lru_cache

from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakOpenIDConnection

from app.settings import AppSettings


@lru_cache
def _settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_user_openid() -> KeycloakOpenID:
    """OpenID client for browser-facing token operations (code exchange, refresh).

    Uses the public Keycloak URL so token issuer claims match what the browser sees.
    """
    keycloak = _settings().keycloak
    return KeycloakOpenID(
        server_url=keycloak.public_url or keycloak.url,
        realm_name=keycloak.realm,
        client_id=keycloak.client_id,
        client_secret_key=keycloak.client_secret,
    )


@lru_cache
def get_internal_openid() -> KeycloakOpenID:
    """OpenID client for server-side validation (decode_token, userinfo, JWKS)."""
    keycloak = _settings().keycloak
    return KeycloakOpenID(
        server_url=keycloak.url,
        realm_name=keycloak.realm,
        client_id=keycloak.client_id,
        client_secret_key=keycloak.client_secret,
    )


@lru_cache
def get_keycloak_admin() -> KeycloakAdmin:
    """Admin API client backed by the fastapi-admin service account."""
    keycloak = _settings().keycloak
    connection = KeycloakOpenIDConnection(
        server_url=keycloak.url,
        realm_name=keycloak.realm,
        client_id=keycloak.admin_client_id,
        client_secret_key=keycloak.admin_client_secret,
    )
    return KeycloakAdmin(connection=connection)
