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
