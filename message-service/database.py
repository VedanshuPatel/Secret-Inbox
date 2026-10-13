from sqlalchemy import create_engine, Column, String, Integer, DateTime, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

ENGINE = create_engine("sqlite:///./message.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)
Base = declarative_base()

class Message(Base):
    """Persist anonymous feedback and its owner-managed follow-up state."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True, nullable=False)
    content = Column(String, nullable=False)
    status = Column(String, default="active", nullable=False)
    category = Column(String, nullable=True)
    reaction = Column(String, nullable=True)
    reply = Column(String, nullable=True)
    reply_at = Column(DateTime, nullable=True)
    report_reason = Column(String, nullable=True)
    reply_token = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Invite(Base):
    """Store shared invite tokens that authorize anonymous submissions."""

    __tablename__ = "invites"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=ENGINE)


def _run_lightweight_migrations():
    """Add schema fields missing from an existing local SQLite database."""
    inspector = inspect(ENGINE)
    if "messages" not in inspector.get_table_names():
        return
    existing_columns = {col["name"] for col in inspector.get_columns("messages")}
    new_columns = {
        "status": "ALTER TABLE messages ADD COLUMN status VARCHAR DEFAULT 'active' NOT NULL",
        "category": "ALTER TABLE messages ADD COLUMN category VARCHAR",
        "reaction": "ALTER TABLE messages ADD COLUMN reaction VARCHAR",
        "reply": "ALTER TABLE messages ADD COLUMN reply VARCHAR",
        "reply_at": "ALTER TABLE messages ADD COLUMN reply_at DATETIME",
        "report_reason": "ALTER TABLE messages ADD COLUMN report_reason VARCHAR",
        "reply_token": "ALTER TABLE messages ADD COLUMN reply_token VARCHAR",
    }
    with ENGINE.begin() as conn:
        for column, ddl in new_columns.items():
            if column not in existing_columns:
                conn.execute(text(ddl))
        if "reply_token" not in existing_columns:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_messages_reply_token ON messages (reply_token)"))


_run_lightweight_migrations()

def get_db():
    """Provide one SQLAlchemy session per request and always close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
