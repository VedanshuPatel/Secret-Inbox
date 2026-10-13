from sqlalchemy.orm import Session
from database import User

class UserService:
    @staticmethod
    def authenticate_user(db: Session, username: str) -> User:
        """Return the account for a trimmed username, creating it when needed."""
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("Username cannot be blank.")

        user = db.query(User).filter(User.username == clean_username).first()
        if not user:
            user = User(username=clean_username)
            db.add(user)
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
