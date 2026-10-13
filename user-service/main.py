from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from services import UserService

app = FastAPI(title="User Microservice")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class AuthPayload(BaseModel):
    """Username supplied when creating or retrieving an account."""

    username: str

class SettingsPayload(BaseModel):
    """Inbox setting supplied by the account owner."""

    accepting_messages: bool

@app.post("/auth")
def login_or_register(payload: AuthPayload, db: Session = Depends(get_db)):
    """Create or retrieve an account by username."""
    try:
        user = UserService.authenticate_user(db, payload.username)
        return {"id": user.id, "username": user.username, "accepting_messages": user.accepting_messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/users/{user_id}")
def verify_user_exists(user_id: str, db: Session = Depends(get_db)):
    """Return account details for an internal user ID."""
    try:
        user = UserService.get_user_by_id(db, user_id)
        return {"id": user.id, "username": user.username, "accepting_messages": user.accepting_messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.patch("/users/{user_id}/settings")
def update_user_settings(user_id: str, payload: SettingsPayload, db: Session = Depends(get_db)):
    """Pause or resume anonymous messages for an account."""
    try:
        user = UserService.update_settings(db, user_id, payload.accepting_messages)
        return {"id": user.id, "username": user.username, "accepting_messages": user.accepting_messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
