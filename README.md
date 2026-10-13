# Secret Inbox

Secret Inbox is a small web application for collecting anonymous feedback.
Inbox owners can share a link, read and organize incoming messages, react to
them, and optionally reply. Senders can use a private follow-up link to see a
reaction or written reply. Optional AI features summarize an inbox or draft a
reply using a local Ollama model.

This repository contains three independently run development services:

| Component | Technology | Local address | Source |
| --- | --- | --- | --- |
| Web client | React, TypeScript, Vite, Tailwind CSS | `http://localhost:5173` | [`frontend/`](./frontend/) |
| User API | FastAPI, SQLAlchemy, SQLite | `http://localhost:8001` | [`user-service/`](./user-service/) |
| Message API | FastAPI, SQLAlchemy, SQLite | `http://localhost:8002` | [`message-service/`](./message-service/) |

## Requirements

- Python 3.9 or later
- Node.js 20.19+ or 22.12+ and npm (developed with Node.js 26 and npm 11)
- Ollama with the `llama3.2:3b` model for AI summaries and reply suggestions
  (optional; the rest of the app works without Ollama)

The backend runtime dependencies are listed in [`requirements.txt`](./requirements.txt);
test dependencies are listed in [`requirements-dev.txt`](./requirements-dev.txt).
Owner accounts use a username and a password of at least 12 characters.
Anonymous senders still use the shared invite link.

## Set up

From the project root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cd frontend
npm ci
```

If the virtual environment already exists, install into it rather than
recreating it.

## Run locally

Start each process in a separate terminal from the project root:

The project reads the local signing secret from `.env.local` automatically. If
you need to create or replace it, generate one from the project root and keep
the file private:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > .env.local
chmod 600 .env.local
```

```sh
cd frontend
npm run dev -- --host 127.0.0.1
```

```sh
cd user-service
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

```sh
cd message-service
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```

Open `http://127.0.0.1:5173`. The APIs expose interactive Swagger
documentation at `http://127.0.0.1:8001/docs` and
`http://127.0.0.1:8002/docs`.

The services use SQLite files in their respective working directories:
`user-service/user.db` and `message-service/message.db`. Run Uvicorn from the
matching service directory so it opens the expected database. The checked-in
databases are local development data; tests never use them.

Accounts created by older versions do not have a password. They cannot be
claimed through public registration; set a password locally before using one
of those accounts with this version. With the user service stopped, run
`../.venv/bin/python set_legacy_password.py` from `user-service` and follow the
prompts. This only upgrades an existing account that has no password yet.

Owner APIs require a signed bearer token. Keep this setup on the local machine;
this development configuration is not intended for public exposure. Invite
and reply-check links are bearer links intended to be shared with senders.

To enable AI features, install/start Ollama and make sure the configured model
is available:

```sh
ollama pull llama3.2:3b
ollama serve
```

The message service calls Ollama at `http://localhost:11434/api/generate`.
AI requests use a 120-second client timeout. If Ollama is unavailable or the
model returns an empty response, the API reports an error; AI failure does not
prevent sending, reading, or managing messages.

## Application flows

1. The client registers or signs in with a username and password. The user
   service returns a short-lived signed access token for owner-only requests.
2. The dashboard loads account settings and the existing shared invite, if
   there is one, and polls the current inbox every three seconds.
3. The owner generates one shared invite link for the inbox and sends it to
   the people they want to hear from. Generating another link invalidates the
   previous one; the active link remains valid for multiple anonymous
   submissions while the inbox stays open.
4. The invited sender opens `/?route=feedback&invite=<invite-token>` and can
   submit one message of up to 500 characters. The service consumes the invite
   when it accepts the message and returns a private reply-check token.
5. The sender can open `/?route=check&token=<reply-token>` to view their
   message and poll for the owner's reaction or written reply every five
   seconds.
6. The dashboard can archive, restore, report, delete, react to, or reply to
   messages, or permanently delete the account and its associated messages and
   invite links. AI summary and reply suggestions are optional Ollama-backed
   operations.

## API overview

Request and response examples use JSON. FastAPI Swagger at each service's
`/docs` endpoint includes the live schemas.

### User service (`:8001`)

| Method and path | Purpose | Request body |
| --- | --- | --- |
| `POST /auth/register` | Create an account | `{"username":"mira","password":"12+ characters"}` |
| `POST /auth/login` | Sign in to an existing account | `{"username":"mira","password":"12+ characters"}` |
| `GET /users/{user_id}` | Read the authenticated owner's username and inbox setting | — |
| `GET /users/{user_id}/status` | Publicly check if the inbox accepts messages | — |
| `PATCH /users/{user_id}/settings` | Pause or resume incoming messages (owner token required) | `{"accepting_messages":false}` |
| `DELETE /users/{user_id}` | Delete the authenticated owner's account and associated inbox data | — |

Registration and login responses contain `id`, `username`,
`accepting_messages`, and `access_token`. Protected owner endpoints require
`Authorization: Bearer <access_token>`. Passwords are stored as salted
PBKDF2 hashes, not plaintext. Account deletion removes the owner's messages
and invite links first; if that cleanup service is unavailable, deletion fails
and the account remains in place so the request can be safely retried.

### Message service (`:8002`)

| Method and path | Purpose | Request body |
| --- | --- | --- |
| `GET /invites/{user_id}` | Restore the authenticated owner's existing shared invite, if any | — |
| `POST /invites/{user_id}` | Create a shared invite link for an accepting inbox | — |
| `POST /invites/{user_id}/batch` | Legacy helper for creating 1-50 distinct invites at once | `{"count":3}` |
| `POST /messages/invite/{invite_token}` | Consume an invite and submit anonymous feedback; returns a private `reply_token` | `{"content":"A note","category":"Compliment"}` |
| `GET /messages/token/{token}` | Read the sender's message, reaction, and written reply | — |
| `GET /messages/{user_id}?status=active` | List inbox messages; `status` is `active`, `archived`, or `reported` | — |
| `PATCH /messages/{message_id}/reaction` | Set the owner's reaction | `{"reaction":"❤️"}` |
| `PATCH /messages/{message_id}/reply` | Save a written reply | `{"reply":"Thank you!"}` |
| `PATCH /messages/{message_id}/archive` | Archive a message | — |
| `PATCH /messages/{message_id}/restore` | Return a message to the active inbox | — |
| `PATCH /messages/{message_id}/report` | Report a message with an optional reason | `{"reason":"Spam"}` |
| `DELETE /messages/{message_id}` | Permanently delete a message | — |
| `POST /messages/{user_id}/summarize` | Generate a summary of active messages | — |
| `POST /messages/{message_id}/suggest-reply` | Generate a suggested reply draft | — |

Invite creation, inbox reads, message changes, and AI dashboard operations
require the owner's bearer token. Invite creation rejects unknown recipients
and paused inboxes with `400`.
Anonymous submission rejects invalid or already-used invites, blank content,
content longer than 500 characters, unknown recipients, and paused inboxes
with `400`. Invalid or missing message IDs generally return `404` (reply
validation errors return `400`). The private token endpoint intentionally
omits the recipient's user ID.

## Tests and quality checks

The suites are separated by test level:

- **Frontend component/integration tests** render React screens, exercise
  user interactions, and mock network calls.
- **Backend unit tests** test user, message, and AI service behavior in
  isolation. HTTP calls to other services and Ollama are mocked.
- **Backend API integration tests** call FastAPI endpoints using in-memory
  SQLite databases. The message API tests stub the user-service and AI
  boundaries rather than requiring those servers to run.

Run the frontend checks:

```sh
cd frontend
npm test
npm run build
npm run lint
```

Install Python test dependencies from the project root:

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run the user-service unit and API tests:

```sh
(cd user-service && PYTHONPATH=.. ../.venv/bin/python -m pytest -q tests)
```

Run message-service and AI unit plus API tests:

```sh
(cd message-service && PYTHONPATH=.. ../.venv/bin/python -m pytest -q tests)
```

Frontend tests are under [`frontend/src/`](./frontend/src/); isolated service
tests and API tests are under each service's `tests/` directory.

## Development notes and limitations

- The frontend calls the local APIs directly at `localhost:8001` and
  `localhost:8002`.
- SQLite paths are relative to each backend process's current working
  directory.
- Owner APIs require password-backed accounts and signed tokens. The
  authentication secret must be at least 32 characters and identical in both
  API services. CORS is permissive; this app is configured for local
  development only, not public hosting. There is no password-reset or
  authentication rate-limiting flow.
- Lightweight database migrations run at service startup. There is no separate
  migration-management tool.
- Frontend implementation notes and scripts are documented in
  [`frontend/README.md`](./frontend/README.md).
