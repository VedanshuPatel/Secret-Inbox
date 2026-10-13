import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import AIService, MessageService, app


@pytest.fixture
def client(monkeypatch):
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

    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_invite(client, user_id="owner-1"):
    response = client.post(f"/invites/{user_id}")
    assert response.status_code == 201, response.text
    return response.json()["invite_token"]


def create_message(client, *, content="Hello there", user_id="owner-1", category="Advice"):
    invite_token = create_invite(client, user_id)
    response = client.post(
        f"/messages/invite/{invite_token}",
        json={"content": content, "category": category},
    )
    assert response.status_code == 200, response.text
    return response


def test_submit_returns_success_status(client):
    response = create_message(client)

    assert response.json()["status"] == "success"


def test_submit_returns_private_reply_token(client):
    response = create_message(client)

    assert response.json()["reply_token"]


def test_invite_creation_returns_unique_tokens(client):
    first = client.post("/invites/owner-1")
    second = client.post("/invites/owner-1")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["invite_token"]
    assert first.json()["invite_token"] != second.json()["invite_token"]


def test_invite_creation_rejects_paused_inbox(client, monkeypatch):
    async def paused_user(_user_id):
        return True, False

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(paused_user))

    response = client.post("/invites/owner-1")

    assert response.status_code == 400
    assert response.json()["detail"] == "This inbox is not currently accepting messages."


def test_invite_batch_returns_one_unique_token_per_requested_invite(client):
    response = client.post("/invites/owner-1/batch", json={"count": 3})

    tokens = response.json()["invite_tokens"]
    assert response.status_code == 201
    assert len(tokens) == 3
    assert len(set(tokens)) == 3


def test_invite_batch_rejects_count_above_limit(client):
    response = client.post("/invites/owner-1/batch", json={"count": 51})

    assert response.status_code == 422


def test_submit_trims_message_content(client):
    token = create_message(client, content="  Hello there  ").json()["reply_token"]

    response = client.get(f"/messages/token/{token}")

    assert response.json()["content"] == "Hello there"


@pytest.mark.parametrize("content", ["", " ", "   "])
def test_submit_rejects_blank_content(client, content):
    invite_token = create_invite(client)
    response = client.post(f"/messages/invite/{invite_token}", json={"content": content})

    assert response.status_code == 400
    assert response.json()["detail"] == "Message content cannot be blank."


def test_submit_rejects_content_over_500_characters(client):
    invite_token = create_invite(client)
    response = client.post(f"/messages/invite/{invite_token}", json={"content": "x" * 501})

    assert response.status_code == 400
    assert response.json()["detail"] == "Message exceeds the 500 character limit."


def test_submit_accepts_exactly_500_characters(client):
    response = create_message(client, content="x" * 500)

    assert response.status_code == 200


def test_shared_invite_can_be_used_multiple_times(client):
    invite_token = create_invite(client)
    first = client.post(f"/messages/invite/{invite_token}", json={"content": "First note"})
    second = client.post(f"/messages/invite/{invite_token}", json={"content": "Second note"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reply_token"] != second.json()["reply_token"]


def test_message_submission_without_invite_is_not_allowed(client):
    response = client.post("/messages/owner-1", json={"content": "No invite"})

    assert response.status_code in (404, 405)


def test_submit_rejects_unknown_recipient(client, monkeypatch):
    invite_token = create_invite(client)

    async def unknown_user(_user_id):
        return False, False

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(unknown_user))
    response = client.post(f"/messages/invite/{invite_token}", json={"content": "Hello"})
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_submit_rejects_paused_recipient(client, monkeypatch):
    invite_token = create_invite(client)

    async def paused_user(_user_id):
        return True, False

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(paused_user))
    response = client.post(f"/messages/invite/{invite_token}", json={"content": "Hello"})
    assert response.status_code == 400
    assert "not currently accepting" in response.json()["detail"]


def test_submit_requires_content(client):
    invite_token = create_invite(client)

    assert client.post(f"/messages/invite/{invite_token}", json={}).status_code == 422


def test_inbox_filters_by_owner(client):
    create_message(client)

    active = client.get("/messages/owner-1?status=active")
    assert active.status_code == 200
    assert len(active.json()) == 1
    assert client.get("/messages/another-owner?status=active").json() == []


def test_inbox_rejects_invalid_status(client):
    response = client.get("/messages/owner-1?status=unknown")

    assert response.status_code == 400


def test_inbox_filters_by_status(client):
    create_message(client)
    message = client.get("/messages/owner-1?status=active").json()[0]
    client.patch(f"/messages/{message['id']}/archive")

    archived = client.get("/messages/owner-1?status=archived")

    assert len(archived.json()) == 1


def test_private_token_returns_saved_reaction(client):
    token = create_message(client).json()["reply_token"]
    message = client.get("/messages/owner-1?status=active").json()[0]
    client.patch(f"/messages/{message['id']}/reaction", json={"reaction": "❤️"})

    response = client.get(f"/messages/token/{token}")

    assert response.json()["reaction"] == "❤️"


def test_private_token_returns_saved_reply(client):
    token = create_message(client).json()["reply_token"]
    message = client.get("/messages/owner-1?status=active").json()[0]
    client.patch(f"/messages/{message['id']}/reply", json={"reply": "Thank you!"})

    response = client.get(f"/messages/token/{token}")

    assert response.json()["reply"] == "Thank you!"


def test_private_token_returns_reply_timestamp(client):
    token = create_message(client).json()["reply_token"]
    message = client.get("/messages/owner-1?status=active").json()[0]
    client.patch(f"/messages/{message['id']}/reply", json={"reply": "Thank you!"})

    response = client.get(f"/messages/token/{token}")

    assert response.json()["reply_at"]


def test_private_token_does_not_expose_recipient_identity(client):
    token = create_message(client).json()["reply_token"]

    response = client.get(f"/messages/token/{token}")

    assert "user_id" not in response.json()


def test_private_token_returns_original_content(client):
    token = create_message(client, content="A private note").json()["reply_token"]

    response = client.get(f"/messages/token/{token}")

    assert response.json()["content"] == "A private note"


def test_private_token_for_unknown_message_returns_404(client):
    response = client.get("/messages/token/invalid-token")

    assert response.status_code == 404
    assert response.json()["detail"] == "No message found for this link."


def test_reaction_can_be_set(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    response = client.patch(f"/messages/{message_id}/reaction", json={"reaction": "❤️"})

    assert response.json()["reaction"] == "❤️"


def test_reaction_can_be_changed(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]
    client.patch(f"/messages/{message_id}/reaction", json={"reaction": "❤️"})

    response = client.patch(f"/messages/{message_id}/reaction", json={"reaction": "🔥"})

    assert response.json()["reaction"] == "🔥"


def test_reaction_for_missing_message_returns_404(client):
    assert client.patch("/messages/999/reaction", json={"reaction": "❤️"}).status_code == 404


def test_reply_is_trimmed(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    response = client.patch(f"/messages/{message_id}/reply", json={"reply": "  Thank you  "})
    assert response.json()["reply"] == "Thank you"


def test_reply_rejects_blank_text(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    response = client.patch(f"/messages/{message_id}/reply", json={"reply": "  "})

    assert response.status_code == 400


def test_reply_rejects_missing_message(client):
    response = client.patch("/messages/999/reply", json={"reply": "Thanks"})

    assert response.status_code == 400


def test_archive_changes_message_status(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    archived = client.patch(f"/messages/{message_id}/archive")

    assert archived.json()["status"] == "archived"


def test_archived_message_is_removed_from_active_filter(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]
    client.patch(f"/messages/{message_id}/archive")

    active = client.get("/messages/owner-1?status=active")

    assert active.json() == []


def test_archived_message_appears_in_archived_filter(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]
    client.patch(f"/messages/{message_id}/archive")

    archived = client.get("/messages/owner-1?status=archived")

    assert len(archived.json()) == 1


def test_restore_changes_message_status(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]
    client.patch(f"/messages/{message_id}/archive")

    restored = client.patch(f"/messages/{message_id}/restore")

    assert restored.json()["status"] == "active"


def test_archive_missing_message_returns_404(client):
    assert client.patch("/messages/999/archive").status_code == 404


def test_restore_missing_message_returns_404(client):
    assert client.patch("/messages/999/restore").status_code == 404


def test_report_changes_status(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    response = client.patch(f"/messages/{message_id}/report", json={"reason": "Spam"})

    assert response.json()["status"] == "reported"


def test_report_trims_reason(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    response = client.patch(f"/messages/{message_id}/report", json={"reason": "  Spam  "})

    assert response.json()["report_reason"] == "Spam"


def test_report_accepts_empty_reason(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]
    response = client.patch(f"/messages/{message_id}/report", json={"reason": "  "})

    assert response.json()["report_reason"] is None


def test_report_missing_message_returns_404(client):
    assert client.patch("/messages/999/report", json={"reason": ""}).status_code == 404


def test_delete_returns_success_status(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    response = client.delete(f"/messages/{message_id}")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}


def test_delete_removes_message_from_inbox(client):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]
    client.delete(f"/messages/{message_id}")

    assert client.get("/messages/owner-1?status=active").json() == []


def test_delete_missing_message_returns_404(client):
    assert client.delete("/messages/999").status_code == 404


def test_summarize_returns_ai_summary(client, monkeypatch):
    create_message(client)

    async def summarize(messages):
        assert len(messages) == 1
        return "A kind note."

    monkeypatch.setattr(AIService, "summarize_inbox", staticmethod(summarize))
    response = client.post("/messages/owner-1/summarize")

    assert response.status_code == 200
    assert response.json()["summary"] == "A kind note."


def test_summarize_returns_message_count(client, monkeypatch):
    create_message(client)

    async def summarize(_messages):
        return "A kind note."

    monkeypatch.setattr(AIService, "summarize_inbox", staticmethod(summarize))

    response = client.post("/messages/owner-1/summarize")

    assert response.json()["message_count"] == 1


def test_summarize_rejects_empty_inbox(client):
    response = client.post("/messages/owner-1/summarize")

    assert response.status_code == 400


def test_summarize_reports_ai_unavailable(client, monkeypatch):
    create_message(client)
    async def unavailable(_messages):
        raise ValueError("AI service is unavailable.")

    monkeypatch.setattr(AIService, "summarize_inbox", staticmethod(unavailable))
    response = client.post("/messages/owner-1/summarize")
    assert response.status_code == 503


def test_suggest_reply_returns_suggestion(client, monkeypatch):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    async def suggest(message):
        return "Thanks for telling me!"

    monkeypatch.setattr(AIService, "suggest_reply", staticmethod(suggest))
    response = client.post(f"/messages/{message_id}/suggest-reply")

    assert response.status_code == 200
    assert response.json() == {"suggestion": "Thanks for telling me!"}


def test_suggest_reply_rejects_missing_message(client):
    assert client.post("/messages/999/suggest-reply").status_code == 404


def test_suggest_reply_reports_ai_unavailable(client, monkeypatch):
    create_message(client)
    message_id = client.get("/messages/owner-1?status=active").json()[0]["id"]

    async def unavailable(_message):
        raise ValueError("AI service is unavailable.")

    monkeypatch.setattr(AIService, "suggest_reply", staticmethod(unavailable))
    response = client.post(f"/messages/{message_id}/suggest-reply")

    assert response.status_code == 503
