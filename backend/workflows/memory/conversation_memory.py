import copy
from typing import Any
from ..graph.state import UnifiedChatState
from ..utils.logger import log_section, log_key_value


class ConversationMemoryManager:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.memory = copy.deepcopy(state.get("conversation_memory") or {})

        # Ensure base structure
        if "workflow" not in self.memory:
            self.memory["workflow"] = {}
        if "semantic" not in self.memory:
            self.memory["semantic"] = {}
        if "short_term" not in self.memory:
            self.memory["short_term"] = {}
        if "recommendation" not in self.memory:
            self.memory["recommendation"] = {}

    def hydrate_planner_metadata(self) -> dict[str, Any]:
        """Reads from conversation_memory to populate planner_metadata for the next turn."""
        metadata = dict(self.state.get("planner_metadata") or {})
        metadata.pop("payment_successful", None)

        hydrated = []
        terminal_workflow = False

        # Hydrate workflow state
        workflow = self.memory.get("workflow", {})
        if workflow:
            print(
                f"[DEBUG][MEMORY][HYDRATE] workflow_keys={sorted(list(workflow.keys()))}"
            )
        if "active_workflow" in workflow:
            active_workflow = copy.deepcopy(workflow["active_workflow"])
            if isinstance(active_workflow, dict):
                status = str(active_workflow.get("status") or "").strip().lower()
                if status in {"completed", "confirmed", "cancelled"}:
                    active_workflow = None
                    terminal_workflow = True
            if isinstance(active_workflow, dict):
                ctx = active_workflow.setdefault("context", {})
                if (
                    "doctor_name" in workflow
                    and workflow["doctor_name"]
                    and not ctx.get("doctor_name")
                ):
                    ctx["doctor_name"] = workflow["doctor_name"]
                if (
                    "appointment_id" in workflow
                    and workflow["appointment_id"]
                    and not ctx.get("appointment_id")
                ):
                    ctx["appointment_id"] = workflow["appointment_id"]
                if (
                    "slot_id" in workflow
                    and workflow["slot_id"]
                    and not ctx.get("slot_id")
                ):
                    ctx["slot_id"] = workflow["slot_id"]
                if (
                    "amount" in workflow
                    and workflow["amount"] is not None
                    and not ctx.get("amount")
                ):
                    ctx["amount"] = workflow["amount"]
                if (
                    "currency" in workflow
                    and workflow["currency"]
                    and not ctx.get("currency")
                ):
                    ctx["currency"] = workflow["currency"]
                if (
                    "booking_datetime" in workflow
                    and workflow["booking_datetime"]
                    and not ctx.get("appointment_time")
                ):
                    ctx["appointment_time"] = workflow["booking_datetime"]
                if (
                    "booking_datetime" in workflow
                    and workflow["booking_datetime"]
                    and not ctx.get("booking_datetime")
                ):
                    ctx["booking_datetime"] = workflow["booking_datetime"]
                if (
                    "booking_ordinal" in workflow
                    and workflow["booking_ordinal"]
                    and not ctx.get("selection_type")
                ):
                    ctx["selection_type"] = workflow["booking_ordinal"]
                if (
                    "booking_ordinal" in workflow
                    and workflow["booking_ordinal"]
                    and not ctx.get("booking_ordinal")
                ):
                    ctx["booking_ordinal"] = workflow["booking_ordinal"]
            metadata["active_workflow"] = active_workflow
            hydrated.append("active_workflow")

        if terminal_workflow:
            for key in [
                "doctor_name",
                "booking_datetime",
                "booking_ordinal",
                "appointment_id",
                "slot_id",
                "amount",
                "currency",
            ]:
                metadata.pop(key, None)
        elif "doctor_name" in workflow:
            metadata["doctor_name"] = workflow["doctor_name"]
            hydrated.append("doctor_name")

        if not terminal_workflow and "booking_datetime" in workflow:
            metadata["booking_datetime"] = workflow["booking_datetime"]
            hydrated.append("booking_datetime")

        if not terminal_workflow and "booking_ordinal" in workflow:
            metadata["booking_ordinal"] = workflow["booking_ordinal"]
            hydrated.append("booking_ordinal")

        # Hydrate recommendation state
        recommendation = self.memory.get("recommendation", {})
        if "recommended_specialty" in recommendation:
            metadata["recommended_specialty"] = recommendation["recommended_specialty"]
            hydrated.append("recommended_specialty")
        if "recommended_doctor_id" in recommendation:
            metadata["recommended_doctor_id"] = recommendation["recommended_doctor_id"]
            hydrated.append("recommended_doctor_id")
        if "recommended_doctor_name" in recommendation:
            metadata["recommended_doctor_name"] = recommendation[
                "recommended_doctor_name"
            ]
            hydrated.append("recommended_doctor_name")

        # Hydrate semantic state
        semantic = self.memory.get("semantic", {})
        # Note: we don't stuff doctor_availability_context into planner_metadata,
        # but the executor might need it later. For now, just hydrate metadata.

        if hydrated:
            log_section("MEMORY")
            log_key_value("Hydrated", hydrated)
            if isinstance(metadata.get("active_workflow"), dict):
                aw_ctx = metadata["active_workflow"].get("context", {})
                log_key_value(
                    "Hydrated Workflow Context",
                    {
                        "status": metadata["active_workflow"].get("status"),
                        "appointment_id": aw_ctx.get("appointment_id"),
                        "slot_id": aw_ctx.get("slot_id"),
                        "amount": aw_ctx.get("amount"),
                        "currency": aw_ctx.get("currency"),
                        "booking_datetime": aw_ctx.get("booking_datetime")
                        or aw_ctx.get("appointment_time"),
                        "booking_ordinal": aw_ctx.get("booking_ordinal")
                        or aw_ctx.get("selection_type"),
                    },
                )

        return metadata

    def update(self, result_dict: dict[str, Any]) -> dict[str, Any]:
        """Updates memory based on executor results and applies expiration."""
        updated = []
        expired = []

        workflow = self.memory.setdefault("workflow", {})
        semantic = self.memory.setdefault("semantic", {})
        recommendation = self.memory.setdefault("recommendation", {})

        # 1. Update Workflow memory from planner_metadata (if Executor preserved it)
        pmeta = result_dict.get(
            "planner_metadata", self.state.get("planner_metadata", {})
        )
        is_workflow_query = pmeta.get("query_type") in ("workflow", "appointment")
        if isinstance(pmeta.get("active_workflow"), dict):
            aw_ctx = pmeta["active_workflow"].get("context", {})
            print(
                "[DEBUG][MEMORY][UPDATE] "
                f"status={pmeta['active_workflow'].get('status')} "
                f"appointment_id={aw_ctx.get('appointment_id')} "
                f"slot_id={aw_ctx.get('slot_id')} "
                f"amount={aw_ctx.get('amount')} "
                f"currency={aw_ctx.get('currency')}"
            )

        # If executor explicitly cleared active_workflow, or it's a workflow query and it's gone
        if "active_workflow" not in pmeta and "active_workflow" in workflow:
            if is_workflow_query:
                workflow.pop("active_workflow", None)
                workflow.pop("doctor_name", None)
                workflow.pop("booking_datetime", None)
                workflow.pop("booking_ordinal", None)
                expired.append("active_workflow")
                expired.append("workflow_context")
                # Also expire recommendation if workflow finished
                if "recommended_specialty" in recommendation:
                    recommendation.clear()
                    expired.append("recommendation")
            else:
                pass  # Preserve workflow memory for unrelated tangents
        elif "active_workflow" in pmeta:
            workflow["active_workflow"] = copy.deepcopy(pmeta["active_workflow"])
            updated.append("active_workflow")

            # Extract items from active_workflow context
            ctx = (
                workflow["active_workflow"].setdefault("context", {})
                if isinstance(workflow["active_workflow"], dict)
                else {}
            )
            if "doctor_name" in ctx and ctx["doctor_name"]:
                workflow["doctor_name"] = ctx["doctor_name"]
                if "doctor_name" not in updated:
                    updated.append("doctor_name")
            if "appointment_id" in ctx and ctx["appointment_id"]:
                workflow["appointment_id"] = ctx["appointment_id"]
                if "appointment_id" not in updated:
                    updated.append("appointment_id")
            if "slot_id" in ctx and ctx["slot_id"]:
                workflow["slot_id"] = ctx["slot_id"]
                if "slot_id" not in updated:
                    updated.append("slot_id")
            if "amount" in ctx and ctx["amount"] is not None:
                workflow["amount"] = ctx["amount"]
                if "amount" not in updated:
                    updated.append("amount")
            if "currency" in ctx and ctx["currency"]:
                workflow["currency"] = ctx["currency"]
                if "currency" not in updated:
                    updated.append("currency")
            if "booking_datetime" in ctx and ctx["booking_datetime"]:
                workflow["booking_datetime"] = ctx["booking_datetime"]
                if "booking_datetime" not in updated:
                    updated.append("booking_datetime")
            if "appointment_time" in ctx and ctx["appointment_time"]:
                workflow["booking_datetime"] = ctx["appointment_time"]
                if "booking_datetime" not in updated:
                    updated.append("booking_datetime")
            if "booking_ordinal" in ctx and ctx["booking_ordinal"]:
                workflow["booking_ordinal"] = ctx["booking_ordinal"]
                if "booking_ordinal" not in updated:
                    updated.append("booking_ordinal")
            if "selection_type" in ctx and ctx["selection_type"]:
                workflow["booking_ordinal"] = ctx["selection_type"]
                if "booking_ordinal" not in updated:
                    updated.append("booking_ordinal")

            if isinstance(workflow.get("active_workflow"), dict):
                aw_ctx = workflow["active_workflow"].setdefault("context", {})
                if "doctor_name" in ctx and ctx["doctor_name"]:
                    aw_ctx["doctor_name"] = ctx["doctor_name"]
                if "appointment_id" in ctx and ctx["appointment_id"]:
                    aw_ctx["appointment_id"] = ctx["appointment_id"]
                if "slot_id" in ctx and ctx["slot_id"]:
                    aw_ctx["slot_id"] = ctx["slot_id"]
                if "amount" in ctx and ctx["amount"] is not None:
                    aw_ctx["amount"] = ctx["amount"]
                if "currency" in ctx and ctx["currency"]:
                    aw_ctx["currency"] = ctx["currency"]
                if "booking_datetime" in ctx and ctx["booking_datetime"]:
                    aw_ctx["booking_datetime"] = ctx["booking_datetime"]
                if "appointment_time" in ctx and ctx["appointment_time"]:
                    aw_ctx["appointment_time"] = ctx["appointment_time"]
                if "booking_ordinal" in ctx and ctx["booking_ordinal"]:
                    aw_ctx["booking_ordinal"] = ctx["booking_ordinal"]
                if "selection_type" in ctx and ctx["selection_type"]:
                    aw_ctx["selection_type"] = ctx["selection_type"]

            if isinstance(workflow.get("active_workflow"), dict):
                aw_ctx = workflow["active_workflow"].get("context", {})
                print(
                    "[DEBUG][MEMORY][UPDATED_WORKFLOW] "
                    f"status={workflow['active_workflow'].get('status')} "
                    f"appointment_id={aw_ctx.get('appointment_id')} "
                    f"slot_id={aw_ctx.get('slot_id')} "
                    f"amount={aw_ctx.get('amount')} "
                    f"currency={aw_ctx.get('currency')}"
                )

        # 2. Update Semantic memory (e.g., doctor_availability_context)
        if "doctor_availability_context" in result_dict:
            avail = result_dict["doctor_availability_context"]
            if avail:
                semantic["doctor_availability_context"] = avail
                updated.append("doctor_availability_context")
            elif "doctor_availability_context" in semantic:
                semantic.pop("doctor_availability_context", None)
                expired.append("doctor_availability_context")

        # 3. Update Recommendation memory
        if "recommendation_context" in result_dict:
            rec = result_dict["recommendation_context"]
            if rec:
                recommendation.update(rec)
                updated.append("recommendation")

        if updated or expired:
            log_section("MEMORY")
            log_key_value("Updated", updated if updated else "none")
            log_key_value("Expired", expired if expired else "none")

        return self.memory
