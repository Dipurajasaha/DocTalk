from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VENV_SITE_PACKAGES = ROOT / ".venv" / "Lib" / "site-packages"
if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

from backend.workflows.executor.capability_registry import handle_appointment_book
from backend.workflows.memory.conversation_memory import ConversationMemoryManager
from backend.workflows.planner.llm_planner import LLMPlanningEngine


class FakePaymentService:
    def __init__(self, client):
        self.client = client
        self.created_order: dict[str, object] | None = None
        self.appointment = None

    async def release_expired_payment_holds(self) -> int:
        return 0

    async def create_order_for_appointment(
        self, *, patient_id, appointment_type, doctor_id, slot_id, reason, note
    ):
        slot = self.client._slot
        doctor = self.client._doctor
        appointment_id = "appt_test_123"
        self.appointment = SimpleNamespace(
            id=appointment_id,
            patientUsername=patient_id,
            doctorId=doctor_id,
            slotId=slot_id,
            appointmentDate=slot.startTime,
            doctor=doctor,
            slot=slot,
            payment=SimpleNamespace(
                id="pay_test_123",
                razorpayOrderId="order_test_123",
                amountPaise=50000,
                currency="INR",
                status="CREATED",
            ),
            amountPaise=50000,
            status="PAYMENT_PENDING",
        )
        self.created_order = {
            "order_id": "order_test_123",
            "amount": 50000,
            "currency": "INR",
            "key_id": "rzp_test_key",
            "appointment_id": appointment_id,
            "doctor_id": doctor_id,
            "slot_id": slot_id,
        }
        return dict(self.created_order)

    async def get_pending_payment_order(self, appointment_id: str, patient_id: str):
        if not self.created_order:
            raise RuntimeError("missing fake order")
        return dict(self.created_order)


class FakePrisma:
    def __init__(self):
        self._doctor = SimpleNamespace(
            doctorId="docdipu", name="DocDipu", consultationFee=50000
        )
        self._slot = SimpleNamespace(
            id="slot_test_123",
            doctorId="docdipu",
            startTime=datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc),
            isBooked=False,
            isActive=True,
            doctor=self._doctor,
        )
        self.doctor = SimpleNamespace(
            find_many=AsyncMock(return_value=[self._doctor]),
        )
        self.doctorslot = SimpleNamespace(
            find_many=AsyncMock(return_value=[self._slot]),
            update=AsyncMock(return_value=self._slot),
            find_unique=AsyncMock(return_value=self._slot),
        )
        self.appointment = SimpleNamespace(
            find_unique=AsyncMock(side_effect=self._find_unique),
        )
        self._service: FakePaymentService | None = None

    async def _find_unique(self, **kwargs):
        if self._service is not None:
            return self._service.appointment
        return None


async def main() -> int:
    fake_prisma = FakePrisma()
    fake_service = FakePaymentService(fake_prisma)
    fake_prisma._service = fake_service

    initial_state = {
        "user_id": "patient_test",
        "target_patient_id": "patient_test",
        "planner_metadata": {
            "active_workflow": {
                "type": "appointment_booking",
                "status": "waiting_confirmation",
                "context": {
                    "doctor_name": "DocDipu",
                    "doctor_id": "docdipu",
                    "selection_type": "first",
                },
            }
        },
        "doctor_availability_context": [
            {"doctor_id": "docdipu", "doctor_name": "DocDipu"}
        ],
    }

    with patch(
        "backend.workflows.executor.capability_registry.prisma", fake_prisma
    ), patch(
        "backend.workflows.executor.capability_registry.ensure_connected",
        AsyncMock(return_value=None),
    ), patch(
        "backend.services.payment_service.PaymentService",
        new=lambda client: fake_service,
    ):
        first = await handle_appointment_book(
            initial_state, {"doctor_name": "DocDipu", "booking_ordinal": "first"}
        )

        assert first.data["action"] == "confirm_payment", first.data
        assert first.data["payment_order"]["order_id"] == "order_test_123", first.data
        assert first.data["active_workflow"]["context"]["appointment_id"] == "appt_test_123", first.data
        assert (
            first.data["active_workflow"]["context"]["slot_id"] == "slot_test_123"
        ), first.data
        assert first.data["active_workflow"]["context"]["amount"] == 50000, first.data
        assert first.data["active_workflow"]["context"]["currency"] == "INR", first.data
        assert first.data["active_workflow"]["context"]["payment_stage"] == "payment_pending", first.data
        assert (
            first.data["active_workflow"]["context"]["booking_ordinal"] == "first"
        ), first.data
        assert first.data["active_workflow"]["status"] == "waiting_payment_confirmation", first.data

        memory_state = {
            "conversation_memory": {},
            "planner_metadata": {
                "query_type": "workflow",
                "active_workflow": first.data["active_workflow"],
            },
        }
        memory_manager = ConversationMemoryManager(memory_state)
        updated_memory = memory_manager.update(
            {
                "planner_metadata": memory_state["planner_metadata"],
            }
        )
        hydrated_state = {
            "conversation_memory": updated_memory,
            "planner_metadata": ConversationMemoryManager(
                {
                    "conversation_memory": updated_memory,
                    "planner_metadata": {},
                }
            ).hydrate_planner_metadata(),
            "doctor_availability_context": [
                {"doctor_id": "docdipu", "doctor_name": "DocDipu"}
            ],
            "user_id": "patient_test",
            "target_patient_id": "patient_test",
        }

        assert (
            hydrated_state["planner_metadata"]["active_workflow"]["context"]["slot_id"]
            == "slot_test_123"
        ), hydrated_state
        assert (
            hydrated_state["planner_metadata"]["active_workflow"]["context"]["amount"]
            == 50000
        ), hydrated_state
        assert (
            hydrated_state["planner_metadata"]["active_workflow"]["context"]["currency"]
            == "INR"
        ), hydrated_state
        assert (
            hydrated_state["planner_metadata"]["active_workflow"]["context"][
                "booking_ordinal"
            ]
            == "first"
        ), hydrated_state
        hydrated_state["planner_metadata"]["payment_confirmation_requested"] = True

        second = await handle_appointment_book(
            hydrated_state, {"doctor_name": "DocDipu", "booking_ordinal": "first"}
        )

        assert second.data["action"] == "open_razorpay", second.data
        assert second.data["payment_order"]["order_id"] == "order_test_123", second.data
        assert (
            second.data["payment_order"]["appointment_id"] == "appt_test_123"
        ), second.data
        assert (
            second.data["payment_order"]["slot_id"] == "slot_test_123"
        ), second.data
        assert (
            second.data["active_workflow"]["context"]["appointment_id"]
            == "appt_test_123"
        ), second.data
        assert (
            second.data["active_workflow"]["context"]["slot_id"] == "slot_test_123"
        ), second.data

        success_state = {
            "user_id": "patient_test",
            "target_patient_id": "patient_test",
            "planner_metadata": {
                "active_workflow": second.data["active_workflow"],
                "payment_successful": True,
            },
            "payment_order": second.data["payment_order"],
        }
        success = await handle_appointment_book(
            success_state,
            {
                "doctor_name": "DocDipu",
                "booking_ordinal": "first",
                "payment_successful": True,
            },
        )

        assert success.data["action"] == "confirmed", success.data
        assert "confirmed" in success.data["message"].lower(), success.data
        assert success.data["active_workflow"]["status"] == "completed", success.data
        assert success.data["active_workflow"]["context"]["appointment_id"] == "appt_test_123", success.data

        planner_state = {
            "messages": [SimpleNamespace(content="payment successful")],
            "planner_metadata": {
                "active_workflow": second.data["active_workflow"],
                "payment_order": second.data["payment_order"],
            },
            "active_workflow": second.data["active_workflow"],
            "payment_order": second.data["payment_order"],
            "payment_successful": True,
        }
        plan = await LLMPlanningEngine(planner_state).execute()
        assert plan.tasks and plan.tasks[0].capability_name == "APPOINTMENT_BOOK", plan.model_dump()
        assert plan.tasks[0].parameters.get("payment_successful") is True, plan.model_dump()
        assert plan.metadata["payment_successful"] is True, plan.model_dump()

    print(
        json.dumps(
            {
                "status": "PASS",
                "first_action": first.data["action"],
                "second_action": second.data["action"],
                "third_action": success.data["action"],
                "payment_order_hidden_on_first_turn": True,
                "payment_order_opened_only_after_confirmation": True,
                "payment_successful_forces_confirmation_plan": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
