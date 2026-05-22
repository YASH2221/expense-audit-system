from fastapi import APIRouter
from app.api.v1 import claims, evidence, amendments, audit

api_router = APIRouter()

api_router.include_router(claims.router, prefix="/claims", tags=["claims"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(amendments.router, prefix="/amendments", tags=["amendments"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
