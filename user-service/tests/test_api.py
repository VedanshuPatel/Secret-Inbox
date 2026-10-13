import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from shared_auth import create_access_token


def create_account(client, username="Mira", password="correct horse battery"):
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SECRET_INBOX_AUTH_SECRET", "test-secret-key-that-is-at-least-32-characters")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_auth_registers_and_trims_username(client):
    response = client.post("/auth/register", json={"username": "  Mira  ", "password": "correct horse battery"})

    assert response.status_code == 201
    assert response.json()["username"] == "Mira"
    assert response.json()["accepting_messages"] is True
    assert response.json()["access_token"]


def test_auth_rejects_duplicate_username(client):
    create_account(client)

    response = client.post("/auth/register", json={"username": "Mira", "password": "correct horse battery"})

    assert response.status_code == 400
    assert response.json()["detail"] == "An account with this username already exists."


def test_auth_login_checks_password(client):
    first = create_account(client)
    response = client.post("/auth/login", json={"username": "Mira", "password": "correct horse battery"})

    assert response.status_code == 200
    assert response.json()["id"] == first["id"]
    assert response.json()["access_token"]


def test_auth_login_rejects_wrong_password(client):
    create_account(client)

    response = client.post("/auth/login", json={"username": "Mira", "password": "wrong password"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."


def test_auth_requires_password(client):
    assert client.post("/auth/register", json={"username": "Mira"}).status_code == 422


def test_auth_requires_minimum_password_length(client):
    response = client.post("/auth/register", json={"username": "Mira", "password": "short"})

    assert response.status_code == 422


def test_get_user_requires_authentication(client):
    user = create_account(client)

    response = client.get(f"/users/{user['id']}")

    assert response.status_code == 401


def test_get_user_returns_account_to_authenticated_owner(client):
    user = create_account(client)

    response = client.get(f"/users/{user['id']}", headers=auth_headers(user["id"]))

    assert response.status_code == 200
    assert response.json() == {
        "id": user["id"],
        "username": "Mira",
        "accepting_messages": True,
    }


def test_get_user_rejects_another_owner(client):
    user = create_account(client)

    response = client.get(f"/users/{user['id']}", headers=auth_headers("someone-else"))

    assert response.status_code == 403


def test_public_status_does_not_return_account_details(client):
    user = create_account(client)

    response = client.get(f"/users/{user['id']}/status")

    assert response.status_code == 200
    assert response.json() == {"accepting_messages": True}


def test_settings_update_requires_owner_authentication(client):
    user = create_account(client)

    response = client.patch(
        f"/users/{user['id']}/settings",
        json={"accepting_messages": False},
        headers=auth_headers("someone-else"),
    )

    assert response.status_code == 403


def test_settings_update_accepting_messages(client):
    user = create_account(client)

    response = client.patch(
        f"/users/{user['id']}/settings",
        json={"accepting_messages": False},
        headers=auth_headers(user["id"]),
    )

    assert response.status_code == 200
    assert response.json()["accepting_messages"] is False
    assert client.get(f"/users/{user['id']}/status").json()["accepting_messages"] is False


def test_delete_user_removes_account_and_requests_message_data_cleanup(client, monkeypatch):
    user = create_account(client)
    request_data = {}

    def delete(url, *, headers, timeout):
        request_data.update(url=url, headers=headers, timeout=timeout)
        return httpx.Response(204)

    monkeypatch.setattr("main.httpx.delete", delete)
    response = client.delete(f"/users/{user['id']}", headers=auth_headers(user["id"]))

    assert response.status_code == 204
    assert request_data["url"] == f"http://localhost:8002/accounts/{user['id']}/data"
    assert request_data["headers"] == auth_headers(user["id"])
    assert client.get(
        f"/users/{user['id']}",
        headers=auth_headers(user["id"]),
    ).status_code == 404


def test_delete_user_keeps_account_if_message_data_cleanup_fails(client, monkeypatch):
    user = create_account(client)

    def fail_delete(*_args, **_kwargs):
        raise httpx.ConnectError("message API unavailable")

    monkeypatch.setattr("main.httpx.delete", fail_delete)
    response = client.delete(f"/users/{user['id']}", headers=auth_headers(user["id"]))

    assert response.status_code == 503
    assert client.get(
        f"/users/{user['id']}",
        headers=auth_headers(user["id"]),
    ).status_code == 200


def test_delete_user_requires_owner_authentication(client):
    user = create_account(client)

    response = client.delete(f"/users/{user['id']}")

    assert response.status_code == 401


def test_delete_user_rejects_another_owner(client, monkeypatch):
    user = create_account(client)
    cleanup_called = False

    def delete(*_args, **_kwargs):
        nonlocal cleanup_called
        cleanup_called = True
        return httpx.Response(204)

    monkeypatch.setattr("main.httpx.delete", delete)
    response = client.delete(
        f"/users/{user['id']}",
        headers=auth_headers("someone-else"),
    )

    assert response.status_code == 403
    assert cleanup_called is False
