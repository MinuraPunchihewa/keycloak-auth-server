from fastapi import Depends, HTTPException, Request
from jose.exceptions import ExpiredSignatureError
from typing import Callable

from app.auth.keycloak import keycloak_oauth2_scheme, User, verify_token
from app.auth.onboarding import has_persona
from app.auth.session import get_session, unsign_session_id
from app.auth.session_tokens import LoginRequired, get_user_from_session


async def get_current_user(
    request: Request, token: str | None = Depends(keycloak_oauth2_scheme)
) -> User:
    if token:
        try:
            return await verify_token(token)
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")

    signed = request.cookies.get("session")
    if not signed:
        raise LoginRequired()

    session_id = unsign_session_id(signed)
    if not session_id:
        raise LoginRequired()

    session = get_session(session_id)
    if not session:
        raise LoginRequired()

    return await get_user_from_session(session)


def require_role(role: str) -> Callable[..., User]:
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if role not in user.roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _dep


class OnboardingRequired(Exception):
    pass


async def require_onboarded_user(user: User = Depends(get_current_user)) -> User:
    if not has_persona(user):
        raise OnboardingRequired()
    return user
