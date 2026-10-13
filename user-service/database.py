from sqlalchemy import create_engine, Column, String, Boolean, DateTime, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import uuid


ENGINE = create_engine("sqlite:///./user.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)
Base = declarative_base()


class User(Base):
    """Persist account identity and whether its inbox accepts new messages."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    accepting_messages = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=ENGINE)


def _run_lightweight_migrations():
    """Add columns introduced after the table already existed on disk."""
    inspector = inspect(ENGINE)
    if "users" not in inspector.get_table_names():
        return
    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    if "accepting_messages" not in existing_columns:
        with ENGINE.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN accepting_messages BOOLEAN DEFAULT 1 NOT NULL"))


_run_lightweight_migrations()


def get_db():
    """Provide one SQLAlchemy session per request and always close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
