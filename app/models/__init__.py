from app.db.base import Base

# Import all models here so Alembic can discover them
from app.models.enums import UserRole, ClaimStatus, AuditAction
from app.models.user import User
from app.models.claim import Claim, ClaimStatusHistory, ReviewerComment
from app.models.evidence import Evidence, EvidenceReuseFlag
from app.models.amendment import Amendment
from app.models.audit import AuditLog
