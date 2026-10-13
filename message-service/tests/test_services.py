import asyncio
from datetime import datetime, timedelta

import pytest

from database import Invite, Message
from services import MessageService


def add_message(db_session, **overrides):
    values = {
        "user_id": "owner-1",
        "content": "A kind note",
        "status": "active",
        "category": None,
        "reaction": None,
        "reply": None,
        "reply_at": None,
        "report_reason": None,
        "reply_token": "private-token",
    }
    values.update(overrides)
    message = Message(**values)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


def add_invite(db_session, user_id="owner-1", token="invite-token"):
    invite = Invite(token=token, user_id=user_id)
    db_session.add(invite)
    db_session.commit()
    return invite


def test_get_user_inbox_filters_by_owner(db_session):
    add_message(db_session)
    add_message(db_session, user_id="owner-2", reply_token="other-owner-token")

    inbox = MessageService.get_user_inbox(db_session, "owner-1", "active")

    assert len(inbox) == 1


def test_get_user_inbox_filters_by_status(db_session):
    add_message(db_session)
    add_message(db_session, status="archived", reply_token="archived-token")

    inbox = MessageService.get_user_inbox(db_session, "owner-1", "archived")

    assert len(inbox) == 1
    assert inbox[0].status == "archived"


def test_get_user_inbox_orders_newest_first(db_session):
    now = datetime.utcnow()
    add_message(db_session, created_at=now - timedelta(days=1))
    add_message(db_session, reply_token="newest-token", created_at=now)

    inbox = MessageService.get_user_inbox(db_session, "owner-1", "active")

    assert inbox[0].reply_token == "newest-token"


def test_get_message_by_token_returns_matching_message(db_session):
    message = add_message(db_session)

    found = MessageService.get_message_by_token(db_session, "private-token")

    assert found.id == message.id


def test_get_message_by_token_rejects_unknown_token(db_session):
    with pytest.raises(ValueError, match="No message found for this link."):
        MessageService.get_message_by_token(db_session, "unknown")


def test_get_message_or_raise_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService._get_message_or_raise(db_session, 999)


def test_archive_message_marks_message_archived(db_session):
    message = add_message(db_session)

    archived = MessageService.archive_message(db_session, message.id)

    assert archived.status == "archived"


def test_archive_message_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService.archive_message(db_session, 999)


def test_restore_message_marks_message_active(db_session):
    message = add_message(db_session, status="archived")

    restored = MessageService.restore_message(db_session, message.id)

    assert restored.status == "active"


def test_restore_message_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService.restore_message(db_session, 999)


def test_delete_message_removes_record(db_session):
    message = add_message(db_session)

    MessageService.delete_message(db_session, message.id)

    assert db_session.query(Message).filter_by(id=message.id).first() is None


def test_delete_message_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService.delete_message(db_session, 999)


def test_set_reaction_persists_selected_reaction(db_session):
    message = add_message(db_session)

    updated = MessageService.set_reaction(db_session, message.id, "❤️")

    assert updated.reaction == "❤️"


def test_set_reaction_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService.set_reaction(db_session, 999, "❤️")


def test_set_reply_trims_reply(db_session):
    message = add_message(db_session)

    updated = MessageService.set_reply(db_session, message.id, "  Thank you!  ")

    assert updated.reply == "Thank you!"


def test_set_reply_sets_reply_timestamp(db_session):
    message = add_message(db_session)

    updated = MessageService.set_reply(db_session, message.id, "Thank you!")

    assert updated.reply_at is not None


def test_set_reply_rejects_blank_reply(db_session):
    message = add_message(db_session)

    with pytest.raises(ValueError, match="Reply cannot be blank."):
        MessageService.set_reply(db_session, message.id, "  ")


def test_set_reply_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService.set_reply(db_session, 999, "Thanks")


def test_report_message_sets_reported_status(db_session):
    message = add_message(db_session)

    updated = MessageService.report_message(db_session, message.id, "  Spam  ")

    assert updated.status == "reported"


def test_report_message_trims_reason(db_session):
    message = add_message(db_session)

    updated = MessageService.report_message(db_session, message.id, "  Spam  ")

    assert updated.report_reason == "Spam"


def test_report_message_stores_no_reason_for_blank_text(db_session):
    message = add_message(db_session)

    updated = MessageService.report_message(db_session, message.id, "  ")

    assert updated.report_reason is None


def test_report_message_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="Message not found."):
        MessageService.report_message(db_session, 999, "Spam")


def test_create_message_rejects_blank_content(db_session, monkeypatch):
    async def should_not_check_user(_user_id):
        pytest.fail("User should not be checked for invalid message content")

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(should_not_check_user))

    with pytest.raises(ValueError, match="Message content cannot be blank."):
        asyncio.run(MessageService.create_anonymous_message(db_session, "owner-1", "  ", None))


def test_create_message_rejects_content_over_500_characters(db_session, monkeypatch):
    async def should_not_check_user(_user_id):
        pytest.fail("User should not be checked for invalid message content")

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(should_not_check_user))

    with pytest.raises(ValueError, match="Message exceeds the 500 character limit."):
        asyncio.run(MessageService.create_anonymous_message(db_session, "owner-1", "x" * 501, None))


def test_create_message_rejects_unknown_user(db_session, monkeypatch):
    async def get_user_status(_user_id):
        return False, False

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(get_user_status))

    with pytest.raises(ValueError, match="The target message inbox user does not exist."):
        add_invite(db_session)
        asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "A note", None))


def test_create_message_rejects_paused_inbox(db_session, monkeypatch):
    async def get_user_status(_user_id):
        return True, False

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(get_user_status))

    with pytest.raises(ValueError, match="This inbox is not currently accepting messages."):
        add_invite(db_session)
        asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "A note", None))


def test_create_message_trims_content(db_session, monkeypatch):
    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))

    add_invite(db_session)
    message = asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "  A note  ", "Advice"))

    assert message.content == "A note"


def test_create_message_saves_category(db_session, monkeypatch):
    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))

    add_invite(db_session)
    message = asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "A note", "Advice"))

    assert message.category == "Advice"


def test_create_message_generates_reply_token(db_session, monkeypatch):
    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))

    add_invite(db_session)
    message = asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "A note", None))

    assert message.reply_token


def test_create_message_does_not_consume_shared_invite(db_session, monkeypatch):
    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))
    add_invite(db_session)

    asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "A note", None))

    invite = db_session.query(Invite).filter_by(token="invite-token").one()
    assert invite.used_at is None


def test_create_message_allows_reusing_shared_invite(db_session, monkeypatch):
    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))
    add_invite(db_session)
    first = asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "First note", None))

    second = asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "Second note", None))

    assert second.id != first.id


def test_create_message_accepts_legacy_invite_marked_used(db_session, monkeypatch):
    async def accepting_user(_user_id):
        return True, True

    monkeypatch.setattr(MessageService, "get_user_status", staticmethod(accepting_user))
    invite = add_invite(db_session)
    invite.used_at = datetime.utcnow()
    db_session.commit()

    message = asyncio.run(MessageService.create_anonymous_message(db_session, "invite-token", "A note", None))

    assert message.id


def test_get_user_status_maps_successful_user_response(monkeypatch):
    import httpx
    original_async_client = httpx.AsyncClient

    async def handler(request):
        assert str(request.url) == "http://localhost:8001/users/owner-1"
        return httpx.Response(200, json={"accepting_messages": False})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    result = asyncio.run(MessageService.get_user_status("owner-1"))

    assert result == (True, False)


def test_get_user_status_maps_not_found_response_to_unknown_user(monkeypatch):
    import httpx

    original_async_client = httpx.AsyncClient

    async def handler(_request):
        return httpx.Response(404)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    result = asyncio.run(MessageService.get_user_status("missing"))

    assert result == (False, False)


def test_get_user_status_maps_connection_failure_to_unknown_user(monkeypatch):
    import httpx

    original_async_client = httpx.AsyncClient

    async def handler(_request):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    result = asyncio.run(MessageService.get_user_status("offline"))

    assert result == (False, False)
