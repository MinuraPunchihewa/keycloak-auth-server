from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


class KeycloakSettings(Settings):
    # Internal URL used by the FastAPI service (e.g. Docker DNS name).
    url: str = Field(default="http://localhost:8080")
    # Public URL used in browser redirects (must be reachable from the user agent).
    public_url: str | None = Field(default=None)
    realm: str = Field(default="dev")
    client_id: str = Field(default="fastapi-server")
    client_secret: str | None = Field(default=None)
    admin_client_id: str = Field(default="fastapi-admin")
    admin_client_secret: str = Field(default="dev-admin-secret-change-me")

    redirect_uri: str = Field(default="http://localhost:8000/auth/callback")
    post_logout_redirect_uri: str = Field(default="http://localhost:8000/")
    scope: str = Field(default="openid profile email")

    @computed_field
    @property
    def auth_url(self) -> str:
        base = self.public_url or self.url
        return f"{base}/realms/{self.realm}/protocol/openid-connect/auth"

    @computed_field
    @property
    def token_url(self) -> str:
        return f"{self.url}/realms/{self.realm}/protocol/openid-connect/token"

    @computed_field
    @property
    def end_session_url(self) -> str:
        base = self.public_url or self.url
        return f"{base}/realms/{self.realm}/protocol/openid-connect/logout"

    @computed_field
    @property
    def jwks_url(self) -> str:
        return f"{self.url}/realms/{self.realm}/protocol/openid-connect/certs"

    @computed_field
    @property
    def issuer(self) -> str:
        base = self.public_url or self.url
        return f"{base}/realms/{self.realm}"


class AppSettings(Settings):
    keycloak: KeycloakSettings = Field(default_factory=KeycloakSettings)
    session_secret_key: str = Field(default="dev-only-change-me")
    cookie_secure: bool = Field(default=False)