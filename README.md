# Keycloak Auth Server

A FastAPI application that demonstrates OpenID Connect authentication with [Keycloak](https://www.keycloak.org/). It implements the authorization code flow with PKCE, stores tokens in a server-side session, and protects routes by validating JWT access tokens against Keycloak's JWKS endpoint.

## How OAuth works

[OAuth 2.0](https://oauth.net/2/) is a standard for **delegated authorization**: an app can access resources on a user's behalf without handling their password. [OpenID Connect (OIDC)](https://openid.net/connect/) builds on OAuth and adds identity — who the user is — via an ID token and standard claims in the access token.

This project uses the **authorization code flow with PKCE**, which is the recommended approach for web apps. Keycloak acts as the **authorization server**; the FastAPI app is the **client**; protected API routes are the **resource server**.

### Roles

| Role | In this project |
|------|-----------------|
| **Resource owner** | The person signing in (register or use an existing account) |
| **Client** | The FastAPI app (`fastapi-server`) |
| **Authorization server** | Keycloak (issues tokens after login) |
| **Resource server** | The FastAPI app again (validates tokens on `/protected`) |

### Login flow (step by step)

1. **User starts login** — The browser visits `/login`. The app creates a session, generates a random `state` value and a PKCE `code_verifier`, and stores them server-side.

2. **Redirect to Keycloak** — The app redirects the browser to Keycloak's authorization endpoint with parameters such as `client_id`, `redirect_uri`, `scope`, `state`, and `code_challenge` (a hash of the verifier). The user never sees the PKCE verifier; only the challenge is sent in the URL.

3. **User authenticates** — Keycloak shows a login page. The user enters credentials or uses Google sign-in. Keycloak validates them; the app never receives the password.

4. **Authorization grant** — If login succeeds, Keycloak redirects the browser back to `/auth/callback` with a short-lived **authorization code** and the same `state` value.

5. **Verify state** — The app compares the returned `state` with the value stored in the session. This prevents CSRF attacks where a malicious site tries to complete a login with someone else's code.

6. **Exchange code for tokens** — The app sends a server-to-server POST to Keycloak's token endpoint with the authorization code, `client_id`, `redirect_uri`, and the original `code_verifier`. Keycloak checks that the verifier matches the earlier `code_challenge`, then returns tokens.

7. **Store tokens** — The app saves the **access token**, **refresh token**, and **ID token** in the server-side session and sets a signed `session` cookie on the browser. The tokens themselves stay on the server; the cookie is only an opaque session reference.

8. **Onboarding (first login only)** — If the user has neither the `buyer` nor `seller` realm role, the app redirects to `/onboarding`. The user picks a persona; the backend assigns the role via the Keycloak Admin API and refreshes the session token so roles appear immediately.

9. **Redirect home** — The browser is sent to `/`. The user is now logged in (and onboarded if this was their first visit).

### Accessing a protected resource (step by step)

1. **Request a protected route** — The browser requests `/protected` and sends the `session` cookie automatically.

2. **Resolve the session** — The app reads the cookie, looks up the stored access token, and validates it.

3. **Validate the JWT** — The app fetches Keycloak's public keys (JWKS), verifies the access token's signature, issuer, and expiry, and reads claims such as `preferred_username` and roles.

4. **Return the response** — If the token is valid, the route handler runs and returns data for that user. If not, the app responds with `401 Unauthorized`.

Alternatively, API clients can send the access token directly in an `Authorization: Bearer <token>` header instead of using the session cookie.

### Logout flow (step by step)

1. **User visits `/logout`** — The app deletes the local session and clears the `session` cookie.

2. **Redirect to Keycloak** — The browser is redirected to Keycloak's end-session endpoint, optionally with an `id_token_hint`, so Keycloak can end the SSO session too.

3. **Return to the app** — Keycloak redirects back to the configured post-logout URL (`/`). The user must log in again to access protected routes.

### Why PKCE?

PKCE (*Proof Key for Code Exchange*) protects public clients that cannot keep a client secret in the browser. The app generates a secret verifier, sends only a hash to Keycloak, and proves possession of the verifier when exchanging the code. Even if an attacker intercepts the authorization code, they cannot redeem it without the verifier stored in the app's session.

## What it does

- **Login via Keycloak** — `/login` redirects the browser to Keycloak, then `/auth/callback` exchanges the authorization code for tokens.
- **Buyer / seller onboarding** — New users without a persona role are prompted once at `/onboarding` to choose buyer or seller. The choice is stored as a Keycloak realm role.
- **Session cookies** — After login, a signed `session` cookie identifies the user. Tokens are kept in an in-memory session store (suitable for local development only).
- **Protected routes** — `/protected` requires authentication and onboarding. `/buyer` and `/seller` require the matching persona role.
- **Bearer token support** — Protected routes also accept a JWT in the `Authorization: Bearer` header.
- **Logout** — `/logout` clears the local session and redirects to Keycloak's end-session endpoint.

The `dev` realm, OAuth clients, realm roles, and admin service account are imported automatically when Keycloak starts via `keycloak/import/dev-realm.json`.

Self registration has also been enabled, therefore, it is possible to click the Register button on the login page and create new users.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose, **or**
- Python 3.12+ and a running Keycloak instance

## Run locally with Docker Compose

This is the recommended way to run the stack.

1. Clone the repository and start the services:

```bash
docker compose up --build
```

2. Wait for the services to be ready:
   - **App:** http://localhost:8000
   - **Keycloak:** http://localhost:8080
   - **Mailpit** (local email inbox): http://localhost:8025

3. Try the flow:
   - Open http://localhost:8000/login — you will be redirected to Keycloak.
   - **Register** a new account (or sign in if you already have one).
   - After login, choose **Buyer** or **Seller** on the onboarding page.
   - Visit http://localhost:8000/ — you should see your username and assigned role.
   - Visit http://localhost:8000/protected — any onboarded user can access this page.
   - Visit http://localhost:8000/buyer or http://localhost:8000/seller — only users with the matching role can access each page.
   - Visit http://localhost:8000/logout to sign out.

### Buyer / seller onboarding

After a user registers or logs in for the first time, if they have neither the `buyer` nor `seller` realm role, the app shows a one-time onboarding page. When they choose a persona:

1. The FastAPI backend obtains a service-account token from the `fastapi-admin` Keycloak client.
2. It assigns the chosen realm role to the user via the Keycloak Admin API.
3. It refreshes the user's session access token so `buyer` or `seller` appears in JWT claims immediately.
4. The user is redirected home and is not prompted again.

Realm roles are defined in `keycloak/import/dev-realm.json`:

- `buyer` — buyer persona
- `seller` — seller persona

The `fastapi-admin` client is a confidential service account used only by the backend (not for browser login). It is granted `view-users`, `query-users`, `manage-users`, and `view-realm` on the `realm-management` client so the app can look up users, read realm roles, and assign them.

If you change realm roles or the admin client in `dev-realm.json`, re-import the realm:

```bash
docker compose down -v
docker compose up --build
```

### Keycloak admin console

- URL: http://localhost:8080/admin
- Username: `admin`
- Password: `admin`

### Email verification (Mailpit)

The `dev` realm is configured with `verifyEmail: true` and SMTP pointing at [Mailpit](https://mailpit.axllent.org/), a local mail catcher. When a user registers or needs to verify their email, Keycloak sends the message to Mailpit instead of the real internet.

**How to verify a new user:**

1. Register at http://localhost:8000/login → **Register**, or use Keycloak's registration page.
2. Open the Mailpit inbox at http://localhost:8025.
3. Open the **Verify email** message and click the link inside.
4. In the Keycloak admin console, the user's **Email verified** flag should now be **On**.

**Existing users** who registered before verification was enabled will not receive a retroactive email. In the admin console, open the user → **Action** → **Send verification email**, or toggle **Email verified** manually for local testing.

If you change `dev-realm.json` (for example SMTP or `verifyEmail`) after Keycloak has already imported the realm, reset the volume so settings are re-imported:

```bash
docker compose down -v
docker compose up --build
```

### Google sign-in (optional)

Google login is configured in **Keycloak**, not in the FastAPI app. It can run **side by side** with username/password — users pick either option on the Keycloak login page when they visit `/login`. The existing OAuth flow (`/login` → `/auth/callback`) does not need to change.

**Option A — edit the realm import file**

`keycloak/import/dev-realm.json` includes a Google identity provider under `identityProviders` with placeholders. Replace `YOUR_GOOGLE_CLIENT_ID` and `YOUR_GOOGLE_CLIENT_SECRET` with credentials from the [Google Cloud Console](https://console.cloud.google.com/), then re-import the realm:

```bash
docker compose down -v
docker compose up --build
```

**Option B — use the Keycloak admin console**

1. Open http://localhost:8080/admin → **dev** realm → **Identity providers** → **Google**.
2. Enter your Google **Client ID** and **Client secret**.
3. Save.

**Google Cloud redirect URI** (required for either option — points to Keycloak, not the FastAPI app):

```
http://localhost:8080/realms/dev/broker/google/endpoint
```

## Run locally without Docker

You need Keycloak running separately (for example on port 8080) with the `dev` realm imported. Then run the FastAPI app on your machine.

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Optionally create a `.env` file to override defaults (see [Configuration](#configuration)). With Keycloak on localhost, the defaults usually work without changes.

3. Start the app:

```bash
uvicorn app.server:app --reload --host 0.0.0.0 --port 8000
```

4. Open http://localhost:8000/login, register or sign in, and complete onboarding.

## API endpoints

| Method | Path                 | Description                                      |
|--------|----------------------|--------------------------------------------------|
| GET    | `/`                  | Home page (shows user info when logged in)       |
| GET    | `/login`             | Start OAuth login (redirects to Keycloak)        |
| GET    | `/auth/callback`     | OAuth callback (handled by Keycloak redirect)    |
| GET    | `/logout`            | Clear session and log out via Keycloak           |
| GET    | `/onboarding`        | One-time buyer/seller choice (auth required)     |
| POST   | `/onboarding/role`   | Assign persona role and refresh session token    |
| GET    | `/protected`         | Requires auth and onboarding (any persona)       |
| GET    | `/buyer`             | Requires `buyer` role                            |
| GET    | `/seller`            | Requires `seller` role                           |

## Saving Resources

When saving resources, they are associated with certain users and typically this would be done with the use of an ID. Here, since Keycloak owns identity, we can use the `sub` (subject) from the JWT access token.

This ID is displayed along with the username when a user navigates to the `/protected` endpoint. 

## Configuration

Settings are loaded from environment variables and an optional `.env` file. Nested settings use a double underscore (`__`) delimiter.

| Variable                         | Default                          | Description |
|----------------------------------|----------------------------------|-------------|
| `KEYCLOAK__URL`                  | `http://localhost:8080`          | Keycloak URL for Admin API and JWKS (internal Docker hostname in Compose) |
| `KEYCLOAK__PUBLIC_URL`           | (same as `KEYCLOAK__URL`)        | Keycloak URL for browser redirects and user token grants (code exchange, refresh) |
| `KEYCLOAK__REALM`                | `dev`                            | Keycloak realm name |
| `KEYCLOAK__CLIENT_ID`            | `fastapi-server`                 | OAuth client ID |
| `KEYCLOAK__CLIENT_SECRET`        | (empty)                          | Client secret (not required for the public client) |
| `KEYCLOAK__ADMIN_CLIENT_ID`      | `fastapi-admin`                  | Service account client for Admin API role assignment |
| `KEYCLOAK__ADMIN_CLIENT_SECRET`  | `dev-admin-secret-change-me`     | Secret for the admin service account client |
| `KEYCLOAK__REDIRECT_URI`         | `http://localhost:8000/auth/callback` | OAuth redirect URI |
| `KEYCLOAK__POST_LOGOUT_REDIRECT_URI` | `http://localhost:8000/`     | URL after Keycloak logout |
| `KEYCLOAK__SCOPE`                | `openid profile email`           | OAuth scopes |
| `SESSION_SECRET_KEY`             | `dev-only-change-me`             | Secret for signing session cookies |
| `COOKIE_SECURE`                  | `false`                          | Set to `true` when serving over HTTPS |

When running with Docker Compose, `KEYCLOAK__URL` is set to `http://keycloak:8080` (internal network) and `KEYCLOAK__PUBLIC_URL` to `http://localhost:8080` (browser-accessible). User token calls (authorization code exchange and refresh) use `PUBLIC_URL` so the request URL matches the token issuer. The app service maps `localhost` to the host via `extra_hosts` so those calls work from inside the container.

## Project structure

```
app/
  server.py          # FastAPI routes, templates, onboarding
  settings.py        # Environment-based configuration
  templates/         # Jinja2 HTML templates
  static/            # Shared CSS
  auth/
    keycloak.py      # PKCE, token exchange, JWT verification
    keycloak_admin.py # Keycloak Admin API (role assignment, token refresh)
    onboarding.py    # Buyer/seller persona helpers
    session.py       # In-memory session store and signed cookies
    deps.py          # FastAPI dependencies (auth, onboarding, roles)
keycloak/import/
  dev-realm.json     # Realm, clients, roles, Mailpit SMTP, Google IdP (optional)
docker-compose.yml   # Keycloak, Mailpit, and app services
Dockerfile           # FastAPI app image
```
