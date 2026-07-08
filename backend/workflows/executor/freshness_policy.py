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
    if capability_metadata.always_refresh:
        return FreshnessDecision(
            execute_fresh=True,
            reuse_existing=False,
            ignore_memory=not capability_metadata.allow_memory,
            ignore_cache=not capability_metadata.allow_cache,
            reason=f"{capability_metadata.capability_name} metadata requires fresh execution."
        )
    else:
        return FreshnessDecision(
            execute_fresh=False,
            reuse_existing=True,
            ignore_memory=not capability_metadata.allow_memory,
            ignore_cache=not capability_metadata.allow_cache,
            reason=f"{capability_metadata.capability_name} metadata permits reuse."
        )
