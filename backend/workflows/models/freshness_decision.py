from pydantic import BaseModel, Field

class FreshnessDecision(BaseModel):
    """
    Represents the output of the freshness policy engine.
    """
    execute_fresh: bool = Field(description="Whether the capability must be executed fresh.")
    reuse_existing: bool = Field(description="Whether existing information can be reused.")
    ignore_memory: bool = Field(description="Whether to explicitly ignore short-term conversational memory.")
    ignore_cache: bool = Field(description="Whether to explicitly ignore any long-term caches.")
    reason: str = Field(description="The justification for this freshness decision.")
