from typing import Literal
from pydantic import BaseModel, Field

class CapabilityMetadata(BaseModel):
    """
    Defines the execution policy and metadata for a given workflow capability.
    """
    capability_name: str = Field(description="The unique identifier for this capability.")
    capability_type: Literal["retriever", "action"] = Field(description="Whether this capability retrieves data or performs an action.")
    always_refresh: bool = Field(default=False, description="If True, the executor should always run this capability even if data exists.")
    allow_memory: bool = Field(default=True, description="If True, the result can be persisted to short-term memory.")
    allow_cache: bool = Field(default=True, description="If True, the result can be cached.")
    priority: int = Field(default=10, description="Execution priority (lower number = higher priority).")
    supports_parallel_execution: bool = Field(default=True, description="If True, this capability can be executed concurrently with others.")
    description: str = Field(description="Human-readable description of what this capability does.")
    target_context_keys: list[str] = Field(default_factory=list, description="Keys in the UnifiedChatState where the result data should be merged.")
    evidence_behavior: str = Field(default="pass_through", description="How evidence is collected for this capability.")
