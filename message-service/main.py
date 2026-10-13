import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
from services import MessageService, VALID_STATUSES
from ai_service import AIService
from shared_auth import authenticated_user_id

app = FastAPI(title="Messaging Microservice")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class MessagePayload(BaseModel):
    """Anonymous feedback submitted to a recipient's inbox."""

    content: str
    category: Optional[str] = None

class InviteBatchPayload(BaseModel):
    """Legacy batch helper for creating distinct links for an inbox."""

    count: int = Field(ge=1, le=50)

class ReactionPayload(BaseModel):
    """Reaction selected by an inbox owner."""

    reaction: str

class ReplyPayload(BaseModel):
    """Written reply sent by an inbox owner."""

    reply: str

class ReportPayload(BaseModel):
    """Optional reason attached to a reported message."""

    reason: str

def _require_owned_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    try:
        message = MessageService._get_message_or_raise(db, message_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if message.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    return message

def _serialize(m):
    """Convert an inbox message to the public owner-facing response shape."""
    return {
        "id": m.id,
        "content": m.content,
        "status": m.status,
        "category": m.category,
        "reaction": m.reaction,
        "reply": m.reply,
        "reply_at": m.reply_at,
        "report_reason": m.report_reason,
        "created_at": m.created_at,
    }

@app.post("/invites/{user_id}", status_code=status.HTTP_201_CREATED)
async def create_invite(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Create an invitation link for the authenticated owner's inbox."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot create invites for this account.")
    try:
        invite = await MessageService.create_invite(db, user_id)
        return {"invite_token": invite.token}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/invites/{user_id}")
def fetch_invite(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Return the owner's saved shared invite without creating a new one."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access invites for this account.")
    invite = MessageService.get_latest_invite(db, user_id)
    return {"invite_token": invite.token if invite else None}

@app.delete("/accounts/{user_id}/data", status_code=status.HTTP_204_NO_CONTENT)
def delete_account_data(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Delete messages and invites belonging to the authenticated owner."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this account's data.")
    MessageService.delete_user_data(db, user_id)

@app.post("/invites/{user_id}/batch", status_code=status.HTTP_201_CREATED)
async def create_invite_batch(
    user_id: str,
    payload: InviteBatchPayload,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Legacy batch endpoint for creating distinct invite links in one request."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot create invites for this account.")
    try:
        invites = await MessageService.create_invites(db, user_id, payload.count)
        return {"invite_tokens": [invite.token for invite in invites]}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/messages/invite/{invite_token}")
async def submit_feedback(invite_token: str, payload: MessagePayload, db: Session = Depends(get_db)):
    """Accept anonymous feedback through a shared invite link."""
    try:
        message = await MessageService.create_anonymous_message(
            db, invite_token, payload.content, payload.category
        )
        return {"status": "success", "reply_token": message.reply_token}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/messages/token/{token}")
def fetch_message_by_token(token: str, db: Session = Depends(get_db)):
    """Return sender-visible message state without exposing the recipient ID."""
    try:
        message = MessageService.get_message_by_token(db, token)
        return {
            "content": message.content,
            "category": message.category,
            "reply": message.reply,
            "reply_at": message.reply_at,
            "reaction": message.reaction,
            "created_at": message.created_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.get("/messages/{user_id}")
def fetch_user_inbox(
    user_id: str,
    status_: str = Query("active", alias="status"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """List the authenticated owner's messages."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this inbox.")
    if status_ not in VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter.")
    messages = MessageService.get_user_inbox(db, user_id, status_)
    return [_serialize(m) for m in messages]

@app.patch("/messages/{message_id}/archive")
def archive_message(message_id: int, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Move a message to the archived inbox."""
    try:
        message = MessageService.archive_message(db, message_id)
        return _serialize(message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.patch("/messages/{message_id}/restore")
def restore_message(message_id: int, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Restore a message to the active inbox."""
    try:
        message = MessageService.restore_message(db, message_id)
        return _serialize(message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.delete("/messages/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Permanently delete a message."""
    try:
        MessageService.delete_message(db, message_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.patch("/messages/{message_id}/reaction")
def set_reaction(message_id: int, payload: ReactionPayload, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Save an owner's reaction for display on the sender's private page."""
    try:
        message = MessageService.set_reaction(db, message_id, payload.reaction)
        return _serialize(message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.patch("/messages/{message_id}/reply")
def set_reply(message_id: int, payload: ReplyPayload, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Save an owner's written reply."""
    try:
        message = MessageService.set_reply(db, message_id, payload.reply)
        return _serialize(message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.patch("/messages/{message_id}/report")
def report_message(message_id: int, payload: ReportPayload, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Mark a message reported and optionally record why."""
    try:
        message = MessageService.report_message(db, message_id, payload.reason)
        return _serialize(message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

def _ai_error_status(e: ValueError) -> int:
    """Map AI availability errors to 503 and request/content errors to 400."""
    if "unavailable" in str(e).lower():
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_400_BAD_REQUEST

@app.post("/messages/{user_id}/summarize")
async def summarize_inbox(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Summarize active messages in the authenticated owner's inbox."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this inbox.")
    messages = MessageService.get_user_inbox(db, user_id, "active")
    try:
        summary = await AIService.summarize_inbox(messages)
        return {"summary": summary, "message_count": len(messages)}
    except ValueError as e:
        raise HTTPException(status_code=_ai_error_status(e), detail=str(e))

@app.post("/messages/{message_id}/suggest-reply")
async def suggest_reply(message_id: int, db: Session = Depends(get_db), _message=Depends(_require_owned_message)):
    """Generate a reply draft for a message in the authenticated owner's inbox."""
    try:
        message = MessageService._get_message_or_raise(db, message_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    try:
        suggestion = await AIService.suggest_reply(message)
        return {"suggestion": suggestion}
    except ValueError as e:
        raise HTTPException(status_code=_ai_error_status(e), detail=str(e))
