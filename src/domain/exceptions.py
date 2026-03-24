class DomainException(Exception):
    """Base exception for all domain errors."""
    pass

class APIError(DomainException):
    """Raised when an error occurs during an API call."""
    def __init__(self, message="API call failed", status_code=None):
        super().__init__(message)
        self.status_code = status_code

class ConfigError(DomainException):
    """Raised when there is an issue with application configuration."""
    pass

class EntityNotFoundError(DomainException):
    """Raised when a requested entity cannot be found in the system."""
    pass

class InvalidStatusError(DomainException):
    """Raised when an invalid status is provided."""
    pass

class ValidationError(DomainException):
    """Raised when data validation fails."""
    pass

class InvalidFilterCriteriaError(DomainException):
    """Raised when filter criteria are semantically invalid or incomplete."""
    pass

class ExternalAPIError(DomainException):
    """Raised when the upstream J&T API returns an unexpected or failed response."""
    def __init__(self, message: str, upstream_code: int | None = None) -> None:
        super().__init__(message)
        self.upstream_code = upstream_code
class ReportGenerationError(DomainException):
    """Raised when PDF report generation fails."""
    pass

class NoDataFoundError(DomainException):
    """Raised when no data is found for a report or query."""
    pass
