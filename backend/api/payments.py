from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.security import CurrentUser, get_current_user
from ..services.payment_service import PaymentService


router = APIRouter()


def get_payment_service() -> PaymentService:
    return PaymentService()


# ─── Request / Response Schemas ───────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    amount: float = Field(gt=0, description="Amount in ₹ (e.g. 500 for ₹500)")
    description: str = Field(min_length=1, max_length=255, default="Appointment Consultation Fee")
    appointment_id: str | None = None

    class Config:
        extra = "forbid"


class CreateOrderResponse(BaseModel):
    payment_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount: int  # in paise
    currency: str
    description: str

    class Config:
        extra = "ignore"


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

    class Config:
        extra = "forbid"


class VerifyPaymentResponse(BaseModel):
    success: bool
    payment_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    status: str

    class Config:
        extra = "ignore"


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/create-order", response_model=CreateOrderResponse)
async def create_payment_order(
    payload: CreateOrderRequest,
    current_user: CurrentUser = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> CreateOrderResponse:
    """Create a Razorpay order to initiate payment. Only patients can initiate payments."""
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can create payment orders")

    result = await payment_service.create_order(
        patient_username=current_user.user_id,
        amount_inr=payload.amount,
        description=payload.description,
        appointment_id=payload.appointment_id,
    )
    return CreateOrderResponse(**result)


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    payload: VerifyPaymentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> VerifyPaymentResponse:
    """Verify Razorpay payment signature and mark payment as PAID."""
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can verify payments")

    result = await payment_service.verify_payment(
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
        patient_username=current_user.user_id,
    )
    return VerifyPaymentResponse(**result)


@router.get("/my-payments")
async def list_my_payments(
    current_user: CurrentUser = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> list[dict]:
    """List payments for the current user."""
    if current_user.role == "patient":
        return await payment_service.list_patient_payments(current_user.user_id)
    if current_user.role == "doctor":
        return await payment_service.list_doctor_payments(current_user.user_id)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot view payments here")
