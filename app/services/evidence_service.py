import hashlib
import os
from typing import List, Tuple, Any
from app.core.config import settings
from app.models.evidence import Evidence, EvidenceReuseFlag
from app.models.enums import AuditAction, ClaimStatus
from app.repositories.evidence_repo import EvidenceRepository
from app.services.audit_service import AuditService
from app.core.exceptions import InvalidStateTransitionError, PermissionDeniedError

class EvidenceService:
    def __init__(self, evidence_repo: EvidenceRepository, audit_service: AuditService):
        self.evidence_repo = evidence_repo
        self.audit_service = audit_service
        
        # Ensure uploads directory exists
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

    async def upload_evidence(
        self, 
        claim_id: int, 
        user_id: int, 
        file_name: str, 
        content: bytes, 
        mime_type: str
    ) -> Tuple[Evidence, List[EvidenceReuseFlag]]:
        from sqlalchemy import select
        from app.models.claim import Claim
        
        # 1. Validate Claim Ownership and State
        query = select(Claim).where(Claim.id == claim_id)
        result = await self.evidence_repo.session.execute(query)
        claim = result.scalars().first()
        
        if not claim:
            raise ValueError("Claim not found")
        if claim.employee_id != user_id:
            raise PermissionDeniedError("Not authorized to add evidence to this claim")
        if claim.status not in [ClaimStatus.DRAFT, ClaimStatus.CHANGES_REQUESTED]:
            raise InvalidStateTransitionError("Evidence can only be added to DRAFT or CHANGES_REQUESTED claims")

        # Compute SHA256 hash
        content_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        
        # Save file to disk
        file_path = os.path.join(settings.UPLOADS_DIR, content_hash)
        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.write(content)
        
        # Check for reuse
        existing_instances = await self.evidence_repo.get_by_hash(content_hash)
        
        # Create evidence record
        evidence_data = {
            "claim_id": claim_id,
            "file_name": file_name,
            "file_size": file_size,
            "content_hash": content_hash,
            "mime_type": mime_type,
            "uploaded_by_id": user_id
        }
        evidence = await self.evidence_repo.create(evidence_data)
        
        # Log evidence attachment
        await self.audit_service.log_action(
            actor_id=user_id,
            action=AuditAction.EVIDENCE_ATTACHED,
            claim_id=claim_id,
            new_value={
                "evidence_id": evidence.id,
                "file_name": file_name,
                "content_hash": content_hash
            }
        )
        
        # Handle reuse flags
        flags = []
        for existing in existing_instances:
            if existing.claim_id != claim_id:
                flag = EvidenceReuseFlag(
                    evidence_id=evidence.id,
                    primary_claim_id=existing.claim_id,
                    secondary_claim_id=claim_id,
                    flagged_by_id=user_id, # System detected
                    reviewer_notes=f"Auto-detected reuse with claim #{existing.claim_id}"
                )
                await self.evidence_repo.add_reuse_flag(flag)
                flags.append(flag)
                
                # Log reuse detection
                await self.audit_service.log_action(
                    actor_id=user_id,
                    action=AuditAction.EVIDENCE_REUSE_FLAGGED,
                    claim_id=claim_id,
                    new_value={
                        "evidence_id": evidence.id,
                        "reused_from_claim": existing.claim_id
                    }
                )
                
        await self.evidence_repo.session.commit()
        return evidence, flags

    async def delete_evidence(self, evidence_id: int, user_id: int):
        from app.models.enums import ClaimStatus
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from app.models.evidence import Evidence
        
        # Load with claim to avoid MissingGreenlet
        query = select(Evidence).where(Evidence.id == evidence_id).options(selectinload(Evidence.claim))
        result = await self.evidence_repo.session.execute(query)
        evidence = result.scalars().first()
        
        if not evidence:
            raise ValueError("Evidence not found")
            
        # Check claim state
        claim = evidence.claim
        if claim.status not in [ClaimStatus.DRAFT, ClaimStatus.CHANGES_REQUESTED]:
             raise InvalidStateTransitionError("Evidence can only be removed from DRAFT or CHANGES_REQUESTED claims.")
             
        # Load user to check role
        from app.models.user import User
        from app.models.enums import UserRole
        user_query = select(User).where(User.id == user_id)
        user_result = await self.evidence_repo.session.execute(user_query)
        user = user_result.scalars().first()
        
        if not user:
            raise ValueError("User not found")

        # 2. RBAC Enforcement (Non-Negotiable)
        # Reviewers & Controllers cannot delete evidence (Brief 73, 89)
        if user.role in [UserRole.REVIEWER, UserRole.CONTROLLER]:
             raise PermissionDeniedError(f"Role {user.role} is not authorized to delete evidence. Only the owning Employee can perform this action.")

        # 3. Ownership Enforcement for Employees
        # An Employee can only delete if they are the owner of the claim or the uploader.
        if user.role == UserRole.EMPLOYEE:
            if evidence.uploaded_by_id != user_id and claim.employee_id != user_id:
                 raise PermissionDeniedError(f"Employee {user_id} is not the owner of this evidence or the parent claim. Deletion denied.")

        # Delete from disk
        file_path = os.path.join(settings.UPLOADS_DIR, evidence.content_hash)
        
        # Check if other evidence records use this hash before deleting file
        query_others = select(Evidence).where(Evidence.content_hash == evidence.content_hash).where(Evidence.id != evidence_id)
        result_others = await self.evidence_repo.session.execute(query_others)
        other_exists = result_others.scalars().first()
        
        if not other_exists and os.path.exists(file_path):
            os.remove(file_path)

        await self.evidence_repo.delete(evidence_id)
        
        # Log removal
        await self.audit_service.log_action(
            actor_id=user_id,
            action=AuditAction.EVIDENCE_REMOVED,
            claim_id=claim.id,
            old_value={"evidence_id": evidence_id, "file_name": evidence.file_name}
        )
        await self.evidence_repo.session.commit()

    async def get_evidence_file(self, evidence_id: int) -> Tuple[str, Evidence, Any]:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.evidence import Evidence
        
        query = select(Evidence).where(Evidence.id == evidence_id).options(selectinload(Evidence.claim))
        result = await self.evidence_repo.session.execute(query)
        evidence = result.scalars().first()
        
        if not evidence:
            raise ValueError("Evidence not found")
        
        claim = evidence.claim
        file_path = os.path.join(settings.UPLOADS_DIR, evidence.content_hash)
        return file_path, evidence, claim

    async def get_claim_evidence_files(self, claim_id: int):
        """
        Returns all evidence file paths for a given claim_id,
        along with the Claim object. Used for multi-invoice AI verification.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.evidence import Evidence
        from app.models.claim import Claim

        # Load claim with all its evidence
        query = (
            select(Claim)
            .where(Claim.id == claim_id)
            .options(selectinload(Claim.evidence))
        )
        result = await self.evidence_repo.session.execute(query)
        claim = result.scalars().first()

        if not claim:
            raise ValueError(f"Claim #{claim_id} not found")

        if not claim.evidence:
            raise ValueError(f"No evidence found for Claim #{claim_id}")

        file_paths = []
        for ev in claim.evidence:
            path = os.path.join(settings.UPLOADS_DIR, ev.content_hash)
            if os.path.exists(path):
                file_paths.append({"evidence_id": ev.id, "path": path, "file_name": ev.file_name})

        if not file_paths:
            raise ValueError(f"No physical files found for Claim #{claim_id}")

        return file_paths, claim

    async def scan_and_flag_reuse(self, claim_id: int, actor_id: int) -> List[EvidenceReuseFlag]:
        """
        Manually scan all evidence in a claim and flag any reuse found across the system.
        """
        from sqlalchemy import select
        from app.models.evidence import Evidence
        
        # Get all evidence for this claim
        query = select(Evidence).where(Evidence.claim_id == claim_id)
        result = await self.evidence_repo.session.execute(query)
        evidences = result.scalars().all()
        
        all_flags = []
        for evidence in evidences:
            # Find any other claims using this same hash
            instances = await self.evidence_repo.get_by_hash(evidence.content_hash)
            for existing in instances:
                if existing.claim_id != claim_id:
                    # Check if flag already exists to prevent duplicates
                    existing_flag = await self.evidence_repo.session.execute(
                        select(EvidenceReuseFlag).where(
                            EvidenceReuseFlag.evidence_id == evidence.id,
                            EvidenceReuseFlag.primary_claim_id == existing.claim_id
                        )
                    )
                    if not existing_flag.scalars().first():
                        flag = EvidenceReuseFlag(
                            evidence_id=evidence.id,
                            primary_claim_id=existing.claim_id,
                            secondary_claim_id=claim_id,
                            flagged_by_id=actor_id,
                            reviewer_notes=f"Manually flagged reuse with claim #{existing.claim_id}"
                        )
                        await self.evidence_repo.add_reuse_flag(flag)
                        all_flags.append(flag)
                        
                        await self.audit_service.log_action(
                            actor_id=actor_id,
                            action=AuditAction.EVIDENCE_REUSE_FLAGGED,
                            claim_id=claim_id,
                            new_value={
                                "evidence_id": evidence.id,
                                "reused_from_claim": existing.claim_id,
                                "manual": True
                            }
                        )
        
        await self.evidence_repo.session.commit()
        return all_flags
