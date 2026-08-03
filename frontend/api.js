const BASE_URL = "http://localhost:8000";

export async function seedData(n = 300) {
  const res = await fetch(`${BASE_URL}/seed?n=${n}`, { method: "POST" });
  return res.json();
}

export async function simulateOne() {
  const res = await fetch(`${BASE_URL}/transactions/simulate`, { method: "POST" });
  return res.json();
}

export async function simulateBurst(userId = "user_9999", count = 5) {
  const res = await fetch(
    `${BASE_URL}/transactions/simulate-burst?user_id=${userId}&count=${count}`,
    { method: "POST" }
  );
  return res.json();
}

export async function getTransactions({ flaggedOnly = false, reviewStatus = null, limit = 100 } = {}) {
  const params = new URLSearchParams({ limit });
  if (flaggedOnly) params.set("flagged_only", "true");
  if (reviewStatus) params.set("review_status", reviewStatus);
  const res = await fetch(`${BASE_URL}/transactions?${params}`);
  return res.json();
}

export async function getStats() {
  const res = await fetch(`${BASE_URL}/stats`);
  return res.json();
}

export async function reviewTransaction(id, reviewStatus) {
  const res = await fetch(`${BASE_URL}/transactions/${id}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_status: reviewStatus }),
  });
  return res.json();
}