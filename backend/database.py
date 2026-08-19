"""
Database layer for FraudLens.

Uses SQLite locally for zero-setup development. To move to Supabase/Postgres
for production, just change DATABASE_URL below to your Supabase connection
string (found in Project Settings -> Database) — SQLAlchemy handles the rest.
"""
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Swap this line for Supabase in production ---
# DATABASE_URL = "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres"
DATABASE_URL = "sqlite:///./fraudlens.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(String, index=True)
    receiver_id = Column(String, index=True)
    amount = Column(Float)
    currency = Column(String, default="USD")
    device_id = Column(String)
    location = Column(String)
    hour_of_day = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # ML + rules output
    risk_score = Column(Float, default=0.0)       # 0-1, higher = more suspicious
    is_flagged = Column(Boolean, default=False)
    flag_reasons = Column(String, default="")      # comma-separated human-readable reasons

    # Review workflow
    review_status = Column(String, default="pending")  # pending | confirmed_fraud | false_positive
    reviewed_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
