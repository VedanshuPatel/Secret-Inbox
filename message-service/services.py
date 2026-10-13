from datetime import datetime
from typing import Optional, Tuple
import secrets
import uuid
from sqlalchemy.orm import Session
from database import Invite, Message
import httpx

VALID_STATUSES = {"active", "archived", "reported"}


class MessageService:
    @staticmethod
    def delete_user_data(db: Session, user_id: str) -> None:
        """Delete an owner's messages and invite links."""
        db.query(Message).filter(Message.user_id == user_id).delete(synchronize_session=False)
        db.query(Invite).filter(Invite.user_id == user_id).delete(synchronize_session=False)
        db.commit()

    @staticmethod
    def get_latest_invite(db: Session, user_id: str) -> Optional[Invite]:
        """Return the newest saved shared invite for an owner, if one exists."""
        return (
            db.query(Invite)
            .filter(Invite.user_id == user_id)
            .order_by(Invite.created_at.desc())
            .first()
        )

    @classmethod
    async def create_invites(cls, db: Session, user_id: str, count: int) -> list[Invite]:
        """Replace prior invite links with a new set for one accepting inbox."""
        if count < 1 or count > 50:
            raise ValueError("Invite count must be between 1 and 50.")

        exists, accepting_messages = await cls.get_user_status(user_id)
        if not exists:
            raise ValueError("The target message inbox user does not exist.")
        if not accepting_messages:
            raise ValueError("This inbox is not currently accepting messages.")

        db.query(Invite).filter(Invite.user_id == user_id).delete(synchronize_session=False)
        invites = [
            Invite(token=secrets.token_urlsafe(32), user_id=user_id)
            for _ in range(count)
        ]
        db.add_all(invites)
        db.commit()
        return invites

    @classmethod
    async def create_invite(cls, db: Session, user_id: str) -> Invite:
        """Create one shared invite link for an existing inbox that is accepting messages."""
        return (await cls.create_invites(db, user_id, 1))[0]

    @staticmethod
    async def get_user_status(user_id: str) -> Tuple[bool, bool]:
        """Check whether the user service knows this recipient and accepts messages.

        Returns a pair of (user_exists, accepting_messages).
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"http://localhost:8001/users/{user_id}/status")
                if response.status_code != 200:
                    return False, False
                data = response.json()
                return True, bool(data.get("accepting_messages", True))
            except httpx.RequestError:
                # Fail closed: a recipient cannot be verified if the user API is offline.
                return False, False

    @classmethod
    async def create_anonymous_message(cls, db: Session, invite_token: str, content: str, category: Optional[str]) -> Message:
        """Validate a shared invite and persist its anonymous message."""
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Message content cannot be blank.")
        if len(clean_content) > 500:
            raise ValueError("Message exceeds the 500 character limit.")

        invite = db.query(Invite).filter(Invite.token == invite_token).first()
        if not invite:
            raise ValueError("This invite link is invalid.")

        exists, accepting_messages = await cls.get_user_status(invite.user_id)
        if not exists:
            raise ValueError("The target message inbox user does not exist.")
        if not accepting_messages:
            raise ValueError("This inbox is not currently accepting messages.")

        new_message = Message(
            user_id=invite.user_id,
            content=clean_content,
            category=category,
            reply_token=str(uuid.uuid4()),
        )
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        return new_message

    @staticmethod
    def get_user_inbox(db: Session, user_id: str, status: str = "active"):
        """Return one user's messages in the requested status, newest first."""
        return (
            db.query(Message)
            .filter(Message.user_id == user_id, Message.status == status)
            .order_by(Message.created_at.desc())
            .all()
        )

    @staticmethod
    def get_message_by_token(db: Session, token: str) -> Message:
        """Resolve a sender's private follow-up token to its message."""
        message = db.query(Message).filter(Message.reply_token == token).first()
        if not message:
            raise ValueError("No message found for this link.")
        return message

    @staticmethod
    def _get_message_or_raise(db: Session, message_id: int) -> Message:
        """Load a message by ID or raise a consistent not-found error."""
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise ValueError("Message not found.")
        return message

    @classmethod
    def archive_message(cls, db: Session, message_id: int) -> Message:
        """Move a message out of the active inbox."""
        message = cls._get_message_or_raise(db, message_id)
        message.status = "archived"
        db.commit()
        db.refresh(message)
        return message

    @classmethod
    def restore_message(cls, db: Session, message_id: int) -> Message:
        """Return an archived or reported message to the active inbox."""
        message = cls._get_message_or_raise(db, message_id)
        message.status = "active"
        db.commit()
        db.refresh(message)
        return message

    @classmethod
    def delete_message(cls, db: Session, message_id: int) -> None:
        """Permanently remove a message."""
        message = cls._get_message_or_raise(db, message_id)
        db.delete(message)
        db.commit()

    @classmethod
    def set_reaction(cls, db: Session, message_id: int, reaction: str) -> Message:
        """Save the inbox owner's reaction for the sender's private page."""
        message = cls._get_message_or_raise(db, message_id)
        message.reaction = reaction
        db.commit()
        db.refresh(message)
        return message

    @classmethod
    def set_reply(cls, db: Session, message_id: int, reply_text: str) -> Message:
        """Save a nonblank written reply and record when it was sent."""
        clean_reply = reply_text.strip()
        if not clean_reply:
            raise ValueError("Reply cannot be blank.")
        message = cls._get_message_or_raise(db, message_id)
        message.reply = clean_reply
        message.reply_at = datetime.utcnow()
        db.commit()
        db.refresh(message)
        return message

    @classmethod
    def report_message(cls, db: Session, message_id: int, reason: str) -> Message:
        """Mark a message reported and store a trimmed optional reason."""
        message = cls._get_message_or_raise(db, message_id)
        message.status = "reported"
        message.report_reason = reason.strip() or None
        db.commit()
        db.refresh(message)
        return message
