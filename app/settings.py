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
    url: str = Field(default="http://localhost:8080")
    realm: str = Field(default="dev")
    client_id: str = Field(default="fastapi-server")

    @computed_field
    @property
    def auth_url(self) -> str:
        return f"{self.url}/realms/{self.realm}/protocol/openid-connect/auth"

    @computed_field
    @property
    def token_url(self) -> str:
        return f"{self.url}/realms/{self.realm}/protocol/openid-connect/token"

    @computed_field
    @property
    def jwks_url(self) -> str:
        return f"{self.url}/realms/{self.realm}/protocol/openid-connect/certs"


class AppSettings(Settings):
    keycloak: KeycloakSettings = Field(default_factory=KeycloakSettings)