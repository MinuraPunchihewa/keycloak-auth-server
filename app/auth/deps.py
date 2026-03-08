from fastapi import Depends, HTTPException
from functools import wraps
from typing import Any, Callable

from app.auth.keycloak import keycloak_oauth2_scheme, User, verify_token


async def get_current_user(token: str = Depends(keycloak_oauth2_scheme)) -> User:
    return await verify_token(token)


def has_role(role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = await get_current_user(*args, **kwargs)
            if role not in user.roles:
                raise HTTPException(status_code=403, detail="Forbidden")
            return await func(*args, **kwargs)
        return wrapper
    return decorator