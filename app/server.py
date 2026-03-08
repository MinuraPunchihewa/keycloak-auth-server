import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth.deps import get_current_user
from app.auth.keycloak import (
    User,
    build_authorize_url,
    build_end_session_url,
    exchange_code_for_tokens,
    generate_pkce_verifier,
    pkce_challenge,
)
from app.auth.session import (
    delete_session,
    get_session,
    new_session,
    sign_session_id,
    unsign_session_id,
)
from app.settings import AppSettings


app = FastAPI()
settings = AppSettings()

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"message": f"Hello, {user.username}!"}


@app.get("/login")
async def login() -> RedirectResponse:
    session_id, session = new_session()

    session.state = secrets.token_urlsafe(16)
    session.code_verifier = generate_pkce_verifier()
    url = build_authorize_url(
        state=session.state,
        code_challenge=pkce_challenge(session.code_verifier),
    )

    resp = RedirectResponse(url=url, status_code=302)
    resp.set_cookie(
        "session",
        sign_session_id(session_id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return resp


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str | None = None, state: str | None = None) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code/state")

    signed = request.cookies.get("session")
    if not signed:
        raise HTTPException(status_code=400, detail="Missing session cookie")

    session_id = unsign_session_id(signed)
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session cookie")

    session = get_session(session_id)
    if not session or not session.code_verifier or not session.state:
        raise HTTPException(status_code=400, detail="Unknown session")
    if session.state != state:
        raise HTTPException(status_code=400, detail="State mismatch")

    tokens = await exchange_code_for_tokens(code=code, code_verifier=session.code_verifier)
    session.access_token = tokens.get("access_token")
    session.refresh_token = tokens.get("refresh_token")
    session.id_token = tokens.get("id_token")
    session.token_type = tokens.get("token_type")

    return RedirectResponse(url="/", status_code=302)


@app.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    signed = request.cookies.get("session")
    id_token_hint = None
    if signed:
        session_id = unsign_session_id(signed)
        if session_id:
            session = get_session(session_id)
            if session:
                id_token_hint = session.id_token
            delete_session(session_id)

    resp = RedirectResponse(url=build_end_session_url(id_token_hint=id_token_hint), status_code=302)
    resp.delete_cookie("session", path="/")
    return resp