import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app


@pytest.fixture
def client():
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


def test_auth_trims_username(client):
    response = client.post("/auth", json={"username": "  Mira  "})

    assert response.status_code == 200
    assert response.json()["username"] == "Mira"


def test_auth_creates_user_with_open_inbox(client):
    response = client.post("/auth", json={"username": "Mira"})

    assert response.json()["accepting_messages"] is True


def test_auth_creates_user_with_id(client):
    response = client.post("/auth", json={"username": "Mira"})

    assert response.json()["id"]


def test_auth_returns_existing_user_instead_of_creating_duplicate(client):
    first = client.post("/auth", json={"username": "Mira"}).json()
    second = client.post("/auth", json={"username": "Mira"}).json()

    assert second == first


@pytest.mark.parametrize("username", ["", " ", "   "])
def test_auth_rejects_blank_usernames(client, username):
    response = client.post("/auth", json={"username": username})

    assert response.status_code == 400
    assert response.json()["detail"] == "Username cannot be blank."


def test_auth_requires_username(client):
    assert client.post("/auth", json={}).status_code == 422


def test_get_user_returns_account_details(client):
    user = client.post("/auth", json={"username": "Mira"}).json()

    response = client.get(f"/users/{user['id']}")

    assert response.status_code == 200
    assert response.json() == user


def test_get_user_returns_404_for_unknown_id(client):
    response = client.get("/users/not-a-user")

    assert response.status_code == 404
    assert response.json()["detail"] == "Requested user account does not exist."


@pytest.mark.parametrize("accepting", [False, True])
def test_settings_update_accepting_messages(client, accepting):
    user = client.post("/auth", json={"username": "Mira"}).json()

    response = client.patch(
        f"/users/{user['id']}/settings",
        json={"accepting_messages": accepting},
    )

    assert response.status_code == 200
    assert response.json()["accepting_messages"] is accepting
    assert client.get(f"/users/{user['id']}").json()["accepting_messages"] is accepting


def test_settings_for_unknown_user_returns_404(client):
    response = client.patch(
        "/users/not-a-user/settings",
        json={"accepting_messages": False},
    )

    assert response.status_code == 404


def test_settings_requires_boolean_value(client):
    user = client.post("/auth", json={"username": "Mira"}).json()

    assert client.patch(
        f"/users/{user['id']}/settings",
        json={"accepting_messages": "not-a-boolean"},
    ).status_code == 422
