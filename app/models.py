from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tariff(Base):
    __tablename__ = "tariffs"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_tariffs_price_nonnegative"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    payments: Mapped[list["Payment"]] = relationship(back_populates="tariff")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payments_amount_nonnegative"),
        CheckConstraint("discount >= 0", name="ck_payments_discount_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name="ck_payments_status",
        ),
        CheckConstraint("method IN ('card', 'sbp', 'installment')", name="ck_payments_method"),
        CheckConstraint(
            "installment_months IS NULL OR installment_months IN (3, 6, 12)",
            name="ck_payments_installment_months",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    tariff_id: Mapped[str] = mapped_column(ForeignKey("tariffs.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    installment_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    tariff: Mapped[Tariff] = relationship(back_populates="payments")
