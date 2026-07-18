from enum import StrEnum


class BackendErrorCode(StrEnum):
    DATABASE_NOT_CONFIGURED = "database_not_configured"
    DATABASE_UNAVAILABLE = "database_unavailable"
    AI_NOT_CONFIGURED = "ai_not_configured"
    AI_SERVICE_UNAVAILABLE = "ai_service_unavailable"


class ServiceUnavailableError(RuntimeError):
    error_code: BackendErrorCode


class DatabaseError(ServiceUnavailableError):
    """Base error for database configuration and availability failures."""


class DatabaseConfigurationError(DatabaseError):
    error_code = BackendErrorCode.DATABASE_NOT_CONFIGURED


class DatabaseUnavailableError(DatabaseError):
    error_code = BackendErrorCode.DATABASE_UNAVAILABLE


class AIConfigurationError(ServiceUnavailableError):
    error_code = BackendErrorCode.AI_NOT_CONFIGURED


class AIServiceError(ServiceUnavailableError):
    error_code = BackendErrorCode.AI_SERVICE_UNAVAILABLE
