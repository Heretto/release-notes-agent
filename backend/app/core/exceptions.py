from typing import Any, Optional, Dict

class ReleaseNotesException(Exception):
    """Base exception for the application."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationError(ReleaseNotesException):
    """Authentication failed."""
    pass

class AuthorizationError(ReleaseNotesException):
    """User not authorized for this action."""
    pass

class CredentialError(ReleaseNotesException):
    """Credential-related error."""
    pass

class JiraIntegrationError(ReleaseNotesException):
    """Error interacting with Jira."""
    pass

class HerettoIntegrationError(ReleaseNotesException):
    """Error interacting with Heretto."""
    pass

class AIGenerationError(ReleaseNotesException):
    """Error during AI content generation."""
    pass

class DITAValidationError(ReleaseNotesException):
    """DITA content validation failed."""
    pass

class JobProcessingError(ReleaseNotesException):
    """Error during job processing."""
    pass