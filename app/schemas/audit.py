from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime
from app.models.enums import AuditAction

class AuditLogResponse(BaseModel):
    id: int
    claim_id: Optional[int]
    actor_id: int
    action: AuditAction
    timestamp: datetime
    old_value: Optional[Any]
    new_value: Optional[Any]
    metadata: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)
