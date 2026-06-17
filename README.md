# Keycloak Auth Server

A FastAPI application that demonstrates OpenID Connect authentication with [Keycloak](https://www.keycloak.org/). It implements the authorization code flow with PKCE, stores tokens in a server-side session, and protects routes by validating JWT access tokens against Keycloak's JWKS endpoint.

## How OAuth works

[OAuth 2.0](https://oauth.net/2/) is a standard for **delegated authorization**: an app can access resources on a user's behalf without handling their password. [OpenID Connect (OIDC)](https://openid.net/connect/) builds on OAuth and adds identity — who the user is — via an ID token and standard claims in the access token.

This project uses the **authorization code flow with PKCE**, which is the recommended approach for web apps. Keycloak acts as the **authorization server**; the FastAPI app is the **client**; protected API routes are the **resource server**.

### Roles

| Role | In this project |
|------|-----------------|
| **Resource owner** | The person signing in (e.g. `alice`) |
| **Client** | The FastAPI app (`fastapi-server`) |
| **Authorization server** | Keycloak (issues tokens after login) |
| **Resource server** | The FastAPI app again (validates tokens on `/protected`) |

### Login flow (step by step)

1. **User starts login** — The browser visits `/login`. The app creates a session, generates a random `state` value and a PKCE `code_verifier`, and stores them server-side.

2. **Redirect to Keycloak** — The app redirects the browser to Keycloak's authorization endpoint with parameters such as `client_id`, `redirect_uri`, `scope`, `state`, and `code_challenge` (a hash of the verifier). The user never sees the PKCE verifier; only the challenge is sent in the URL.

3. **User authenticates** — Keycloak shows a login page. The user enters credentials (e.g. `alice` / `alice`). Keycloak validates them; the app never receives the password.

4. **Authorization grant** — If login succeeds, Keycloak redirects the browser back to `/auth/callback` with a short-lived **authorization code** and the same `state` value.

5. **Verify state** — The app compares the returned `state` with the value stored in the session. This prevents CSRF attacks where a malicious site tries to complete a login with someone else's code.

6. **Exchange code for tokens** — The app sends a server-to-server POST to Keycloak's token endpoint with the authorization code, `client_id`, `redirect_uri`, and the original `code_verifier`. Keycloak checks that the verifier matches the earlier `code_challenge`, then returns tokens.

7. **Store tokens** — The app saves the **access token**, **refresh token**, and **ID token** in the server-side session and sets a signed `session` cookie on the browser. The tokens themselves stay on the server; the cookie is only an opaque session reference.

8. **Redirect home** — The browser is sent to `/`. The user is now logged in.

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
- **Session cookies** — After login, a signed `session` cookie identifies the user. Tokens are kept in an in-memory session store (suitable for local development only).
- **Protected routes** — `/protected` requires authentication and returns the logged-in username.
- **Bearer token support** — Protected routes also accept a JWT in the `Authorization: Bearer` header.
- **Logout** — `/logout` clears the local session and redirects to Keycloak's end-session endpoint.

The `dev` realm, OAuth client, and a demo user are imported automatically when Keycloak starts via `keycloak/import/dev-realm.json`.

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
   - Sign in with the demo user (see below).
   - Visit http://localhost:8000/protected — you should see a greeting with your username.
   - Visit http://localhost:8000/logout to sign out.

### Demo user

The demo user is not created by the FastAPI app. It is defined in `keycloak/import/dev-realm.json` and provisioned by Keycloak on startup.

When you run `docker compose up`, the Keycloak service:

1. Starts with `--import-realm`, which tells Keycloak to import JSON realm files from `/opt/keycloak/data/import`.
2. Mounts `./keycloak/import` into that directory (see `docker-compose.yml`).
3. Reads `dev-realm.json`, which creates the `dev` realm, the `fastapi-server` OAuth client, and the `alice` user in one step.

The user entry in the realm file looks like this:

```json
{
  "username": "alice",
  "enabled": true,
  "emailVerified": true,
  "firstName": "Alice",
  "lastName": "Demo",
  "email": "alice@example.com",
  "credentials": [
    {
      "type": "password",
      "value": "alice",
      "temporary": false
    }
  ]
}
```

Because `temporary` is `false`, no password change is required on first login. The realm also sets `loginWithEmailAllowed: true`, so you can sign in with either the username or email address.

Import runs on first startup when the realm does not already exist. If you change `dev-realm.json` after Keycloak has created the realm, delete the `keycloak_data` Docker volume and restart so Keycloak re-imports:

```bash
docker compose down -v
docker compose up --build
```

To add or change users without editing the JSON file, use the Keycloak admin console (see below) under **Users** in the `dev` realm.

| Field    | Value               |
|----------|---------------------|
| Username | `alice`             |
| Password | `alice`             |
| Email    | `alice@example.com` |

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

4. Open http://localhost:8000/login and sign in with the demo user.

## API endpoints

| Method | Path             | Description                                      |
|--------|------------------|--------------------------------------------------|
| GET    | `/`              | Public hello endpoint                            |
| GET    | `/login`         | Start OAuth login (redirects to Keycloak)        |
| GET    | `/auth/callback` | OAuth callback (handled by Keycloak redirect)    |
| GET    | `/logout`        | Clear session and log out via Keycloak           |
| GET    | `/protected`     | Requires authentication (cookie or Bearer token) |

## Saving Resources

When saving resources, they are associated with certain users and typically this would be done with the use of an ID. Here, since Keycloak owns identity, we can use the `sub` (subject) from the JWT access token.

This ID is displayed along with the username when a user navigates to the `/protected` endpoint. 

## Configuration

Settings are loaded from environment variables and an optional `.env` file. Nested settings use a double underscore (`__`) delimiter.

| Variable                         | Default                          | Description |
|----------------------------------|----------------------------------|-------------|
| `KEYCLOAK__URL`                  | `http://localhost:8080`          | Keycloak URL used by the app for token exchange and JWKS |
| `KEYCLOAK__PUBLIC_URL`           | (same as `KEYCLOAK__URL`)        | Keycloak URL used in browser redirects |
| `KEYCLOAK__REALM`                | `dev`                            | Keycloak realm name |
| `KEYCLOAK__CLIENT_ID`            | `fastapi-server`                 | OAuth client ID |
| `KEYCLOAK__CLIENT_SECRET`        | (empty)                          | Client secret (not required for the public client) |
| `KEYCLOAK__REDIRECT_URI`         | `http://localhost:8000/auth/callback` | OAuth redirect URI |
| `KEYCLOAK__POST_LOGOUT_REDIRECT_URI` | `http://localhost:8000/`     | URL after Keycloak logout |
| `KEYCLOAK__SCOPE`                | `openid profile email`           | OAuth scopes |
| `SESSION_SECRET_KEY`             | `dev-only-change-me`             | Secret for signing session cookies |
| `COOKIE_SECURE`                  | `false`                          | Set to `true` when serving over HTTPS |

When running with Docker Compose, `KEYCLOAK__URL` is set to `http://keycloak:8080` (internal network) and `KEYCLOAK__PUBLIC_URL` to `http://localhost:8080` (browser-accessible).

## Project structure

```
app/
  server.py          # FastAPI routes (login, callback, logout, protected)
  settings.py        # Environment-based configuration
  auth/
    keycloak.py      # PKCE, token exchange, JWT verification
    session.py       # In-memory session store and signed cookies
    deps.py          # FastAPI dependencies (get_current_user, require_role)
keycloak/import/
  dev-realm.json     # Realm, client, demo user, Mailpit SMTP, Google IdP (optional)
docker-compose.yml   # Keycloak, Mailpit, and app services
Dockerfile           # FastAPI app image
```
