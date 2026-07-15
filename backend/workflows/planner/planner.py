from __future__ import annotations
from typing import Any

from ..graph.common import latest_message_text
from ..graph.state import UnifiedChatState
from .parsers.intent_parser import parse_intent, ParsedIntent
from .parsers.document_query_parser import parse_document_query
from ..models.planner_task import PlannerTask
from ..models.execution_plan import ExecutionPlan
from ..models.resolved_context import ResolvedContext
from ..models.active_workflow import ActiveWorkflow
from .planner_rule_config import (
    APPOINTMENT_RULE_CONFIG,
    CONSULTATION_RULE_CONFIG,
    PATIENT_HISTORY_RULE_CONFIG,
)
from .context_resolver import ContextResolver


class PlanningEngine:
    def __init__(self, state: UnifiedChatState):
        self.state = state
        self.text = latest_message_text(state.get("messages") or []).lower()
        self.plan = ExecutionPlan()

        previous_metadata = dict(state.get("planner_metadata") or {})
        incoming_active_workflow = state.get("active_workflow")
        if isinstance(incoming_active_workflow, dict):
            previous_metadata["active_workflow"] = incoming_active_workflow
        incoming_payment_order = state.get("payment_order")
        if isinstance(incoming_payment_order, dict):
            previous_metadata["payment_order"] = incoming_payment_order
        previous_metadata.pop("payment_successful", None)
        prev_wf_dict = previous_metadata.get("active_workflow")
        active_wf = ActiveWorkflow.from_dict(prev_wf_dict)
        self.current_payment_successful = bool(
            (state.get("context_payload") or {}).get("payment_successful")
            or "payment successful" in self.text
            or "payment complete" in self.text
            or "payment completed" in self.text
            or "paid successfully" in self.text
        )
        wf_ctx = (
            active_wf.context
            if (active_wf and active_wf.status not in ("cancelled", "completed", "confirmed"))
            else {}
        )

        doc_name_from_avail = None
        avail_context = state.get("doctor_availability_context") or []
        for avail in avail_context:
            if isinstance(avail, dict) and avail.get("doctor_name"):
                doc_name_from_avail = avail["doctor_name"]
                break

        self.plan.metadata = {
            "query_type": previous_metadata.get("query_type", "general"),
            "detected_entities": previous_metadata.get("detected_entities", []),
            "detected_actions": [],
            "doctor_name": wf_ctx.get("doctor_name")
            or previous_metadata.get("doctor_name")
            or doc_name_from_avail,
            "booking_datetime": wf_ctx.get("appointment_time")
            or wf_ctx.get("selected_slot")
            or previous_metadata.get("booking_datetime"),
            "booking_ordinal": wf_ctx.get("selection_type")
            or previous_metadata.get("booking_ordinal"),
            "appointment_id": wf_ctx.get("appointment_id")
            or previous_metadata.get("appointment_id"),
            "slot_id": wf_ctx.get("slot_id") or previous_metadata.get("slot_id"),
            "amount": wf_ctx.get("amount") or previous_metadata.get("amount"),
            "currency": wf_ctx.get("currency") or previous_metadata.get("currency"),
            "active_workflow": (
                active_wf.to_dict()
                if (active_wf and active_wf.status not in ("cancelled", "completed", "confirmed"))
                else None
            ),
        }
        # filter out Nones
        self.plan.metadata = {
            k: v for k, v in self.plan.metadata.items() if v is not None
        }
        self.intent: ParsedIntent | None = None
        self.resolved_context: ResolvedContext | None = None

    def determine_goal(self):
        self.intent = parse_intent(self.text)
        res_ctx = self.resolved_context
        self.plan.metadata.pop("payment_confirmation_requested", None)

        # Check cancellation patterns ("never mind", "cancel this", "abort", "forget it", "don't book", "stop")
        is_workflow_cancellation = any(
            k in self.text
            for k in [
                "never mind",
                "nevermind",
                "cancel this",
                "abort",
                "forget it",
                "don't book",
                "stop booking",
            ]
        )
        if is_workflow_cancellation:
            self.plan.metadata["active_workflow"] = None
            self.resolved_context = ResolvedContext(has_reference=False)
            res_ctx = self.resolved_context

        # Explicit patient appointment requests
        is_explicit_patient_appointment = any(
            k in self.text
            for k in [
                "my appointment",
                "my appointments",
                "list my",
                "show my",
                "my upcoming",
                "cancel my",
                "reschedule my",
            ]
        ) or (
            any(
                a in self.intent.actions
                for a in ["cancel", "reschedule", "list", "upcoming"]
            )
            and (
                "my" in self.text
                or "appointment" in self.text
                or self.intent.is_appointment
            )
            and not any(
                k in self.text
                for k in ["availability", "available", "doctor", "dr.", "dr "]
            )
        )

        # Booking confirmation via active_workflow or resolved context
        active_wf_dict = self.plan.metadata.get("active_workflow")
        active_wf = ActiveWorkflow.from_dict(active_wf_dict) if active_wf_dict else None

        is_booking_confirmation = False
        if is_workflow_cancellation:
            is_booking_confirmation = False
        elif res_ctx and res_ctx.has_reference and res_ctx.reference_type == "ordinal":
            # Ordinal selection ("book the first available slot") proposes candidate, does NOT confirm yet
            is_booking_confirmation = False
        elif active_wf and active_wf.status in (
            "waiting_confirmation",
            "waiting_payment_confirmation",
        ):
            if self.current_payment_successful or (
                res_ctx and (
                    res_ctx.reference_type == "affirmation"
                    or "yes" in self.text
                    or "confirm" in self.text
                    or "proceed" in self.text
                    or "payment successful" in self.text
                    or "payment complete" in self.text
                    or "payment completed" in self.text
                    or "paid successfully" in self.text
                )
            ):
                is_booking_confirmation = True
                self.plan.metadata["payment_confirmation_requested"] = True
                if "payment" in self.text or self.current_payment_successful:
                    self.plan.metadata["payment_successful"] = True
            elif any(
                p in self.text
                for p in [
                    "book it",
                    "book this",
                    "book this slot",
                    "book now",
                    "please book it",
                    "ok",
                    "okay",
                    "sure",
                    "go ahead",
                ]
            ):
                is_booking_confirmation = True
                self.plan.metadata["payment_confirmation_requested"] = True
        elif (
            res_ctx
            and res_ctx.has_reference
            and res_ctx.resolved_source == "doctor_availability"
            and res_ctx.reference_type == "affirmation"
        ):
            is_booking_confirmation = True
            self.plan.metadata["payment_confirmation_requested"] = True
        elif "book" in self.intent.actions and (
            (self.plan.metadata.get("doctor_name") or self.intent.doctor_name)
            and (
                self.plan.metadata.get("booking_datetime")
                or self.intent.booking_datetime
            )
        ):
            if not (res_ctx and res_ctx.reference_type == "ordinal"):
                is_booking_confirmation = True

        is_availability = (
            any(
                k in self.text
                for k in [
                    "doctor available",
                    "available doctor",
                    "doctor slot",
                    "open slots",
                    "open appointments",
                    "slots open",
                    "is dr",
                    "is dr.",
                    "is doctor",
                    "available on",
                    "availability",
                    "when is",
                    "free slots",
                    "any slots",
                    "check slots",
                    "show slots",
                    "available slots",
                    "appointment slots",
                    "book",
                    "reserve",
                    "schedule",
                ]
            )
            or ("book" in self.intent.actions)
            or (res_ctx and res_ctx.reference_type == "ordinal")
        )

        if (
            is_explicit_patient_appointment
            or is_booking_confirmation
            or ("book" in self.intent.actions)
        ):
            self.plan.goals.append("manage_appointment")
        elif is_availability:
            self.plan.goals.append("check_doctor_availability")
        elif self.intent.is_appointment or "appointment" in self.text:
            if "my" in self.text:
                self.plan.goals.append("manage_appointment")
            else:
                self.plan.goals.append("check_doctor_availability")

        if (
            self.intent.is_consultation
            or any(
                k in self.text
                for k in [
                    "previous consultation",
                    "last consultation",
                    "what did doctor say",
                    "last visit",
                    "follow up",
                ]
            )
            or (
                res_ctx
                and res_ctx.has_reference
                and res_ctx.resolved_source == "consultation"
            )
        ):
            self.plan.goals.append("review_consultation")

        if (
            self.intent.is_history
            or any(
                k in self.text
                for k in [
                    "medicine",
                    "medication",
                    "prescribed",
                    "prescribe",
                    "drug",
                    "tablet",
                    "capsule",
                    "dosage",
                    "what doctor recommended",
                    "doctor recommend",
                ]
            )
            or (
                res_ctx
                and res_ctx.has_reference
                and res_ctx.resolved_source == "patient_history"
            )
        ):
            self.plan.goals.append("review_patient_history")

        if (
            parse_document_query(self.intent.original_text) is not None
            or any(
                k in self.text
                for k in [
                    "latest report",
                    "last report",
                    "compare reports",
                    "blood report",
                    "analyze my report",
                    "analyze my blood",
                    "summarize my report",
                    "review my report",
                    "what does my report",
                    "cbc report",
                    "hemoglobin",
                    "hb level",
                    "pcv level",
                    "rbc count",
                    "wbc count",
                    "platelet",
                    "blood test",
                    "prescription",
                    "medicine",
                    "medication",
                    "prescribed",
                ]
            )
            or (
                res_ctx
                and res_ctx.has_reference
                and res_ctx.resolved_source == "asset_selection"
            )
        ):
            self.plan.goals.append("review_document")

        if any(k in self.text for k in ["memory", "remember", "recall"]):
            self.plan.goals.append("access_memory")

        # Context-aware follow-up logic
        prev_query_type = self.plan.metadata.get("query_type", "general")
        if not self.plan.goals or (
            len(self.plan.goals) == 1 and self.plan.goals[0] == "review_consultation"
        ):
            # If it only detected consultation (e.g., due to "symptoms"), but previous was RAG, add review_document
            if prev_query_type == "rag" or prev_query_type == "document":
                if "review_document" not in self.plan.goals:
                    self.plan.goals.append("review_document")
                if "review_patient_history" not in self.plan.goals:
                    self.plan.goals.append("review_patient_history")

        if not self.plan.goals:
            if prev_query_type == "rag":
                self.plan.goals.extend(["review_document", "review_patient_history"])
            elif prev_query_type == "consultation":
                self.plan.goals.append("review_consultation")
            else:
                self.plan.goals.append("general_chat")

    def determine_required_information(self):
        meta = self.plan.metadata

        for goal in self.plan.goals:
            if goal == "manage_appointment":
                meta["query_type"] = "appointment"
                if self.intent.is_appointment:
                    for entity in APPOINTMENT_RULE_CONFIG["entities"]:
                        if entity in self.intent.entities:
                            meta["detected_entities"].append(entity)
                if "cancel" in self.intent.actions:
                    meta["detected_actions"].append("cancel")
                elif "reschedule" in self.intent.actions:
                    meta["detected_actions"].append("reschedule")
                elif "book" in self.intent.actions or (
                    self.resolved_context and self.resolved_context.has_reference
                ):
                    if "book" not in meta["detected_actions"]:
                        meta["detected_actions"].append("book")
                elif "upcoming" in self.intent.actions:
                    meta["detected_actions"].append("upcoming")
                elif "list" in self.intent.actions:
                    meta["detected_actions"].append("list")

            elif goal == "check_doctor_availability":
                meta["query_type"] = "doctor_availability"
                if self.intent.doctor_name:
                    meta["doctor_name"] = self.intent.doctor_name

            elif goal == "review_consultation":
                if self.intent.intent_type == "symptom":
                    meta["query_type"] = "symptom"
                    for entity in CONSULTATION_RULE_CONFIG["entities"]:
                        if entity in self.intent.entities:
                            meta["detected_entities"].append(entity)
                elif self.intent.intent_type == "consultation":
                    meta["query_type"] = "consultation"

            elif goal == "review_patient_history":
                meta["query_type"] = "patient_history"
                if self.intent.history_type:
                    meta["history_type"] = self.intent.history_type

            elif goal == "review_document":
                doc_intent = parse_document_query(self.intent.original_text)
                if doc_intent:
                    meta["query_type"] = "document"
                    meta["document_type"] = doc_intent.document_type
                    meta["report_type"] = doc_intent.report_type
                    meta["comparison_requested"] = doc_intent.comparison_requested
                    if doc_intent.detected_entities:
                        meta["detected_entities"].extend(doc_intent.detected_entities)

    def build_execution_plan(self):
        tasks = []
        res_ctx = self.resolved_context

        for goal in self.plan.goals:
            if goal == "manage_appointment":
                action_handler = "APPOINTMENT"
                action = "all"
                if "cancel" in self.intent.actions:
                    action_handler = "APPOINTMENT_CANCEL"
                elif "reschedule" in self.intent.actions:
                    action_handler = "APPOINTMENT_RESCHEDULE"
                elif (
                    "book" in self.intent.actions
                    or (
                        res_ctx
                        and res_ctx.has_reference
                        and res_ctx.resolved_source == "doctor_availability"
                    )
                    or self.plan.metadata.get("active_workflow")
                ):
                    action_handler = "APPOINTMENT_BOOK"
                elif "upcoming" in self.intent.actions:
                    action = "upcoming"
                elif "list" in self.intent.actions:
                    action = "all"

                params = {"action": action}
                if action_handler == "APPOINTMENT_BOOK":
                    active_wf_dict = self.plan.metadata.get("active_workflow")
                    active_wf = (
                        ActiveWorkflow.from_dict(active_wf_dict)
                        if active_wf_dict
                        else None
                    )
                    wf_ctx = active_wf.context if active_wf else {}
                    is_existing_payment_turn = bool(
                        active_wf
                        and active_wf.status
                        in ("waiting_confirmation", "waiting_payment_confirmation")
                        and (
                            self.plan.metadata.get("appointment_id")
                            or wf_ctx.get("appointment_id")
                        )
                    )

                    booking_datetime = (
                        self.intent.booking_datetime
                        or self.plan.metadata.get("booking_datetime")
                        or wf_ctx.get("appointment_time")
                        or wf_ctx.get("selected_slot")
                    )
                    booking_ordinal = (
                        self.intent.booking_ordinal
                        or self.plan.metadata.get("booking_ordinal")
                        or wf_ctx.get("selection_type")
                    )
                    appointment_id = (
                        self.plan.metadata.get("appointment_id")
                        or wf_ctx.get("appointment_id")
                        or (
                            res_ctx.resolved_entity.get("appointment_id")
                            if res_ctx and res_ctx.resolved_entity
                            else None
                        )
                    )
                    slot_id = (
                        self.plan.metadata.get("slot_id")
                        or wf_ctx.get("slot_id")
                        or (
                            res_ctx.resolved_entity.get("slot_id")
                            if res_ctx and res_ctx.resolved_entity
                            else None
                        )
                    )

                    if (
                        res_ctx
                        and res_ctx.has_reference
                        and not is_existing_payment_turn
                    ):
                        if res_ctx.reference_type == "ordinal" and not booking_ordinal:
                            booking_ordinal = str(res_ctx.resolved_selection)
                        if (
                            res_ctx.resolved_entity.get("available_slots")
                            and not booking_datetime
                        ):
                            slots = res_ctx.resolved_entity["available_slots"]
                            idx = res_ctx.metadata.get("ordinal_index", 0)
                            if (
                                isinstance(slots, list)
                                and slots
                                and abs(idx) < len(slots)
                            ):
                                booking_datetime = slots[idx]

                    if booking_datetime:
                        params["booking_datetime"] = booking_datetime
                        self.plan.metadata["booking_datetime"] = booking_datetime
                    if booking_ordinal:
                        params["booking_ordinal"] = booking_ordinal
                        self.plan.metadata["booking_ordinal"] = booking_ordinal
                    if appointment_id:
                        params["appointment_id"] = appointment_id
                        self.plan.metadata["appointment_id"] = appointment_id
                    if slot_id:
                        params["slot_id"] = slot_id
                        self.plan.metadata["slot_id"] = slot_id

                    doc_name = (
                        params.get("doctor_name")
                        or self.plan.metadata.get("doctor_name")
                        or (
                            res_ctx.resolved_entity.get("doctor_name")
                            if res_ctx
                            else None
                        )
                        or wf_ctx.get("doctor_name")
                    )
                    if doc_name:
                        params["doctor_name"] = doc_name
                        self.plan.metadata["doctor_name"] = doc_name

                    if self.plan.metadata.get("payment_confirmation_requested"):
                        params["payment_confirmation_requested"] = True
                    if self.plan.metadata.get("payment_successful"):
                        params["payment_successful"] = True

                    print(
                        "[DEBUG][PLANNER][BOOK_PARAMS] "
                        f"existing_payment_turn={is_existing_payment_turn} "
                        f"appointment_id={appointment_id} slot_id={slot_id} "
                        f"booking_datetime={booking_datetime} booking_ordinal={booking_ordinal}"
                    )

                    # Update active_workflow state to executing
                    if active_wf:
                        active_wf.status = "executing"
                        self.plan.metadata["active_workflow"] = active_wf.to_dict()

                if action_handler == "APPOINTMENT":
                    tasks.append(
                        PlannerTask.create_retrieve("APPOINTMENT", parameters=params)
                    )
                else:
                    tasks.append(
                        PlannerTask.create_action(action_handler, parameters=params)
                    )

            elif goal == "check_doctor_availability":
                params = {}
                doc_name = self.intent.doctor_name or self.plan.metadata.get(
                    "doctor_name"
                )
                if doc_name:
                    params["doctor_name"] = doc_name

                # Check if this is a new search replacing a previous doctor's workflow
                prev_wf_dict = self.plan.metadata.get("active_workflow")
                prev_wf = (
                    ActiveWorkflow.from_dict(prev_wf_dict) if prev_wf_dict else None
                )
                if (
                    prev_wf
                    and doc_name
                    and prev_wf.context.get("doctor_name")
                    and prev_wf.context.get("doctor_name").lower() != doc_name.lower()
                ):
                    prev_wf = None

                if (
                    res_ctx
                    and res_ctx.has_reference
                    and res_ctx.reference_type == "ordinal"
                ):
                    booking_ordinal = str(res_ctx.resolved_selection)
                    booking_datetime = None
                    slots = res_ctx.resolved_entity.get("available_slots") or []
                    idx = res_ctx.metadata.get("ordinal_index", 0)
                    if isinstance(slots, list) and slots and abs(idx) < len(slots):
                        booking_datetime = slots[idx]

                    self.plan.metadata["booking_ordinal"] = booking_ordinal
                    if booking_datetime:
                        self.plan.metadata["booking_datetime"] = booking_datetime

                    # Fallback to existing contexts if missing from resolved entity
                    avail_ctx = self.state.get("doctor_availability_context") or []
                    avail_dict = (
                        avail_ctx[0]
                        if isinstance(avail_ctx, list) and len(avail_ctx) > 0
                        else {}
                    )
                    prev_wf_dict = self.plan.metadata.get("active_workflow") or {}
                    prev_ctx = (
                        prev_wf_dict.get("context", {})
                        if isinstance(prev_wf_dict, dict)
                        else {}
                    )

                    wf_context = {
                        "doctor_name": doc_name
                        or res_ctx.resolved_entity.get("doctor_name")
                        or avail_dict.get("doctor_name")
                        or prev_ctx.get("doctor_name"),
                        "doctor_id": doc_name
                        or res_ctx.resolved_entity.get("doctor_id")
                        or avail_dict.get("doctor_id")
                        or prev_ctx.get("doctor_id"),
                        "selected_slot": booking_datetime,
                        "appointment_time": booking_datetime,
                        "selection_type": booking_ordinal,
                        "appointment_id": res_ctx.resolved_entity.get("appointment_id")
                        or prev_ctx.get("appointment_id"),
                        "slot_id": res_ctx.resolved_entity.get("slot_id")
                        or prev_ctx.get("slot_id"),
                        "amount": res_ctx.resolved_entity.get("amount")
                        or prev_ctx.get("amount"),
                        "currency": res_ctx.resolved_entity.get("currency")
                        or prev_ctx.get("currency"),
                        "available_slots": slots
                        or avail_dict.get("available_slots")
                        or prev_ctx.get("available_slots", []),
                    }
                    new_wf = ActiveWorkflow(
                        type="appointment_booking",
                        status="waiting_confirmation",
                        context=wf_context,
                    )
                    self.plan.metadata["active_workflow"] = new_wf.to_dict()
                    tasks.append(
                        PlannerTask.create_retrieve(
                            "APPOINTMENT_SEARCH_SLOTS", parameters=params
                        )
                    )
                elif doc_name or ("book" in self.intent.actions):
                    wf_context = {
                        "doctor_name": doc_name,
                        "doctor_id": doc_name,
                        "available_slots": (
                            res_ctx.resolved_entity.get("available_slots")
                            if res_ctx
                            else []
                        ),
                    }
                    new_wf = ActiveWorkflow(
                        type="appointment_booking",
                        status="waiting_selection",
                        context=wf_context,
                    )
                    self.plan.metadata["active_workflow"] = new_wf.to_dict()
                    tasks.append(
                        PlannerTask.create_retrieve(
                            "APPOINTMENT_SEARCH_SLOTS", parameters=params
                        )
                    )
                else:
                    tasks.append(
                        PlannerTask.create_retrieve(
                            "APPOINTMENT_SEARCH_SLOTS", parameters=params
                        )
                    )

            elif goal == "review_consultation":
                if self.intent.intent_type == "symptom":
                    tasks.append(PlannerTask.create_retrieve("MEMORY"))
                    tasks.append(PlannerTask.create_retrieve("CONSULTATION"))
                elif self.intent.intent_type == "consultation":
                    if "last_time" in self.intent.actions:
                        tasks.append(PlannerTask.create_retrieve("MEMORY"))
                    tasks.append(PlannerTask.create_retrieve("CONSULTATION"))
                else:
                    action = "retrieve"
                    if "history" in self.intent.actions:
                        action = "history"
                    tasks.append(
                        PlannerTask.create_retrieve("CONSULTATION", action=action)
                    )

            elif goal == "review_patient_history":
                tasks.append(PlannerTask.create_retrieve("PATIENT_HISTORY"))

            elif goal == "review_document":
                doc_intent = parse_document_query(self.intent.original_text)
                if doc_intent:
                    tasks.append(
                        PlannerTask.create_retrieve(
                            "ASSET_INDEX", action=doc_intent.action
                        )
                    )
                else:
                    tasks.append(
                        PlannerTask.create_retrieve("ASSET_INDEX", action="latest")
                    )

            elif goal == "access_memory":
                tasks.append(PlannerTask.create_retrieve("MEMORY"))

        self.plan.add_tasks(tasks)

    def order_tasks(self):
        self.plan.deduplicate()
        if not self.plan.tasks:
            self.plan.add_tasks([PlannerTask(task_type="general_response")])

    def derive_legacy_strategy(self) -> str:
        primary_goal = self.plan.goals[0] if self.plan.goals else "general_chat"
        if primary_goal == "manage_appointment":
            return "APPOINTMENT_QUERY"
        elif primary_goal == "check_doctor_availability":
            return "APPOINTMENT_SEARCH_SLOTS"
        elif primary_goal == "review_consultation":
            return "CONSULTATION_QUERY"
        elif primary_goal == "review_patient_history":
            return "PATIENT_HISTORY_QUERY"
        elif primary_goal == "review_document":
            return "DOCUMENT_QUERY"
        elif primary_goal == "access_memory":
            return "MEMORY_QUERY"
        return "GENERAL_CHAT"

    def execute(self) -> ExecutionPlan:
        print(f"[DEBUG][PLANNER] text = {self.text}")
        print(
            f"[DEBUG][PLANNER] prev_metadata_keys={sorted(list((self.state.get('planner_metadata') or {}).keys()))}"
        )

        # ── 1. Run generic ContextResolver ────────────────────────────────
        self.resolved_context = ContextResolver(self.state, self.text).resolve()
        if self.resolved_context:
            print(
                "[DEBUG][PLANNER][CONTEXT] "
                f"has_reference={self.resolved_context.has_reference} "
                f"reference_type={self.resolved_context.reference_type} "
                f"source={self.resolved_context.resolved_source} "
                f"selection={self.resolved_context.resolved_selection} "
                f"entity_keys={sorted(list((self.resolved_context.resolved_entity or {}).keys()))}"
            )

        # Merge generic entity attributes from resolved_context into plan metadata
        if self.resolved_context and self.resolved_context.resolved_entity:
            res_ent = self.resolved_context.resolved_entity

            # If a new ordinal/selection is resolved, override previous selection metadata
            if self.resolved_context.reference_type == "ordinal":
                if res_ent.get("booking_datetime"):
                    self.plan.metadata["booking_datetime"] = res_ent["booking_datetime"]
                if self.resolved_context.resolved_selection:
                    self.plan.metadata["booking_ordinal"] = str(
                        self.resolved_context.resolved_selection
                    )

            for k, v in res_ent.items():
                if v is not None and (
                    k not in self.plan.metadata
                    or self.resolved_context.reference_type == "ordinal"
                ):
                    self.plan.metadata[k] = v

            # Maintain active_workflow in planner_metadata
            if (
                res_ent.get("doctor_name")
                or res_ent.get("available_slots")
                or res_ent.get("booking_datetime")
                or res_ent.get("selected_slot")
                or res_ent.get("appointment_time")
            ):
                current_wf_dict = self.plan.metadata.get("active_workflow")
                current_wf = (
                    ActiveWorkflow.from_dict(current_wf_dict)
                    if current_wf_dict
                    else None
                )
                wf_ctx = current_wf.context if current_wf else {}
                b_dt = (
                    res_ent.get("booking_datetime")
                    or res_ent.get("appointment_time")
                    or res_ent.get("selected_slot")
                    or (self.intent.booking_datetime if self.intent else None)
                    or self.plan.metadata.get("booking_datetime")
                )
                b_ord = (
                    self.plan.metadata.get("booking_ordinal")
                    or res_ent.get("selection_type")
                    or wf_ctx.get("selection_type")
                )
                appointment_id = (
                    self.plan.metadata.get("appointment_id")
                    or res_ent.get("appointment_id")
                    or wf_ctx.get("appointment_id")
                )
                slot_id = (
                    self.plan.metadata.get("slot_id")
                    or res_ent.get("slot_id")
                    or wf_ctx.get("slot_id")
                )
                amount = (
                    self.plan.metadata.get("amount")
                    or res_ent.get("amount")
                    or wf_ctx.get("amount")
                )
                currency = (
                    self.plan.metadata.get("currency")
                    or res_ent.get("currency")
                    or wf_ctx.get("currency")
                )
                existing_payment_turn = bool(
                    current_wf
                    and current_wf.status
                    in ("waiting_confirmation", "waiting_payment_confirmation")
                    and appointment_id
                )

                updated_ctx = {
                    **wf_ctx,
                    "doctor_name": res_ent.get("doctor_name")
                    or wf_ctx.get("doctor_name")
                    or self.plan.metadata.get("doctor_name"),
                    "doctor_id": res_ent.get("doctor_id")
                    or wf_ctx.get("doctor_id")
                    or res_ent.get("doctor_name"),
                    "selected_slot": b_dt,
                    "appointment_time": b_dt,
                    "booking_datetime": b_dt,
                    "selection_type": b_ord,
                    "booking_ordinal": b_ord,
                    "appointment_id": appointment_id,
                    "slot_id": slot_id,
                    "amount": amount,
                    "currency": currency,
                    "available_slots": res_ent.get("available_slots")
                    or wf_ctx.get("available_slots", []),
                }
                if existing_payment_turn:
                    status = current_wf.status
                    if wf_ctx.get("appointment_id"):
                        updated_ctx["appointment_id"] = wf_ctx.get("appointment_id")
                    if wf_ctx.get("slot_id"):
                        updated_ctx["slot_id"] = wf_ctx.get("slot_id")
                    if wf_ctx.get("amount") is not None:
                        updated_ctx["amount"] = wf_ctx.get("amount")
                    if wf_ctx.get("currency"):
                        updated_ctx["currency"] = wf_ctx.get("currency")
                else:
                    status = (
                        "waiting_confirmation"
                        if updated_ctx.get("selected_slot")
                        else "waiting_selection"
                    )
                new_wf = ActiveWorkflow(
                    type="appointment_booking", status=status, context=updated_ctx
                )
                self.plan.metadata["active_workflow"] = new_wf.to_dict()
                print(
                    "[DEBUG][PLANNER][WF_MERGE] "
                    f"status={status} appointment_id={updated_ctx.get('appointment_id')} "
                    f"slot_id={updated_ctx.get('slot_id')} amount={updated_ctx.get('amount')} "
                    f"currency={updated_ctx.get('currency')} booking_datetime={updated_ctx.get('booking_datetime')}"
                )

        # ── 2. Standard Planner Pipeline ──────────────────────────────────
        self.determine_goal()
        self.determine_required_information()
        self.build_execution_plan()
        self.order_tasks()

        legacy_strategy = self.derive_legacy_strategy()
        for task in self.plan.tasks:
            if not task.parameters:
                task.parameters = {}
            task.parameters["retrieval_strategy"] = legacy_strategy

        return self.plan


async def planner_node(state: UnifiedChatState) -> dict[str, Any]:
    import os
    import traceback
    import time
    from ..utils.logger import log_section, log_key_value, log_error

    start_time = time.time()
    used_llm = False

    from ..memory.conversation_memory import ConversationMemoryManager

    memory_manager = ConversationMemoryManager(state)
    hydrated_metadata = memory_manager.hydrate_planner_metadata()

    local_state = dict(state)
    local_state["planner_metadata"] = hydrated_metadata

    fallback_reason = None
    validation_errors = []
    llm_confidence = None

    if os.environ.get("USE_LLM_PLANNER", "true").lower() == "true":
        try:
            from .llm_planner import LLMPlanningEngine
            from .planning_validator import PlanningValidator

            llm_engine = LLMPlanningEngine(local_state)
            plan = await llm_engine.execute()

            is_valid, errors = PlanningValidator.validate(plan)
            if not is_valid:
                validation_errors = errors
                raise ValueError(f"Plan validation failed: {', '.join(errors)}")

            strategy = plan.metadata.get("retrieval_strategy", "general")
            used_llm = True
            llm_confidence = getattr(plan, "confidence", None)
        except Exception as e:
            fallback_reason = str(e)
            log_error(f"LLM Planner failed: {e}. Falling back to rule-based planner.")
            # Do not print stack trace for intended fallbacks like low confidence
            if (
                "confidence" not in str(e).lower()
                and "validation failed" not in str(e).lower()
            ):
                traceback.print_exc()

    if not used_llm:
        engine = PlanningEngine(local_state)
        plan = engine.execute()
        strategy = engine.derive_legacy_strategy()

    from .plan_optimizer import PlanOptimizer

    plan, opt_stats = PlanOptimizer.optimize(plan, local_state)

    plan_time = (time.time() - start_time) * 1000
    timing = state.get("timing_metrics", {})
    timing["planner"] = plan_time

    planner_stats = {
        "planner_used": "LLM" if used_llm else "Rule-based",
        "planning_time_ms": int(plan_time),
        "confidence": llm_confidence,
        "fallback_reason": fallback_reason,
        "validation_errors": validation_errors,
    }

    log_section("PLANNER")
    log_key_value("Planner", "LLM" if used_llm else "Rule-based")
    if used_llm and llm_confidence is not None:
        log_key_value("Confidence", f"{llm_confidence:.2f}")

    log_key_value("Validation", "PASSED" if not validation_errors else "FAILED")

    log_section("PLANNER OPTIMIZATION")
    log_key_value("Original Tasks", str(opt_stats["original_tasks"]))
    log_key_value("Optimized Tasks", str(opt_stats["optimized_tasks"]))
    log_key_value("Duplicates Removed", str(opt_stats["duplicates_removed"]))
    log_key_value("Context Reused", str(opt_stats["context_reused"]))
    log_key_value("Skipped Retrievals", str(opt_stats["skipped_retrievals"]))

    if plan.tasks:
        task_summaries = []
        for i, t in enumerate(plan.tasks):
            task_summaries.append(
                f"{i+1}. {t.task_id or 'unknown'} ({t.capability_name})"
            )
        log_key_value("Tasks", "\n".join(task_summaries))
    else:
        log_key_value("Tasks", "[]")

    display_metadata = {
        k: v
        for k, v in plan.metadata.items()
        if k not in ["detected_entities", "active_workflow"]
    }
    log_key_value("Metadata Updated", display_metadata if display_metadata else "{}")
    log_key_value("Fallback", fallback_reason if fallback_reason else "None")
    log_key_value("Planning Time", f"{int(plan_time)} ms")

    plan.metadata["planner_stats"] = planner_stats

    return {
        "execution_plan": plan.tasks,
        "planner_metadata": plan.metadata,
        "retrieval_strategy": strategy,
        "timing_metrics": timing,
    }
