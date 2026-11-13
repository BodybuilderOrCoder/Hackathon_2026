from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    objective: str = "BALANCED"
    include_carriers: bool = True
    time_limit_seconds: int = Field(default=10, ge=1, le=30)


class ApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    comment: str = ""


class AssignRequest(BaseModel):
    order_id: str
    route_key: str


class ExtractRequest(BaseModel):
    text: str = Field(min_length=3, max_length=10000)
