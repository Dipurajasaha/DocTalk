"""Razorpay payment API routes.

Endpoints
---------
POST /api/payments/create-order   – Patient initiates payment for an appointment
POST /api/payments/verify         – Frontend reports successful checkout; server verifies HMAC
POST /api/payments/webhook        – Razorpay sends server-side payment events
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from ..core.security import CurrentUser, get_current_user
from ..schemas.payment_schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    RetryOrderRequest,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    WebhookResponse,
)
from ..services.payment_service import PaymentService


router = APIRouter()


def get_payment_service() -> PaymentService:
    return PaymentService()


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    payload: CreateOrderRequest,
    current_user: CurrentUser = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> CreateOrderResponse:
    """
    Create a Razorpay order and a provisional appointment (PAYMENT_PENDING).

    The frontend receives the order details and opens the Razorpay checkout popup.
    The appointment is confirmed only after payment verification.
    """
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")

    result = await payment_service.create_order_for_appointment(
        patient_id=current_user.user_id,
        appointment_type=payload.appointment_type,
        doctor_id=payload.doctor_id,
        slot_id=payload.slot_id,
        reason=payload.reason,
        note=payload.note,
    )
    return CreateOrderResponse.model_validate(result)


@router.post("/retry-order", response_model=CreateOrderResponse)
async def retry_order(
    payload: RetryOrderRequest,
    current_user: CurrentUser = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> CreateOrderResponse:
    """
    Creates a new Razorpay order for an existing PAYMENT_PENDING appointment.
    """
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")

    result = await payment_service.retry_payment_order(
        appointment_id=payload.appointment_id,
        patient_id=current_user.user_id,
    )
    return CreateOrderResponse.model_validate(result)


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    payload: VerifyPaymentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> VerifyPaymentResponse:
    """
    Verify the HMAC-SHA256 signature returned by Razorpay checkout.

    On success the appointment transitions from PAYMENT_PENDING to:
    - CONFIRMED  (direct / slot booking)
    - PENDING    (open request — doctor still needs to accept)
    """
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")

    result = await payment_service.verify_payment(
        appointment_id=payload.appointment_id,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
        patient_id=current_user.user_id,
    )
    return VerifyPaymentResponse.model_validate(result)


@router.post("/webhook", response_model=WebhookResponse)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default="", alias="X-Razorpay-Signature"),
    payment_service: PaymentService = Depends(get_payment_service),
) -> WebhookResponse:
    """
    Razorpay server-to-server webhook.

    Configured in the Razorpay Dashboard → Webhooks.
    Set RAZORPAY_WEBHOOK_SECRET in .env to enable signature verification
    (highly recommended for production).
    """
    payload_bytes = await request.body()
    result = await payment_service.process_webhook(payload_bytes, x_razorpay_signature)
    return WebhookResponse.model_validate(result)
