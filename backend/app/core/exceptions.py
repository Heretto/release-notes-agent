"""Application exceptions.

Core exceptions are provided by hop-core. Domain-specific exceptions are defined here.
"""

# Re-export core exceptions
from hop_core.core.exceptions import (
    HopException as ReleaseNotesException,
    AuthenticationError,
    AuthorizationError,
    CredentialError,
    EmailNotConfiguredError,
)


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
