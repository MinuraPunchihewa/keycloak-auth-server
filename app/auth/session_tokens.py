from typing import Any

from fastapi import HTTPException
from jose.exceptions import ExpiredSignatureError

from app.auth.keycloak import User, verify_token
from app.auth.keycloak_admin import refresh_access_token
from app.auth.session import SessionData


class LoginRequired(Exception):
    pass


def apply_token_response(session: SessionData, tokens: dict[str, Any]) -> None:
    session.access_token = tokens.get("access_token")
    if tokens.get("refresh_token"):
        session.refresh_token = tokens.get("refresh_token")
    if tokens.get("id_token"):
        session.id_token = tokens.get("id_token")
    session.token_type = tokens.get("token_type")


async def refresh_session_tokens(session: SessionData) -> None:
    if not session.refresh_token:
        raise LoginRequired()
    try:
        tokens = await refresh_access_token(session.refresh_token)
    except HTTPException:
        raise LoginRequired() from None
    if not isinstance(tokens.get("access_token"), str):
        raise LoginRequired()
    apply_token_response(session, tokens)


async def get_user_from_session(session: SessionData) -> User:
    if not session.access_token:
        raise LoginRequired()
    try:
        return await verify_token(session.access_token)
    except ExpiredSignatureError:
        await refresh_session_tokens(session)
        return await verify_token(session.access_token)
