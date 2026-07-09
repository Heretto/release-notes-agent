"""Regression tests for the Anthropic temperature-deprecation fallback.

Newer Claude models (e.g. claude-sonnet-5) reject the `temperature` parameter
with a 400 "temperature is deprecated for this model" error. Both generation
paths must retry once WITHOUT temperature rather than failing the whole call.

See: credential-test 400 ("Anthropic Connection failed") caused by sending
temperature to claude-sonnet-5.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services.anthropic_adapter import AnthropicAdapter
from app.services.ai_service import GenerationRequest

TEMPERATURE_ERROR = "`temperature` is deprecated for this model."


def _make_adapter():
    adapter = AnthropicAdapter(api_key="sk-test-key", model_name="claude-sonnet-5")
    adapter.client = MagicMock()
    return adapter


def _fake_response(text="Connection successful"):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )


def _request():
    return GenerationRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="hi",
        max_tokens=20,
        temperature=0.7,
    )


class TestGenerateTemperatureFallback:
    async def test_retries_without_temperature_on_deprecation_error(self):
        """A temperature-deprecation 400 triggers one retry with temperature removed."""
        adapter = _make_adapter()
        adapter.client.messages.create = AsyncMock(
            side_effect=[Exception(TEMPERATURE_ERROR), _fake_response()]
        )

        result = await adapter.generate(_request())

        assert result.content == "Connection successful"
        assert adapter.client.messages.create.call_count == 2
        first_kwargs = adapter.client.messages.create.call_args_list[0].kwargs
        second_kwargs = adapter.client.messages.create.call_args_list[1].kwargs
        assert "temperature" in first_kwargs, "first attempt should include temperature"
        assert "temperature" not in second_kwargs, "retry must drop temperature"
        # Everything else must be preserved on the retry.
        assert second_kwargs["model"] == "claude-sonnet-5"
        assert second_kwargs["max_tokens"] == 20

    async def test_none_text_block_is_skipped(self):
        """claude-sonnet-5 returns a TextBlock with text=None before the real content
        block; concatenating it must not crash, and the real text must survive."""
        adapter = _make_adapter()
        response = SimpleNamespace(
            content=[
                SimpleNamespace(text=None),           # the None block that caused the crash
                SimpleNamespace(text="<topic>ok</topic>"),
            ],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            stop_reason="end_turn",
        )
        adapter.client.messages.create = AsyncMock(return_value=response)

        result = await adapter.generate(_request())

        assert result.content == "<topic>ok</topic>"

    async def test_no_retry_on_success(self):
        """When the model accepts temperature, it is sent and there is no retry."""
        adapter = _make_adapter()
        adapter.client.messages.create = AsyncMock(return_value=_fake_response())

        result = await adapter.generate(_request())

        assert result.content == "Connection successful"
        assert adapter.client.messages.create.call_count == 1
        assert adapter.client.messages.create.call_args.kwargs["temperature"] == 0.7

    async def test_unrelated_error_is_not_retried(self):
        """A non-temperature error must propagate, not be swallowed by the retry."""
        adapter = _make_adapter()
        adapter.client.messages.create = AsyncMock(
            side_effect=Exception("overloaded_error: server is overloaded")
        )

        try:
            await adapter.generate(_request())
            assert False, "expected the error to propagate"
        except Exception as e:
            assert "overloaded" in str(e).lower()
        assert adapter.client.messages.create.call_count == 1


class _RaisingStream:
    """Async CM whose entry raises — mimics the 400 firing on request send."""

    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *args):
        return False


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def text_stream(self):
        async def _gen():
            for c in self._chunks:
                yield c
        return _gen()


class TestGenerateStreamTemperatureFallback:
    async def test_stream_retries_without_temperature(self):
        """Streaming path also retries without temperature on the deprecation error."""
        adapter = _make_adapter()
        adapter.client.messages.stream = MagicMock(
            side_effect=[
                _RaisingStream(Exception(TEMPERATURE_ERROR)),
                _FakeStream(["Connection ", "successful"]),
            ]
        )

        chunks = [chunk async for chunk in adapter.generate_stream(_request())]

        assert "".join(chunks) == "Connection successful"
        assert adapter.client.messages.stream.call_count == 2
        assert "temperature" in adapter.client.messages.stream.call_args_list[0].kwargs
        assert "temperature" not in adapter.client.messages.stream.call_args_list[1].kwargs
