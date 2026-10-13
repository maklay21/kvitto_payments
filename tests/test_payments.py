import hashlib
import hmac
import json

from app.core.config import settings
from app.services import build_schedule


def post_signed_webhook(client, payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/bank",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": signature},
    )


def test_tariffs_are_seeded(client):
    response = client.get("/tariffs")
    assert response.status_code == 200
    assert {item["id"]: item["price"] for item in response.json()} == {
        "basic": 990_000,
        "standard": 1_990_000,
        "premium": 2_990_000,
    }


def test_payment_amount_without_promo(client, payment_payload):
    response = client.post("/payments", json=payment_payload)
    assert response.status_code == 201
    assert response.json()["amount"] == 1_990_000
    assert response.json()["discount"] == 0


def test_promo_is_case_insensitive_and_uses_kopecks(client, payment_payload):
    response = client.post("/payments", json={**payment_payload, "promo_code": "kvitto10"})
    assert response.status_code == 201
    assert response.json()["discount"] == 199_000
    assert response.json()["amount"] == 1_791_000


def test_unknown_promo_is_422(client, payment_payload):
    response = client.post("/payments", json={**payment_payload, "promo_code": "NOPE"})
    assert response.status_code == 422


def test_installment_schedules_sum_exactly():
    amount = 1_990_000
    for months in (3, 6, 12):
        schedule = build_schedule(amount, months)
        assert len(schedule) == months
        assert sum(schedule) == amount
        assert max(schedule) - min(schedule) <= 1


def test_idempotency_key_returns_existing_payment(client, payment_payload):
    first = client.post(
        "/payments", json=payment_payload, headers={"Idempotency-Key": "request-1"}
    )
    second = client.post(
        "/payments", json=payment_payload, headers={"Idempotency-Key": "request-1"}
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_invalid_status_transition_returns_409_and_preserves_status(client, payment_payload):
    created = client.post("/payments", json=payment_payload).json()
    response = post_signed_webhook(
        client, {"payment_id": created["id"], "status": "refunded"}
    )
    assert response.status_code == 409
    assert response.json() == {"error": "invalid_transition"}
    current = client.get(f"/payments/{created['id']}")
    assert current.json()["status"] == "pending"


def test_unknown_payment_returns_404(client):
    assert client.get("/payments/nonexistent").status_code == 404


def test_missing_tariff_returns_404(client, payment_payload):
    response = client.post("/payments", json={**payment_payload, "tariff_id": "missing"})
    assert response.status_code == 404


def test_installment_requires_supported_months(client, payment_payload):
    response = client.post(
        "/payments",
        json={**payment_payload, "method": "installment", "installment_months": 5},
    )
    assert response.status_code == 422


def test_webhook_allows_pending_to_succeeded_then_refunded(client, payment_payload):
    created = client.post("/payments", json=payment_payload).json()
    success = post_signed_webhook(
        client, {"payment_id": created["id"], "status": "succeeded"}
    )
    refund = post_signed_webhook(
        client, {"payment_id": created["id"], "status": "refunded"}
    )
    assert success.json() == {"result": "ok"}
    assert refund.json() == {"result": "ok"}
    assert client.get(f"/payments/{created['id']}").json()["status"] == "refunded"
