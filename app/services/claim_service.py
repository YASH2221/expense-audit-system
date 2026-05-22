from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm.exc import StaleDataError
from app.models.claim import Claim, ClaimStatusHistory, ReviewerComment
from app.models.amendment import Amendment
from app.models.enums import ClaimStatus, AuditAction
from app.repositories.claim_repo import ClaimRepository
from app.repositories.amendment_repo import AmendmentRepository
from app.services.audit_service import AuditService
from app.core.exceptions import (
    InvalidStateTransitionError, 
    ConcurrencyConflictError, 
    InsufficientEvidenceError,
    PermissionDeniedError
)

class ClaimService:
    def __init__(self, claim_repo: ClaimRepository, audit_service: AuditService, amendment_repo: AmendmentRepository):
        self.claim_repo = claim_repo
        self.audit_service = audit_service
        self.amendment_repo = amendment_repo

    async def create_claim(self, employee_id: int, amount: Decimal, description: str, purpose: str) -> Claim:
        claim_data = {
            "employee_id": employee_id,
            "amount": amount,
            "description": description,
            "purpose": purpose,
            "status": ClaimStatus.DRAFT
        }
        claim = await self.claim_repo.create(claim_data)
        
        await self.audit_service.log_action(
            actor_id=employee_id,
            action=AuditAction.CLAIM_CREATED,
            claim_id=claim.id,
            new_value=claim_data
        )
        await self.claim_repo.session.commit()
        return claim

    async def update_claim(self, claim_id: int, employee_id: int, data: dict) -> Claim:
        claim = await self.claim_repo.get(claim_id)
        if not claim:
            raise ValueError("Claim not found")
        if claim.employee_id != employee_id:
            raise PermissionDeniedError("Not authorized to edit this claim")
        if claim.status not in [ClaimStatus.DRAFT, ClaimStatus.CHANGES_REQUESTED]:
            raise InvalidStateTransitionError("Only DRAFT or CHANGES_REQUESTED claims can be edited")
            
        old_data = {
            "amount": str(claim.amount),
            "description": claim.description,
            "purpose": claim.purpose
        }
        
        updated_claim = await self.claim_repo.update(claim, data)
        
        await self.audit_service.log_action(
            actor_id=employee_id,
            action=AuditAction.CLAIM_EDITED,
            claim_id=claim.id,
            old_value=old_data,
            new_value=data
        )
        await self.claim_repo.session.commit()
        return updated_claim

    async def submit_claim(self, claim_id: int, employee_id: int) -> Claim:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        
        # We need to eagerly load evidence to avoid MissingGreenlet error
        query = select(Claim).where(Claim.id == claim_id).options(selectinload(Claim.evidence))
        result = await self.claim_repo.session.execute(query)
        claim = result.scalars().first()
        if not claim:
            raise ValueError("Claim not found")
        
        if claim.employee_id != employee_id:
            raise PermissionDeniedError("Only the creator can submit the claim")
        
        if claim.status not in [ClaimStatus.DRAFT, ClaimStatus.CHANGES_REQUESTED]:
            raise InvalidStateTransitionError(f"Cannot submit claim from {claim.status}")

        # Enforce Evidence Sufficiency Rule (Non-Negotiable)
        # Every claim requires at least one piece of evidence attached before submission.
        if not claim.evidence:
             raise InsufficientEvidenceError(f"Submission failed: Claim #{claim_id} requires at least one piece of evidence attached.")

        old_status = claim.status
        claim.status = ClaimStatus.SUBMITTED
        
        try:
            await self.claim_repo.update(claim, {}) # Trigger flush/version check
            
            # History record
            history = ClaimStatusHistory(
                claim_id=claim.id,
                old_status=old_status,
                new_status=ClaimStatus.SUBMITTED,
                changed_by_id=employee_id
            )
            await self.claim_repo.add_status_history(history)
            
            # Audit log
            await self.audit_service.log_action(
                actor_id=employee_id,
                action=AuditAction.CLAIM_SUBMITTED,
                claim_id=claim.id,
                old_value={"status": old_status},
                new_value={"status": ClaimStatus.SUBMITTED}
            )
            
            await self.claim_repo.session.commit()
            return claim
        except StaleDataError:
            raise ConcurrencyConflictError("The claim was modified by another process. Please refresh and try again.")

    async def approve_claim(self, claim_id: int, reviewer_id: int, remarks: str) -> Claim:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        
        query = select(Claim).where(Claim.id == claim_id).options(selectinload(Claim.evidence))
        result = await self.claim_repo.session.execute(query)
        claim = result.scalars().first()
        if not claim:
            raise ValueError("Claim not found")
            
        if claim.status not in [ClaimStatus.SUBMITTED, ClaimStatus.RESUBMITTED]:
            raise InvalidStateTransitionError(f"Cannot approve claim from {claim.status}")

        # Enforce Evidence Sufficiency
        if not claim.evidence:
             raise InsufficientEvidenceError("At least one piece of evidence is required for approval.")
        
        # Amount-based rule example: > $100 requires evidence (already checked above as min 1)
        
        old_status = claim.status
        claim.status = ClaimStatus.APPROVED
        
        try:
            await self.claim_repo.update(claim, {})
            
            # Add Remarks
            comment = ReviewerComment(
                claim_id=claim.id,
                reviewer_id=reviewer_id,
                comment_text=remarks
            )
            await self.claim_repo.add_comment(comment)
            
            # History
            history = ClaimStatusHistory(
                claim_id=claim.id,
                old_status=old_status,
                new_status=ClaimStatus.APPROVED,
                changed_by_id=reviewer_id,
                reason=remarks
            )
            await self.claim_repo.add_status_history(history)
            
            # Audit
            await self.audit_service.log_action(
                actor_id=reviewer_id,
                action=AuditAction.CLAIM_REVIEWED,
                claim_id=claim.id,
                old_value={"status": old_status},
                new_value={"status": ClaimStatus.APPROVED, "remarks": remarks}
            )
            
            await self.claim_repo.session.commit()
            return claim
        except StaleDataError:
            raise ConcurrencyConflictError("Conflict detected. Another reviewer may have already processed this claim.")

    async def request_changes(self, claim_id: int, reviewer_id: int, reason: str) -> Claim:
        claim = await self.claim_repo.get(claim_id)
        if not claim:
            raise ValueError("Claim not found")
            
        if claim.status not in [ClaimStatus.SUBMITTED, ClaimStatus.RESUBMITTED]:
            raise InvalidStateTransitionError(f"Cannot request changes from {claim.status}")

        old_status = claim.status
        claim.status = ClaimStatus.CHANGES_REQUESTED
        
        try:
            await self.claim_repo.update(claim, {})
            
            # Comment
            comment = ReviewerComment(claim_id=claim.id, reviewer_id=reviewer_id, comment_text=reason)
            await self.claim_repo.add_comment(comment)
            
            # History
            history = ClaimStatusHistory(
                claim_id=claim.id,
                old_status=old_status,
                new_status=ClaimStatus.CHANGES_REQUESTED,
                changed_by_id=reviewer_id,
                reason=reason
            )
            await self.claim_repo.add_status_history(history)
            
            await self.audit_service.log_action(
                actor_id=reviewer_id,
                action=AuditAction.CLAIM_REVIEWED,
                claim_id=claim.id,
                old_value={"status": old_status},
                new_value={"status": ClaimStatus.CHANGES_REQUESTED, "reason": reason}
            )
            await self.claim_repo.session.commit()
            return claim
        except StaleDataError:
            raise ConcurrencyConflictError("Conflict detected.")

    async def reject_claim(self, claim_id: int, reviewer_id: int, reason: str) -> Claim:
        claim = await self.claim_repo.get(claim_id)
        if not claim:
            raise ValueError("Claim not found")
            
        if claim.status not in [ClaimStatus.SUBMITTED, ClaimStatus.RESUBMITTED]:
            raise InvalidStateTransitionError(f"Cannot reject claim from {claim.status}")

        old_status = claim.status
        claim.status = ClaimStatus.REJECTED
        
        try:
            await self.claim_repo.update(claim, {})
            
            comment = ReviewerComment(claim_id=claim.id, reviewer_id=reviewer_id, comment_text=reason)
            await self.claim_repo.add_comment(comment)
            
            history = ClaimStatusHistory(
                claim_id=claim.id,
                old_status=old_status,
                new_status=ClaimStatus.REJECTED,
                changed_by_id=reviewer_id,
                reason=reason
            )
            await self.claim_repo.add_status_history(history)
            
            await self.audit_service.log_action(
                actor_id=reviewer_id,
                action=AuditAction.CLAIM_REVIEWED,
                claim_id=claim.id,
                old_value={"status": old_status},
                new_value={"status": ClaimStatus.REJECTED, "reason": reason}
            )
            await self.claim_repo.session.commit()
            return claim
        except StaleDataError:
            raise ConcurrencyConflictError("Conflict detected.")

    async def finalize_claim(self, claim_id: int, controller_id: int) -> Claim:
        claim = await self.claim_repo.get(claim_id)
        if not claim:
            raise ValueError("Claim not found")
            
        if claim.status != ClaimStatus.APPROVED:
            raise InvalidStateTransitionError(f"Only APPROVED claims can be finalized. Current status: {claim.status}")

        old_status = claim.status
        claim.status = ClaimStatus.FINALIZED
        claim.finalized_at = datetime.utcnow()
        
        try:
            await self.claim_repo.update(claim, {})
            
            # History
            history = ClaimStatusHistory(
                claim_id=claim.id,
                old_status=old_status,
                new_status=ClaimStatus.FINALIZED,
                changed_by_id=controller_id
            )
            await self.claim_repo.add_status_history(history)
            
            # Audit
            await self.audit_service.log_action(
                actor_id=controller_id,
                action=AuditAction.CLAIM_FINALIZED,
                claim_id=claim.id,
                old_value={"status": old_status},
                new_value={"status": ClaimStatus.FINALIZED, "finalized_at": claim.finalized_at.isoformat()}
            )
            await self.claim_repo.session.commit()
            return claim
        except StaleDataError:
            raise ConcurrencyConflictError("Conflict detected.")

    async def amend_claim(self, claim_id: int, controller_id: int, amount: Decimal, reason: str) -> Amendment:
        original_claim = await self.claim_repo.get(claim_id)
        if not original_claim:
            raise ValueError("Claim not found")
            
        if original_claim.status != ClaimStatus.FINALIZED:
            raise InvalidStateTransitionError("Amendments are allowed only on FINALIZED claims.")

        # 0. Check if an amendment already exists
        existing = await self.amendment_repo.get_by_original_claim(claim_id)
        if existing:
            raise InvalidStateTransitionError(f"Claim #{claim_id} has already been amended. Only one amendment per claim is allowed.")

        # 1. Create a "shadow" claim record with corrected data
        amended_claim_data = {
            "employee_id": original_claim.employee_id,
            "amount": amount,
            "description": f"AMENDMENT to Claim #{claim_id}: {original_claim.description}",
            "purpose": original_claim.purpose,
            "status": ClaimStatus.FINALIZED 
        }
        amended_claim = await self.claim_repo.create(amended_claim_data)
        
        # 2. Create amendment link
        amendment = Amendment(
            original_claim_id=claim_id,
            amendment_claim_id=amended_claim.id,
            controller_id=controller_id,
            reason=reason,
            created_at=datetime.utcnow(),
            finalized_at=datetime.utcnow()
        )
        self.amendment_repo.session.add(amendment)
        await self.amendment_repo.session.flush()

        # 3. Audit log
        await self.audit_service.log_action(
            actor_id=controller_id,
            action=AuditAction.AMENDMENT_CREATED,
            claim_id=claim_id,
            old_value={"amount": str(original_claim.amount)},
            new_value={"amount": str(amount), "amendment_id": amendment.id, "reason": reason}
        )
        
        await self.claim_repo.session.commit()
        return amendment

