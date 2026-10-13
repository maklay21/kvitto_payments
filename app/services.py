from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Payment, Tariff
from app.schemas import BankWebhook, PaymentCreate

PROMO_CODES = {"KVITTO10"}

ALLOWED_TRANSITIONS = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"refunded"},
    "failed": set(),
    "refunded": set(),
}


class UnknownPromoCodeError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


def seed_tariffs(db: Session) -> None:
    tariffs = (
        ("basic", "Basic", 990_000),
        ("standard", "Standard", 1_990_000),
        ("premium", "Premium", 2_990_000),
    )
    for tariff_id, title, price in tariffs:
        if db.get(Tariff, tariff_id) is None:
            db.add(Tariff(id=tariff_id, title=title, price=price))
    db.commit()


def build_schedule(amount: int, months: int) -> list[int]:
    base, remainder = divmod(amount, months)
    return [base + (1 if month < remainder else 0) for month in range(months)]


def create_payment(
    db: Session,
    payload: PaymentCreate,
    idempotency_key: str | None,
) -> tuple[Payment, bool]:

    if idempotency_key:
        existing = db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
        if existing is not None:
            return existing, False

    tariff = db.get(Tariff, payload.tariff_id)
    if tariff is None:
        raise LookupError("tariff_not_found")

    discount = 0
    if payload.promo_code is not None:
        if payload.promo_code.strip().upper() not in PROMO_CODES:
            raise UnknownPromoCodeError
        discount = tariff.price * 10 // 100

    amount = tariff.price - discount
    schedule = (
        build_schedule(amount, payload.installment_months)
        if payload.method == "installment" and payload.installment_months is not None
        else None
    )

    payment = Payment(
        id=str(uuid4()),
        status="pending",
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=payload.method,
        installment_months=payload.installment_months,
        schedule=schedule,
        email=str(payload.email),
        idempotency_key=idempotency_key,
    )
    db.add(payment)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
            if existing is not None:
                return existing, False
        raise

    db.refresh(payment)
    return payment, True


def get_payment(db: Session, payment_id: str) -> Payment | None:
    return db.get(Payment, payment_id)


def list_payments(db: Session, email: str | None, status: str | None) -> list[Payment]:
    query = select(Payment).order_by(Payment.created_at.desc())
    if email:
        query = query.where(Payment.email == email)
    if status:
        query = query.where(Payment.status == status)

    return list(db.scalars(query).all())


def apply_bank_webhook(db: Session, payload: BankWebhook) -> None:
    payment = db.scalar(select(Payment).where(Payment.id == payload.payment_id).with_for_update())
    if payment is None:
        raise LookupError("payment_not_found")
    if payload.status not in ALLOWED_TRANSITIONS[payment.status]:
        raise InvalidTransitionError

    payment.status = payload.status
    db.commit()
