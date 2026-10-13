import pytest

from database import User
from services import UserService


def create_user(db_session, username="Mira", password="correct horse battery"):
    return UserService.register_user(db_session, username, password)


def test_register_trims_username(db_session):
    user = create_user(db_session, "  Mira  ")

    assert user.username == "Mira"


def test_register_opens_new_inbox_by_default(db_session):
    user = create_user(db_session)

    assert user.accepting_messages is True


def test_register_assigns_identifier(db_session):
    assert create_user(db_session).id


def test_register_rejects_duplicate_username(db_session):
    first = create_user(db_session)

    with pytest.raises(ValueError, match="already exists"):
        create_user(db_session)

    assert db_session.query(User).count() == 1
    assert first.password_hash


@pytest.mark.parametrize("username", ["", " ", "   "])
def test_register_rejects_blank_username(db_session, username):
    with pytest.raises(ValueError, match="Username cannot be blank."):
        create_user(db_session, username)


def test_login_checks_password(db_session):
    user = create_user(db_session)

    assert UserService.login_user(db_session, "Mira", "correct horse battery").id == user.id
    with pytest.raises(ValueError, match="Incorrect username or password."):
        UserService.login_user(db_session, "Mira", "wrong password")


def test_login_rejects_unknown_user(db_session):
    with pytest.raises(ValueError, match="Incorrect username or password."):
        UserService.login_user(db_session, "unknown", "wrong password")

def test_set_legacy_password_upgrades_existing_account(db_session):
    legacy_user = User(username="Mira")
    db_session.add(legacy_user)
    db_session.commit()

    upgraded = UserService.set_legacy_password(db_session, "Mira", "correct horse battery")

    assert UserService.login_user(db_session, "Mira", "correct horse battery").id == legacy_user.id
    assert upgraded.password_hash

def test_set_legacy_password_does_not_replace_existing_password(db_session):
    create_user(db_session)

    with pytest.raises(ValueError, match="already has a password"):
        UserService.set_legacy_password(db_session, "Mira", "new password 123")


def test_get_user_by_id_returns_existing_user(db_session):
    user = create_user(db_session)

    assert UserService.get_user_by_id(db_session, user.id).id == user.id


def test_get_user_by_id_rejects_unknown_user(db_session):
    with pytest.raises(ValueError, match="Requested user account does not exist."):
        UserService.get_user_by_id(db_session, "unknown")


@pytest.mark.parametrize("accepting_messages", [False, True])
def test_update_settings_changes_acceptance_preference(db_session, accepting_messages):
    user = create_user(db_session)

    updated = UserService.update_settings(db_session, user.id, accepting_messages)

    assert updated.accepting_messages is accepting_messages


def test_update_settings_rejects_unknown_user(db_session):
    with pytest.raises(ValueError, match="Requested user account does not exist."):
        UserService.update_settings(db_session, "unknown", False)


def test_delete_user_removes_account(db_session):
    user = create_user(db_session)

    UserService.delete_user(db_session, user.id)

    assert db_session.query(User).filter_by(id=user.id).first() is None


def test_delete_user_rejects_unknown_user(db_session):
    with pytest.raises(ValueError, match="Requested user account does not exist."):
        UserService.delete_user(db_session, "unknown")
