"""
FraudLens API
Endpoints for seeding data, streaming/creating transactions, listing flagged
transactions, and reviewing them (confirm fraud / mark false positive).
"""
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import init_db, get_db, Transaction
from data_simulator import generate_batch, generate_transaction, generate_burst_for_user
from model import detector

app = FastAPI(title="FraudLens API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class ReviewUpdate(BaseModel):
    review_status: str  # "confirmed_fraud" | "false_positive"


def _save_and_score(db: Session, raw_tx: dict) -> Transaction:
    scored = detector.score(raw_tx)
    tx = Transaction(**raw_tx, **scored)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@app.post("/seed")
def seed_data(n: int = 300, db: Session = Depends(get_db)):
    """
    Generate n historical transactions, fit the ML model on them, then score
    and store them. Call this once on a fresh database before using the app.
    """
    batch = generate_batch(n=n)
    detector.fit(batch)  # train on the batch's raw features (unsupervised)

    saved = [_save_and_score(db, row) for row in batch]
    flagged_count = sum(1 for tx in saved if tx.is_flagged)
    return {"created": len(saved), "flagged": flagged_count}


@app.post("/transactions/simulate")
def simulate_one(db: Session = Depends(get_db)):
    """Create one new incoming transaction, score it live, return the result."""
    if not detector.is_fitted:
        raise HTTPException(400, "Model not trained yet — call POST /seed first.")
    raw_tx = generate_transaction()
    tx = _save_and_score(db, raw_tx)
    return _serialize(tx)


@app.post("/transactions/simulate-burst")
def simulate_burst(user_id: str = "user_9999", count: int = 5, db: Session = Depends(get_db)):
    """Simulate a rapid-fire velocity-fraud burst from one sender — good for demos."""
    if not detector.is_fitted:
        raise HTTPException(400, "Model not trained yet — call POST /seed first.")
    burst = generate_burst_for_user(user_id, count)
    saved = [_serialize(_save_and_score(db, row)) for row in burst]
    return saved


@app.get("/transactions")
def list_transactions(
    flagged_only: bool = False,
    review_status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).order_by(desc(Transaction.timestamp))
    if flagged_only:
        query = query.filter(Transaction.is_flagged == True)  # noqa: E712
    if review_status:
        query = query.filter(Transaction.review_status == review_status)
    rows = query.limit(limit).all()
    return [_serialize(tx) for tx in rows]


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Transaction).count()
    flagged = db.query(Transaction).filter(Transaction.is_flagged == True).count()  # noqa: E712
    pending = db.query(Transaction).filter(Transaction.review_status == "pending",
                                            Transaction.is_flagged == True).count()  # noqa: E712
    confirmed = db.query(Transaction).filter(Transaction.review_status == "confirmed_fraud").count()
    false_positive = db.query(Transaction).filter(Transaction.review_status == "false_positive").count()
    return {
        "total_transactions": total,
        "total_flagged": flagged,
        "pending_review": pending,
        "confirmed_fraud": confirmed,
        "false_positives": false_positive,
        "flag_rate": round(flagged / total, 3) if total else 0,
    }


@app.patch("/transactions/{tx_id}/review")
def review_transaction(tx_id: int, update: ReviewUpdate, db: Session = Depends(get_db)):
    if update.review_status not in ("confirmed_fraud", "false_positive", "pending"):
        raise HTTPException(400, "Invalid review_status")
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(404, "Transaction not found")
    tx.review_status = update.review_status
    tx.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(tx)
    return _serialize(tx)


def _serialize(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "sender_id": tx.sender_id,
        "receiver_id": tx.receiver_id,
        "amount": tx.amount,
        "currency": tx.currency,
        "device_id": tx.device_id,
        "location": tx.location,
        "hour_of_day": tx.hour_of_day,
        "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
        "risk_score": tx.risk_score,
        "is_flagged": tx.is_flagged,
        "flag_reasons": tx.flag_reasons,
        "review_status": tx.review_status,
    }


@app.get("/")
def root():
    return {"status": "FraudLens API running", "docs": "/docs"}