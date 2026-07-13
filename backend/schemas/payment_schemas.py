"""Pydantic schemas for the Razorpay payment flow."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CreateOrderRequest(BaseModel):
    """Body sent by the patient when they click 'Proceed to Pay'."""

    model_config = ConfigDict(extra="forbid")

    # Booking mode: 'direct' (slot) or 'open' (request)
    appointment_type: str = Field(default="direct", pattern="^(direct|open)$")
    doctor_id: str = Field(min_length=1)
    slot_id: str | None = None        # Required for direct booking
    reason: str = Field(min_length=1)
    note: str | None = None


class CreateOrderResponse(BaseModel):
    """Returned to the frontend so it can open the Razorpay checkout popup."""

    model_config = ConfigDict(extra="forbid")

    order_id: str           # Razorpay order ID (rzp_order_…)
    amount: int             # Amount in paise
    currency: str
    key_id: str             # Public key — safe to send to frontend
    appointment_id: str     # DB appointment ID created alongside the order


class RetryOrderRequest(BaseModel):
    """Body sent when patient clicks Pay Now on an existing pending appointment."""
    model_config = ConfigDict(extra="forbid")
    appointment_id: str

class VerifyPaymentRequest(BaseModel):
    """Sent by the frontend after the Razorpay popup resolves successfully."""

    model_config = ConfigDict(extra="forbid")

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    appointment_id: str


class VerifyPaymentResponse(BaseModel):
    """Returned after successful signature verification."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    appointment_id: str
    status: str
    message: str = "Payment verified successfully"


class WebhookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received: bool = True
