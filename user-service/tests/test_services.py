import pytest

from database import User
from services import UserService


def test_authenticate_user_trims_username(db_session):
    user = UserService.authenticate_user(db_session, "  Mira  ")

    assert user.username == "Mira"


def test_authenticate_user_opens_new_inbox_by_default(db_session):
    user = UserService.authenticate_user(db_session, "Mira")

    assert user.accepting_messages is True


def test_authenticate_user_assigns_identifier(db_session):
    user = UserService.authenticate_user(db_session, "Mira")

    assert user.id


def test_authenticate_user_reuses_existing_username(db_session):
    first = UserService.authenticate_user(db_session, "Mira")

    second = UserService.authenticate_user(db_session, "Mira")

    assert second.id == first.id
    assert db_session.query(User).count() == 1


@pytest.mark.parametrize("username", ["", " ", "   "])
def test_authenticate_user_rejects_blank_username(db_session, username):
    with pytest.raises(ValueError, match="Username cannot be blank."):
        UserService.authenticate_user(db_session, username)


def test_get_user_by_id_returns_existing_user(db_session):
    user = UserService.authenticate_user(db_session, "Mira")

    found = UserService.get_user_by_id(db_session, user.id)

    assert found.id == user.id


def test_get_user_by_id_rejects_unknown_user(db_session):
    with pytest.raises(ValueError, match="Requested user account does not exist."):
        UserService.get_user_by_id(db_session, "unknown")


@pytest.mark.parametrize("accepting_messages", [False, True])
def test_update_settings_changes_acceptance_preference(db_session, accepting_messages):
    user = UserService.authenticate_user(db_session, "Mira")

    updated = UserService.update_settings(db_session, user.id, accepting_messages)

    assert updated.accepting_messages is accepting_messages


def test_update_settings_rejects_unknown_user(db_session):
    with pytest.raises(ValueError, match="Requested user account does not exist."):
        UserService.update_settings(db_session, "unknown", False)
