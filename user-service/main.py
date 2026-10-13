import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from sqlalchemy.orm import Session
from database import get_db
from services import UserService
from shared_auth import authenticated_user_id, bearer_scheme, create_access_token

app = FastAPI(title="User Microservice")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class AuthPayload(BaseModel):
    """Credentials supplied when registering or signing in."""

    username: str
    password: str = Field(min_length=12, max_length=128)

class SettingsPayload(BaseModel):
    """Inbox setting supplied by the account owner."""

    accepting_messages: bool

def _auth_response(user):
    return {
        "id": user.id,
        "username": user.username,
        "accepting_messages": user.accepting_messages,
        "access_token": create_access_token(user.id),
    }

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: AuthPayload, db: Session = Depends(get_db)):
    """Create a new owner account with a password."""
    try:
        return _auth_response(UserService.register_user(db, payload.username, payload.password))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/auth/login")
def login(payload: AuthPayload, db: Session = Depends(get_db)):
    """Authenticate an existing owner account."""
    try:
        return _auth_response(UserService.login_user(db, payload.username, payload.password))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@app.get("/users/{user_id}")
def verify_user_exists(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Return account details to the authenticated owner."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this account.")
    try:
        user = UserService.get_user_by_id(db, user_id)
        return {"id": user.id, "username": user.username, "accepting_messages": user.accepting_messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.get("/users/{user_id}/status")
def get_public_inbox_status(user_id: str, db: Session = Depends(get_db)):
    """Expose only whether a recipient can receive feedback."""
    try:
        user = UserService.get_user_by_id(db, user_id)
        return {"accepting_messages": user.accepting_messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.patch("/users/{user_id}/settings")
def update_user_settings(
    user_id: str,
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
):
    """Allow the authenticated owner to pause or resume anonymous messages."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot update this account.")
    try:
        user = UserService.update_settings(db, user_id, payload.accepting_messages)
        return {"id": user.id, "username": user.username, "accepting_messages": user.accepting_messages}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(authenticated_user_id),
    credentials=Depends(bearer_scheme),
):
    """Delete an account and its inbox data after confirming the data cleanup."""
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this account.")
    try:
        UserService.get_user_by_id(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    try:
        response = httpx.delete(
            f"http://localhost:8002/accounts/{user_id}/data",
            headers={"Authorization": f"Bearer {credentials.credentials}"},
            timeout=10,
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete associated inbox data. The account was not deleted; please try again.",
        ) from e
    if response.status_code != status.HTTP_204_NO_CONTENT:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete associated inbox data. The account was not deleted; please try again.",
        )

    UserService.delete_user(db, user_id)
