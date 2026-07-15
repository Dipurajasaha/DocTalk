from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.workflows.graph.state import create_workflow_state
from backend.workflows.llm.llm_orchestrator import llm_orchestrator_node
from backend.workflows.models.capability_result import CapabilityResult
from backend.workflows.models.execution_context import ExecutionContext
from backend.workflows.models.planner_task import PlannerTask


def _build_fake_payment_order() -> dict[str, Any]:
    return {
        "order_id": "order_test_123",
        "amount": 50000,
        "currency": "INR",
        "key_id": "rzp_test_key",
        "appointment_id": "appt_test_123",
    }


async def main() -> int:
    fake_order = _build_fake_payment_order()
    fake_result = CapabilityResult(
        capability_name="APPOINTMENT_BOOK",
        status="SUCCESS",
        data={"payment_order": fake_order, "message": "Opening payment window now."},
        metadata={"payment_order": fake_order, "clear_doctor_availability": True},
        evidence=[{"source": "APPOINTMENT_BOOK", "type": "appointment", "content": "test"}],
    )
    task = PlannerTask(task_type="action", action_handler="APPOINTMENT_BOOK", parameters={})

    ctx = ExecutionContext()
    ctx.merge_result(task, fake_result)

    assert ctx.shared_context.get("payment_order") == fake_order, "ExecutionContext did not keep payment_order"
    assert ctx.metadata.get("payment_order") == fake_order, "ExecutionContext metadata did not keep payment_order"

    result_dict = {
        "memory_context": [],
        "appointment_context": {},
        "consultation_context": [],
        "asset_selection_context": {},
        "rag_scope": {},
        "patient_history_context": [],
        "doctor_availability_context": [],
        "pending_tasks": [],
        "evidence": ctx.evidence,
        "payment_order": ctx.metadata["payment_order"],
    }

    assert result_dict.get("payment_order") == fake_order, "payment_order did not reach the executor result payload"

    state = create_workflow_state(
        messages=[],
        role="patient",
        user_id="patient_test",
        ai_session_id="patient_ai_test",
        payment_order=fake_order,
        final_response="Opening payment window now.",
    )
    response = await llm_orchestrator_node(state)
    assert response.get("payment_order") == fake_order, "llm_orchestrator_node did not preserve payment_order"

    print(json.dumps({
        "status": "PASS",
        "payment_order": fake_order,
        "executor_payload_has_payment_order": True,
        "orchestrator_preserved_payment_order": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
