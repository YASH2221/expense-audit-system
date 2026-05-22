from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
from app.core.exceptions import (
    AppError, 
    InsufficientEvidenceError, 
    InvalidStateTransitionError, 
    ConcurrencyConflictError,
    PermissionDeniedError
)
from app.core.error_handlers import app_error_handler

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    app.add_exception_handler(AppError, app_error_handler)
    
    @app.exception_handler(InvalidStateTransitionError)
    @app.exception_handler(ConcurrencyConflictError)
    async def conflict_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InsufficientEvidenceError)
    async def evidence_exception_handler(request: Request, exc: InsufficientEvidenceError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PermissionDeniedError)
    async def permission_exception_handler(request: Request, exc: PermissionDeniedError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})


    # Include Routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
        
    return app

app = create_app()
