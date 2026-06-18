from fastapi import Depends, HTTPException, Request
from typing import Callable

from app.auth.keycloak import keycloak_oauth2_scheme, User, verify_token
from app.auth.onboarding import has_persona
from app.auth.session import get_session, unsign_session_id


async def get_current_user(
    request: Request, token: str | None = Depends(keycloak_oauth2_scheme)
) -> User:
    if token:
        return await verify_token(token)

    signed = request.cookies.get("session")
    if not signed:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_id = unsign_session_id(signed)
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    session = get_session(session_id)
    if not session or not session.access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return await verify_token(session.access_token)


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