import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth.deps import (
    OnboardingRequired,
    get_current_user,
    require_onboarded_user,
    require_role,
)
from app.auth.keycloak import (
    User,
    build_authorize_url,
    build_end_session_url,
    exchange_code_for_tokens,
    generate_pkce_verifier,
    pkce_challenge,
    verify_token,
)
from app.auth.keycloak_admin import assign_persona_role, refresh_access_token
from app.auth.onboarding import has_persona, is_valid_persona
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

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")


@app.exception_handler(OnboardingRequired)
async def onboarding_required_handler(request: Request, exc: OnboardingRequired) -> RedirectResponse:
    return RedirectResponse(url="/onboarding", status_code=302)


async def _optional_user(request: Request) -> User | None:
    signed = request.cookies.get("session")
    if not signed:
        return None
    session_id = unsign_session_id(signed)
    if not session_id:
        return None
    session = get_session(session_id)
    if not session or not session.access_token:
        return None
    try:
        return await verify_token(session.access_token)
    except HTTPException:
        return None


@app.get("/")
async def read_root(request: Request):
    user = await _optional_user(request)
    return templates.TemplateResponse(
        request,
        "home.html",
        {"request": request, "user": user},
    )


@app.get("/onboarding")
async def onboarding_page(request: Request, user: User = Depends(get_current_user)):
    if has_persona(user):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {"request": request, "user": user},
    )


@app.post("/onboarding/role")
async def onboarding_role(
    request: Request,
    role: str = Form(...),
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    if has_persona(user):
        raise HTTPException(status_code=409, detail="Persona already assigned")

    if not is_valid_persona(role):
        raise HTTPException(status_code=400, detail="Invalid persona role")

    await assign_persona_role(username=user.username, role_name=role)

    signed = request.cookies.get("session")
    if signed:
        session_id = unsign_session_id(signed)
        if session_id:
            session = get_session(session_id)
            if session and session.refresh_token:
                tokens = await refresh_access_token(session.refresh_token)
                session.access_token = tokens.get("access_token")
                if tokens.get("refresh_token"):
                    session.refresh_token = tokens.get("refresh_token")
                if tokens.get("id_token"):
                    session.id_token = tokens.get("id_token")
                session.token_type = tokens.get("token_type")

    return RedirectResponse(url="/", status_code=302)


@app.get("/protected")
async def protected(
    request: Request,
    user: User = Depends(require_onboarded_user),
):
    return templates.TemplateResponse(
        request,
        "protected.html",
        {"request": request, "user": user},
    )


@app.get("/buyer")
async def buyer_area(
    request: Request,
    user: User = Depends(require_role("buyer")),
):
    return templates.TemplateResponse(
        request,
        "buyer.html",
        {"request": request, "user": user},
    )


@app.get("/seller")
async def seller_area(
    request: Request,
    user: User = Depends(require_role("seller")),
):
    return templates.TemplateResponse(
        request,
        "seller.html",
        {"request": request, "user": user},
    )


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

    user = await verify_token(session.access_token)
    next_url = "/onboarding" if not has_persona(user) else "/"
    return RedirectResponse(url=next_url, status_code=302)


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
