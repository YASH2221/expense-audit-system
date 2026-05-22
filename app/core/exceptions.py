class AppError(Exception):
    """Base exception for application errors"""
    pass

class InvalidStateTransitionError(AppError):
    """Raised when a state transition is not allowed"""
    pass

class ConcurrencyConflictError(AppError):
    """Raised when an optimistic locking conflict occurs"""
    pass

class InsufficientEvidenceError(AppError):
    """Raised when a claim is approved/submitted without required evidence"""
    pass

class PermissionDeniedError(AppError):
    """Raised when a user lacks the required permissions"""
    pass
