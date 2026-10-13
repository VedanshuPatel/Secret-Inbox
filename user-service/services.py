import hashlib
import hmac
import secrets
from typing import Optional
from sqlalchemy.orm import Session
from database import User


PASSWORD_ITERATIONS = 600_000


class UserService:
    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
        return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, encoded: Optional[str]) -> bool:
        if not encoded:
            return False
        try:
            algorithm, iterations, salt, expected = encoded.split("$")
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
            return hmac.compare_digest(digest.hex(), expected)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _clean_username(username: str) -> str:
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("Username cannot be blank.")
        return clean_username

    @classmethod
    def register_user(cls, db: Session, username: str, password: str) -> User:
        """Create a new password-protected account."""
        clean_username = cls._clean_username(username)
        if db.query(User).filter(User.username == clean_username).first():
            raise ValueError("An account with this username already exists.")
        user = User(username=clean_username, password_hash=cls._hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def login_user(cls, db: Session, username: str, password: str) -> User:
        """Verify credentials without revealing whether an account exists."""
        clean_username = cls._clean_username(username)
        user = db.query(User).filter(User.username == clean_username).first()
        if not user or not cls._verify_password(password, user.password_hash):
            raise ValueError("Incorrect username or password.")
        return user

    @classmethod
    def set_legacy_password(cls, db: Session, username: str, password: str) -> User:
        """Set a password only for an existing account from before password auth."""
        clean_username = cls._clean_username(username)
        user = db.query(User).filter(User.username == clean_username).first()
        if not user:
            raise ValueError("Requested user account does not exist.")
        if user.password_hash:
            raise ValueError("This account already has a password.")
        user.password_hash = cls._hash_password(password)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> User:
        """Return an account by its ID or raise when it does not exist."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("Requested user account does not exist.")
        return user

    @staticmethod
    def update_settings(db: Session, user_id: str, accepting_messages: bool) -> User:
        """Set whether an existing account accepts anonymous messages."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("Requested user account does not exist.")
        user.accepting_messages = accepting_messages
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: str) -> None:
        """Delete an account after its associated message-service data is removed."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("Requested user account does not exist.")
        db.delete(user)
        db.commit()
