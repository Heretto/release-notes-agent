"""
Orchestrator error-message sanitization tests.

(The DITA root-element regression suite that used to live alongside this moved
to hop-core with the validator: hop-core tests/test_dita_root_element.py.)
"""


class TestOrchestratorErrorSanitization:
    def test_validation_failure_message_is_user_visible(self):
        from app.services.job_orchestrator import _sanitize_job_error
        msg = (
            "DITA validation failed: the generated content could not be made "
            "valid after correction attempts, so no output was produced."
        )
        assert _sanitize_job_error(msg) == msg
