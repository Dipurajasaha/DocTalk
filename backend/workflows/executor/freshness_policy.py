from typing import Any
from ..models.capability_metadata import CapabilityMetadata
from ..models.freshness_decision import FreshnessDecision
from ..graph.state import WorkflowState

def evaluate_freshness_policy(
    capability_metadata: CapabilityMetadata,
    state: WorkflowState,
    task: dict[str, Any]
) -> FreshnessDecision:
    """
    Evaluates whether a capability needs to be executed fresh or can reuse existing information.
    This logic is completely independent of the execution logic.
    """
    
    # Check for specific hardcoded rules matching the requested defaults first
    name = capability_metadata.capability_name
    
    if name == "DOCTOR_AVAILABILITY" or name == "APPOINTMENT_SEARCH_SLOTS":
        return FreshnessDecision(
            execute_fresh=True,
            reuse_existing=False,
            ignore_memory=True,
            ignore_cache=True,
            reason="Doctor availability must always reflect real-time live data."
        )
        
    if name in ("APPOINTMENT_BOOK", "APPOINTMENT_CANCEL", "APPOINTMENT_RESCHEDULE"):
        return FreshnessDecision(
            execute_fresh=True,
            reuse_existing=False,
            ignore_memory=True,
            ignore_cache=True,
            reason="Actions must always be executed fresh."
        )
        
    if name == "APPOINTMENT":
        return FreshnessDecision(
            execute_fresh=True,
            reuse_existing=False,
            ignore_memory=True,
            ignore_cache=True,
            reason="Appointment schedules can change frequently and should be executed fresh."
        )
        
    if name in ("PATIENT_HISTORY", "CONSULTATION", "ASSET_INDEX", "MEMORY"):
        return FreshnessDecision(
            execute_fresh=False,
            reuse_existing=True,
            ignore_memory=not capability_metadata.allow_memory,
            ignore_cache=not capability_metadata.allow_cache,
            reason=f"{name} is historically stable and can reuse existing contexts if available."
        )
        
    # Fallback default based purely on metadata
    if capability_metadata.always_refresh:
        return FreshnessDecision(
            execute_fresh=True,
            reuse_existing=False,
            ignore_memory=True,
            ignore_cache=True,
            reason="Capability metadata always_refresh is True."
        )
    else:
        return FreshnessDecision(
            execute_fresh=False,
            reuse_existing=True,
            ignore_memory=not capability_metadata.allow_memory,
            ignore_cache=not capability_metadata.allow_cache,
            reason="Capability metadata permits reuse."
        )
