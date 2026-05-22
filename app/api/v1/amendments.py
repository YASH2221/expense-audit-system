from fastapi import APIRouter, Depends, HTTPException
from typing import List, Any
from decimal import Decimal
from pydantic import BaseModel, Field
from app.api.dependencies import (
    get_claim_service, 
    get_current_user,
    RoleChecker,
    get_amendment_repo
)
from app.services.claim_service import ClaimService
from app.core.exceptions import InvalidStateTransitionError, PermissionDeniedError
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter()

class AmendmentCreate(BaseModel):
    amount: Decimal = Field(gt=0, description="The corrected amount must be positive")
    reason: str = Field(min_length=5, description="A valid reason for amendment is required")

@router.post("/{claim_id}/amend")
async def amend_claim(
    claim_id: int,
    amendment_in: AmendmentCreate,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(RoleChecker([UserRole.CONTROLLER]))
):
    try:
        return await service.amend_claim(
            claim_id=claim_id,
            controller_id=current_user.id,
            amount=amendment_in.amount,
            reason=amendment_in.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, PermissionDeniedError) as e:
        raise HTTPException(status_code=409 if isinstance(e, InvalidStateTransitionError) else 403, detail=str(e))

@router.get("/{claim_id}")
async def get_amendments(
    claim_id: int,
    amendment_repo = Depends(get_amendment_repo),
    current_user: User = Depends(get_current_user)
):
    # RBAC: Only authorized users or owners (though controllers typically handle this)
    # For now, all authenticated can view if they can see the claim
    return await amendment_repo.get_by_original_claim(claim_id)
