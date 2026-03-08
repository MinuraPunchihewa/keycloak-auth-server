from fastapi.security import OAuth2AuthorizationCodeBearer
from httpx import AsyncClient
from jose import jwt
from pydantic import BaseModel

from app.settings import AppSettings


settings = AppSettings()
keycloak_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.keycloak.auth_url,
    tokenUrl=settings.keycloak.token_url,
    auto_error=False,
)


class User(BaseModel):
    username: str
    roles: list[str]


async def verify_token(token: str) -> User:
    async with AsyncClient() as client:
        response = await client.get(settings.keycloak.jwks_url)
        jwks = jwt.jwks_from_pem(response.json()["keys"])
        payload = jwt.decode(token, jwks, algorithms=["RS256"])
        return User(username=payload["sub"], roles=payload["roles"])