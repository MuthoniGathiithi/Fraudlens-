"""
Generates realistic-looking transaction data, with a controlled percentage
of deliberate anomalies injected so the detection model has real signal
to learn from and the dashboard has something meaningful to show.
"""
import random
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()

NORMAL_AMOUNT_RANGE = (5, 500)
ANOMALY_AMOUNT_RANGE = (2000, 20000)
DEVICE_POOL = [fake.uuid4()[:8] for _ in range(40)]
LOCATIONS = ["Nairobi", "Lagos", "Kampala", "Accra", "Kigali", "Dar es Salaam", "Unknown"]


def _random_user_id():
    return f"user_{random.randint(1000, 9999)}"


def generate_transaction(force_anomaly: bool = False) -> dict:
    """Generate a single transaction dict. ~8% are anomalous unless forced."""
    is_anomaly = force_anomaly or random.random() < 0.08

    hour = random.choice([2, 3, 4]) if is_anomaly and random.random() < 0.5 else random.randint(6, 22)
    amount = round(random.uniform(*ANOMALY_AMOUNT_RANGE), 2) if is_anomaly and random.random() < 0.6 \
        else round(random.uniform(*NORMAL_AMOUNT_RANGE), 2)

    device = random.choice(["NEW_DEVICE_" + fake.uuid4()[:6]] if is_anomaly and random.random() < 0.4
                            else DEVICE_POOL)
    location = "Unknown" if is_anomaly and random.random() < 0.3 else random.choice(LOCATIONS[:-1])

    return {
        "sender_id": _random_user_id(),
        "receiver_id": _random_user_id(),
        "amount": amount,
        "currency": "USD",
        "device_id": device,
        "location": location,
        "hour_of_day": hour,
        "timestamp": datetime.utcnow() - timedelta(minutes=random.randint(0, 60)),
    }


def generate_batch(n: int = 200, anomaly_rate: float = 0.08) -> list[dict]:
    """Generate a batch of n transactions with roughly anomaly_rate fraction anomalous."""
    batch = []
    for _ in range(n):
        batch.append(generate_transaction(force_anomaly=random.random() < anomaly_rate))
    return batch


def generate_burst_for_user(user_id: str, count: int = 5) -> list[dict]:
    """Simulate a rapid-fire burst of transactions from one sender — a classic fraud pattern."""
    now = datetime.utcnow()
    burst = []
    for i in range(count):
        burst.append({
            "sender_id": user_id,
            "receiver_id": _random_user_id(),
            "amount": round(random.uniform(50, 300), 2),
            "currency": "USD",
            "device_id": random.choice(DEVICE_POOL),
            "location": random.choice(LOCATIONS),
            "hour_of_day": now.hour,
            "timestamp": now - timedelta(seconds=i * 10),  # 10 seconds apart
        })
    return burst