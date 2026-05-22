from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.exceptions import (
    AppError, 
    InvalidStateTransitionError, 
    ConcurrencyConflictError, 
    InsufficientEvidenceError
)

async def app_error_handler(request: Request, exc: AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    
    if isinstance(exc, InvalidStateTransitionError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, ConcurrencyConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, InsufficientEvidenceError):
        status_code = status.HTTP_409_CONFLICT
        
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc)},
    )

async def general_exception_handler(request: Request, exc: Exception):
    # Log the full exception here in a real app
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )
