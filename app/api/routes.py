import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Tariff
from app.schemas import BankWebhook, PaymentCreate, PaymentRead, PaymentStatus, TariffRead
from app.services import (
    InvalidTransitionError,
    UnknownPromoCodeError,
    apply_bank_webhook,
    create_payment,
    get_payment,
    list_payments,
)

router = APIRouter()
logger = logging.getLogger("app.payments")


@router.get("/tariffs", response_model=list[TariffRead])
def get_tariffs(db: Session = Depends(get_db)) -> list[Tariff]:
    """
    Эндпоинт получения актуальных тарифов.

    :param db:
    :return: list[Tariff]
    """
    return list(db.scalars(select(Tariff).order_by(Tariff.price)).all())


@router.post("/payments", response_model=PaymentRead)
def post_payment(
    payload: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    db: Session = Depends(get_db),
) -> PaymentRead:
    """
    Эндпоинт создания платежа. Проверяет идемпотентность
    платежа, валдность формы запроса.

    :param payload:
    :param response:
    :param idempotency_key:
    :param db:
    :return: PaymentRead
    """

    try:
        payment, created = create_payment(db, payload, idempotency_key)
    except LookupError as error:
        logger.warning(
            "Payment creation rejected: tariff not found (tariff_id=%s)", payload.tariff_id
        )
        raise HTTPException(status_code=404, detail="tariff_not_found") from error
    except UnknownPromoCodeError as error:
        logger.warning(
            "Payment creation rejected: unknown promo code (tariff_id=%s)", payload.tariff_id
        )
        raise HTTPException(status_code=422, detail="unknown_promo_code") from error
    except Exception:
        logger.exception(
            "Unexpected error while creating payment (tariff_id=%s)", payload.tariff_id
        )
        raise

    if created:
        logger.info(
            "Payment created (payment_id=%s tariff_id=%s amount=%s method=%s)",
            payment.id,
            payment.tariff_id,
            payment.amount,
            payment.method,
        )
    else:
        logger.info(
            "Idempotent payment request returned existing payment (payment_id=%s)", payment.id
        )

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return PaymentRead.model_validate(payment)


@router.get("/payments", response_model=list[PaymentRead])
def get_payments(
    email: str | None = Query(default=None),
    payment_status: PaymentStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[PaymentRead]:
    """
    Эндпоинт получения платежа c параметрами поиска.

    :param email:
    :param payment_status:
    :param db:
    :return: list[PaymentRead]
    """

    return [PaymentRead.model_validate(p) for p in list_payments(db, email, payment_status)]


@router.get("/payments/{payment_id}", response_model=PaymentRead)
def get_payment_by_id(payment_id: str, db: Session = Depends(get_db)) -> PaymentRead:
    """
    Эндпоинт получения платежа по id.

    :param payment_id:
    :param db:
    :return: PaymentRead
    """

    payment = get_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")

    return PaymentRead.model_validate(payment)


def _verify_signature(body: bytes, supplied_signature: str | None) -> bool:
    """
    Функция верификации сигнатуры вебхука.

    :param body:
    :param supplied_signature:
    :return: bool
    """

    secret = settings.webhook_secret
    if not secret:
        return True
    if not supplied_signature:
        return False

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    signature = supplied_signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/bank")
async def bank_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Вебхук уведомления от банка. Принимает сигнатуру с секретным ключом,
    валидирует ее, изменяет состояние платежа.

    :param request:
    :param x_signature:
    :param db:
    :return: JSONResponse
    """

    logger.info("Bank webhook received")
    raw_body = await request.body()
    if not _verify_signature(raw_body, x_signature):
        logger.warning("Bank webhook rejected: invalid signature")
        raise HTTPException(status_code=401, detail="invalid_signature")
    try:
        payload = BankWebhook.model_validate_json(raw_body)
    except (ValueError, json.JSONDecodeError) as error:
        logger.warning("Bank webhook rejected: invalid payload")
        raise HTTPException(status_code=422, detail="invalid_webhook_payload") from error
    try:
        apply_bank_webhook(db, payload)
    except LookupError as error:
        logger.warning(
            "Bank webhook references missing payment (payment_id=%s status=%s)",
            payload.payment_id,
            payload.status,
        )
        raise HTTPException(status_code=404, detail="payment_not_found") from error
    except InvalidTransitionError:
        logger.warning(
            "Bank webhook rejected: invalid status transition (payment_id=%s requested_status=%s)",
            payload.payment_id,
            payload.status,
        )
        return JSONResponse(status_code=409, content={"error": "invalid_transition"})
    except Exception:
        logger.exception(
            "Unexpected error while processing bank webhook (payment_id=%s)", payload.payment_id
        )
        raise

    logger.info(
        "Bank webhook processed (payment_id=%s status=%s)", payload.payment_id, payload.status
    )
    return JSONResponse(status_code=200, content={"result": "ok"})
