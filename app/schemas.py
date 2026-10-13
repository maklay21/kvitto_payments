from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

PaymentMethod = Literal["card", "sbp", "installment"]
PaymentStatus = Literal["pending", "succeeded", "failed", "refunded"]


class TariffRead(BaseModel):
    id: str
    title: str
    price: int

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    tariff_id: str = Field(min_length=1, max_length=32)
    email: EmailStr
    method: PaymentMethod
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_installment_fields(self) -> "PaymentCreate":
        if self.method == "installment" and self.installment_months is None:
            raise ValueError("installment_months is required for installment payments")
        if self.method != "installment" and self.installment_months is not None:
            raise ValueError("installment_months is only valid for installment payments")
        return self


class PaymentRead(BaseModel):
    id: str
    status: PaymentStatus
    tariff_id: str
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankWebhook(BaseModel):
    payment_id: str = Field(min_length=1, max_length=36)
    status: PaymentStatus
