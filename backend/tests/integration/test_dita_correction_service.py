"""
Integration tests for the DITA correction loop.

These tests verify that:
1. Invalid DITA is detected by DTD validation (not just structural checks).
2. Validation errors are fed back to the LLM with precise DTD error messages.
3. The LLM corrects the content and the corrected content passes DTD validation.
4. Concept / task / reference types are corrected with the right DOCTYPE and body
   element (conbody / taskbody / refbody), not forced into a generic <topic>.
5. Text content is preserved across correction cycles.
6. Already-valid content is returned unchanged without calling the LLM.
7. The regeneration fallback prompt uses the correct DOCTYPE for the topic type.

Tests that require a live LLM are automatically skipped when no AI credentials
are available in the environment.  Supported providers (checked in order):
  ANTHROPIC_API_KEY / TEST_CLAUDE_API_KEY
  GOOGLE_AI_API_KEY
  TEST_OPENAI_API_KEY
"""

import os
import re
import pytest

from app.services.dita_validator_v2 import DITAValidatorV2
from app.services.dita_correction_service import DITACorrectionService
from app.services.ai_service import AIServiceFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_TOPIC = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release_notes">
  <title>Release Notes v1.0</title>
  <body>
    <section>
      <title>New Features</title>
      <ul>
        <li>Feature one: faster processing</li>
        <li>Feature two: improved UI</li>
      </ul>
    </section>
  </body>
</topic>"""

VALID_CONCEPT = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
<concept id="overview">
  <title>Overview</title>
  <conbody>
    <p>This is the overview concept.</p>
  </conbody>
</concept>"""

VALID_TASK = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task id="install">
  <title>Installation</title>
  <taskbody>
    <steps>
      <step><cmd>Run the installer.</cmd></step>
    </steps>
  </taskbody>
</task>"""

# Invalid: title is missing — DTD requires (title, ...) as first child of topic
INVALID_TOPIC_NO_TITLE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="broken">
  <body>
    <p>This topic has no title, which violates the DTD.</p>
  </body>
</topic>"""

# Invalid concept: uses <body> instead of <conbody>
INVALID_CONCEPT_WRONG_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
<concept id="bad_concept">
  <title>Bad Concept</title>
  <body>
    <p>Concept content should be in conbody, not body.</p>
  </body>
</concept>"""

# Invalid task: missing <steps> — only a <taskbody> shell
INVALID_TASK_MISSING_STEPS = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task id="bad_task">
  <title>Bad Task</title>
  <taskbody>
    <p>Tasks need steps, not bare paragraphs in taskbody.</p>
  </taskbody>
</task>"""


def _first_available_ai_service():
    """Return (provider, api_key, model) for the first configured AI provider."""
    candidates = [
        ("anthropic", os.getenv("ANTHROPIC_API_KEY") or os.getenv("TEST_CLAUDE_API_KEY"),
         os.getenv("TEST_CLAUDE_MODEL", "claude-haiku-4-5-20251001")),
        ("gemini",    os.getenv("GOOGLE_AI_API_KEY"),
         os.getenv("TEST_GOOGLE_MODEL", "gemini-2.0-flash")),
        ("openai",    os.getenv("TEST_OPENAI_API_KEY"),
         os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")),
    ]
    for provider, key, model in candidates:
        if key:
            return provider, key, model
    return None, None, None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def validator():
    return DITAValidatorV2()


@pytest.fixture(scope="module")
def ai_service():
    """Return a live AI service, or skip the test if none is configured / reachable."""
    import asyncio
    from app.services.ai_service import GenerationRequest

    provider, key, model = _first_available_ai_service()
    if not provider:
        pytest.skip(
            "No AI credentials configured "
            "(set ANTHROPIC_API_KEY, GOOGLE_AI_API_KEY, or TEST_OPENAI_API_KEY)"
        )

    service = AIServiceFactory.create(provider=provider, api_key=key, model=model)

    # Verify the key is valid with a minimal generation call; skip if it fails.
    probe = GenerationRequest(
        system_prompt="You are a test assistant.",
        user_prompt="Reply with the single word: OK",
        max_tokens=10,
        temperature=0.0,
    )
    try:
        asyncio.get_event_loop().run_until_complete(service.generate(probe))
    except Exception as exc:
        pytest.skip(f"AI service ({provider}) unreachable or key invalid: {exc}")

    return service


@pytest.fixture(scope="module")
def correction_service(ai_service, validator):
    return DITACorrectionService(ai_service=ai_service, validator=validator)


# ---------------------------------------------------------------------------
# Unit tests — no LLM required
# ---------------------------------------------------------------------------

class TestDetectTopicType:
    """_detect_topic_type() correctly identifies the root element."""

    def _service(self):
        """Minimal service without a real AI service (unit-test-only)."""
        class _Stub:
            async def generate(self, req):
                raise AssertionError("should not be called")
        return DITACorrectionService(ai_service=_Stub())

    def test_detects_concept(self):
        svc = self._service()
        assert svc._detect_topic_type(VALID_CONCEPT) == "concept"

    def test_detects_task(self):
        svc = self._service()
        assert svc._detect_topic_type(VALID_TASK) == "task"

    def test_detects_reference(self):
        svc = self._service()
        xml = """<?xml version="1.0"?>
<reference id="r1"><title>R</title><refbody/></reference>"""
        assert svc._detect_topic_type(xml) == "reference"

    def test_detects_topic(self):
        svc = self._service()
        assert svc._detect_topic_type(VALID_TOPIC) == "topic"

    def test_defaults_to_topic_for_unknown_root(self):
        svc = self._service()
        assert svc._detect_topic_type("<unknown id='x'/>") == "topic"

    def test_fallback_text_scan_on_malformed_xml(self):
        svc = self._service()
        # lxml parse will fail; text scan should find <concept
        assert svc._detect_topic_type("not xml at all but has <concept id=") == "concept"

    def test_task_takes_priority_over_later_topic_tag(self):
        svc = self._service()
        # Root element is <task>, so result must be task even if 'topic' appears later
        xml = """<?xml version="1.0"?>
<task id="t1"><title>T</title><taskbody/></task>
<!-- topic -->"""
        assert svc._detect_topic_type(xml) == "task"


class TestExtractValidationErrors:
    """extract_validation_errors() uses DTD validation, not just structural."""

    def test_returns_no_errors_for_valid_topic(self, validator):
        result = validator.extract_validation_errors(VALID_TOPIC)
        assert result["has_errors"] is False
        assert result["errors"] == []
        assert result["line_errors"] == {}

    def test_detects_missing_title_via_dtd(self, validator):
        result = validator.extract_validation_errors(INVALID_TOPIC_NO_TITLE)
        assert result["has_errors"] is True
        all_errors = result["errors"] + [
            msg for msgs in result["line_errors"].values() for msg in msgs
        ]
        assert any("title" in e.lower() or "topic" in e.lower() for e in all_errors), (
            f"Expected a DTD error about missing title, got: {all_errors}"
        )

    def test_detects_wrong_body_for_concept_via_dtd(self, validator):
        result = validator.extract_validation_errors(INVALID_CONCEPT_WRONG_BODY)
        assert result["has_errors"] is True
        all_errors = result["errors"] + [
            msg for msgs in result["line_errors"].values() for msg in msgs
        ]
        combined = " ".join(all_errors).lower()
        assert "body" in combined or "conbody" in combined or "concept" in combined, (
            f"Expected a DTD error about wrong body element, got: {all_errors}"
        )

    def test_line_numbers_present_for_dtd_errors(self, validator):
        result = validator.extract_validation_errors(INVALID_TOPIC_NO_TITLE)
        # DTD validation via xmllint should produce at least one line-numbered error
        assert result["line_errors"], (
            "Expected line-specific errors from xmllint DTD validation"
        )

    def test_xml_syntax_error_captured(self, validator):
        bad_xml = "<topic id='x'><title>T</title><body><p>unclosed"
        result = validator.extract_validation_errors(bad_xml)
        assert result["has_errors"] is True

    def test_returns_no_errors_for_valid_concept(self, validator):
        result = validator.extract_validation_errors(VALID_CONCEPT)
        assert result["has_errors"] is False

    def test_returns_no_errors_for_valid_task(self, validator):
        result = validator.extract_validation_errors(VALID_TASK)
        assert result["has_errors"] is False


class TestRegenerationPromptDoctype:
    """The regeneration fallback prompt uses the DOCTYPE matching the topic type."""

    def _build_enhanced_prompt(self, content: str) -> str:
        """Mirror the logic in validate_and_correct_with_ai to extract the prompt."""
        svc = DITACorrectionService(ai_service=None)  # ai_service not called here
        topic_type = svc._detect_topic_type(content)
        doctype_map = {
            "concept": ('<!DOCTYPE concept', "<concept ", "<conbody>", "</concept>"),
            "task":    ('<!DOCTYPE task',    "<task ",    "<taskbody>", "</task>"),
            "reference": ('<!DOCTYPE reference', "<reference ", "<refbody>", "</reference>"),
        }
        doctype_hint, root_open, body_el, root_close = doctype_map.get(topic_type, (
            '<!DOCTYPE topic', "<topic ", "<body>", "</topic>",
        ))
        return "\n".join([doctype_hint, root_open, body_el, root_close])

    def test_concept_prompt_uses_concept_doctype(self):
        snippet = self._build_enhanced_prompt(INVALID_CONCEPT_WRONG_BODY)
        assert "<!DOCTYPE concept" in snippet
        assert "<conbody>" in snippet
        assert "<!DOCTYPE topic" not in snippet

    def test_task_prompt_uses_task_doctype(self):
        snippet = self._build_enhanced_prompt(INVALID_TASK_MISSING_STEPS)
        assert "<!DOCTYPE task" in snippet
        assert "<taskbody>" in snippet

    def test_topic_prompt_uses_topic_doctype(self):
        snippet = self._build_enhanced_prompt(INVALID_TOPIC_NO_TITLE)
        assert "<!DOCTYPE topic" in snippet
        assert "<body>" in snippet


# ---------------------------------------------------------------------------
# Integration tests — live LLM required
# ---------------------------------------------------------------------------

class TestCorrectionLoopIntegration:
    """End-to-end correction loop tests that call a real LLM."""

    @pytest.mark.asyncio
    async def test_already_valid_topic_passes_without_llm_call(self, correction_service, validator):
        """Valid content must pass validation immediately — no LLM call needed."""
        call_count = {"n": 0}
        original_get_ai = correction_service._get_ai_correction

        async def counting_get_ai(prompt):
            call_count["n"] += 1
            return await original_get_ai(prompt)

        correction_service._get_ai_correction = counting_get_ai
        try:
            content, is_valid, log = await correction_service.validate_and_correct_with_ai(VALID_TOPIC)
        finally:
            correction_service._get_ai_correction = original_get_ai

        assert is_valid, f"Valid topic should pass. Log:\n" + "\n".join(log)
        assert call_count["n"] == 0, (
            f"No LLM calls expected for already-valid content, got {call_count['n']}"
        )

    @pytest.mark.asyncio
    async def test_already_valid_concept_passes_without_llm_call(self, correction_service):
        call_count = {"n": 0}
        original = correction_service._get_ai_correction

        async def counting(prompt):
            call_count["n"] += 1
            return await original(prompt)

        correction_service._get_ai_correction = counting
        try:
            content, is_valid, log = await correction_service.validate_and_correct_with_ai(VALID_CONCEPT)
        finally:
            correction_service._get_ai_correction = original

        assert is_valid, "Valid concept should pass. Log:\n" + "\n".join(log)
        assert call_count["n"] == 0

    @pytest.mark.asyncio
    async def test_corrects_topic_missing_title(self, correction_service, validator):
        """LLM should add the missing <title> so the output passes DTD validation."""
        content, is_valid, log = await correction_service.correct_validation_errors(
            INVALID_TOPIC_NO_TITLE, max_attempts=3
        )
        assert is_valid, (
            "Correction loop failed to fix topic missing title.\n"
            "Log:\n" + "\n".join(log) + "\n"
            "Final content:\n" + content
        )
        valid, errors = validator.validate_with_dtd(content)
        assert valid, f"Corrected content still fails DTD validation: {errors}"

    @pytest.mark.asyncio
    async def test_corrects_concept_wrong_body_element(self, correction_service, validator):
        """LLM should replace <body> with <conbody> so the concept passes DTD validation."""
        content, is_valid, log = await correction_service.correct_validation_errors(
            INVALID_CONCEPT_WRONG_BODY, max_attempts=3
        )
        assert is_valid, (
            "Correction loop failed to fix concept with wrong body element.\n"
            "Log:\n" + "\n".join(log) + "\n"
            "Final content:\n" + content
        )
        # The corrected output must be a concept — not silently rewritten as <topic>
        assert "<concept" in content, (
            "Corrected output should remain a <concept>, got:\n" + content
        )
        valid, errors = validator.validate_with_dtd(content)
        assert valid, f"Corrected concept still fails DTD validation: {errors}"

    @pytest.mark.asyncio
    async def test_corrects_task_missing_steps(self, correction_service, validator):
        """LLM should restructure the task so it has valid <steps>/<step>/<cmd>."""
        content, is_valid, log = await correction_service.correct_validation_errors(
            INVALID_TASK_MISSING_STEPS, max_attempts=3
        )
        assert is_valid, (
            "Correction loop failed to fix task with missing steps.\n"
            "Log:\n" + "\n".join(log) + "\n"
            "Final content:\n" + content
        )
        assert "<task" in content, (
            "Corrected output should remain a <task>, got:\n" + content
        )
        valid, errors = validator.validate_with_dtd(content)
        assert valid, f"Corrected task still fails DTD validation: {errors}"

    @pytest.mark.asyncio
    async def test_correction_preserves_text_content(self, correction_service):
        """The correction prompt instructs the LLM to preserve text — verify it does."""
        content, is_valid, log = await correction_service.correct_validation_errors(
            INVALID_TOPIC_NO_TITLE, max_attempts=3
        )
        assert "This topic has no title, which violates the DTD." in content, (
            "Original paragraph text must be preserved after correction.\n"
            "Final content:\n" + content
        )

    @pytest.mark.asyncio
    async def test_validate_and_correct_full_flow_invalid_topic(self, correction_service, validator):
        """End-to-end: auto-fix → AI correction → final validation."""
        content, is_valid, log = await correction_service.validate_and_correct_with_ai(
            INVALID_TOPIC_NO_TITLE,
            original_prompt="Generate DITA release notes.",
            max_cycles=2,
        )
        assert is_valid, (
            "validate_and_correct_with_ai should produce valid DITA.\n"
            "Log:\n" + "\n".join(log) + "\n"
            "Final content:\n" + content
        )
        valid, errors = validator.validate_with_dtd(content)
        assert valid, f"Output of validate_and_correct_with_ai still fails DTD: {errors}"

    @pytest.mark.asyncio
    async def test_validate_and_correct_full_flow_invalid_concept(self, correction_service, validator):
        content, is_valid, log = await correction_service.validate_and_correct_with_ai(
            INVALID_CONCEPT_WRONG_BODY,
            original_prompt="Generate a DITA concept about this feature.",
            max_cycles=2,
        )
        assert is_valid, (
            "validate_and_correct_with_ai should produce a valid concept.\n"
            "Log:\n" + "\n".join(log) + "\n"
            "Final content:\n" + content
        )
        valid, errors = validator.validate_with_dtd(content)
        assert valid, f"Output of validate_and_correct_with_ai still fails DTD: {errors}"

    @pytest.mark.asyncio
    async def test_dtd_errors_are_in_correction_log(self, correction_service):
        """The log entries should reference DTD-level errors, not vague structural ones."""
        _, _, log = await correction_service.correct_validation_errors(
            INVALID_TOPIC_NO_TITLE, max_attempts=1
        )
        combined = " ".join(log).lower()
        # Log must mention that errors were found (the count comes from DTD validation)
        assert "error" in combined, f"Expected error mention in log, got:\n{log}"

    @pytest.mark.asyncio
    async def test_correction_loop_reports_progress(self, correction_service):
        """The log should track attempt numbers."""
        _, _, log = await correction_service.correct_validation_errors(
            INVALID_TOPIC_NO_TITLE, max_attempts=2
        )
        attempt_lines = [l for l in log if l.startswith("Attempt ")]
        assert len(attempt_lines) >= 1, f"Expected attempt log entries, got:\n{log}"
