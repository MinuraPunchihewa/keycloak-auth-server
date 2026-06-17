# Keycloak Auth Server

A FastAPI application that demonstrates OpenID Connect authentication with [Keycloak](https://www.keycloak.org/). It implements the authorization code flow with PKCE, stores tokens in a server-side session, and protects routes by validating JWT access tokens against Keycloak's JWKS endpoint.

## What it does

- **Login via Keycloak** — `/login` redirects the browser to Keycloak, then `/auth/callback` exchanges the authorization code for tokens.
- **Session cookies** — After login, a signed `session` cookie identifies the user. Tokens are kept in an in-memory session store (suitable for local development only).
- **Protected routes** — `/protected` requires authentication and returns the logged-in username.
- **Bearer token support** — Protected routes also accept a JWT in the `Authorization: Bearer` header.
- **Logout** — `/logout` clears the local session and redirects to Keycloak's end-session endpoint.

The `dev` realm, OAuth client, and a demo user are imported automatically when Keycloak starts via `keycloak/import/dev-realm.json`.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose, **or**
- Python 3.12+ and a running Keycloak instance

## Run locally with Docker Compose

This is the recommended way to run the stack.

1. Clone the repository and start the services:

```bash
docker compose up --build
```

2. Wait for both services to be ready:
   - **App:** http://localhost:8000
   - **Keycloak:** http://localhost:8080

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
  dev-realm.json     # Pre-configured realm, client, and demo user
docker-compose.yml   # Keycloak + app services
Dockerfile           # FastAPI app image
```
