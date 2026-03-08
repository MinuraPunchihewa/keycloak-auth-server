import secrets
from dataclasses import dataclass
from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer

from app.settings import AppSettings


settings = AppSettings()
_serializer = URLSafeSerializer(settings.session_secret_key, salt="session")


@dataclass
class SessionData:
    # pending auth
    state: str | None = None
    code_verifier: str | None = None

    # tokens after callback
    access_token: str | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    token_type: str | None = None


_SESSIONS: dict[str, SessionData] = {}


def new_session() -> tuple[str, SessionData]:
    session_id = secrets.token_urlsafe(32)
    data = SessionData()
    _SESSIONS[session_id] = data
    return session_id, data


def get_session(session_id: str) -> SessionData | None:
    return _SESSIONS.get(session_id)


def delete_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def sign_session_id(session_id: str) -> str:
    return _serializer.dumps({"sid": session_id})


def unsign_session_id(signed_value: str) -> str | None:
    try:
        raw: Any = _serializer.loads(signed_value)
    except BadSignature:
        return None
    if isinstance(raw, dict) and isinstance(raw.get("sid"), str):
        return raw["sid"]
    return None
