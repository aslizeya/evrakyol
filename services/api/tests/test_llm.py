from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from app.llm import AnthropicProvider, DailyLimitedProvider, FakeProvider, LLMError

SCHEMA = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


def fake_response(stop_reason: str = "end_turn", text: str = '{"ok": true}', category=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=None),
    )


def provider(model: str = "claude-opus-5-5", **kwargs) -> tuple[AnthropicProvider, MagicMock]:
    client = MagicMock()
    stream = client.beta.messages.stream.return_value.__enter__.return_value
    stream.get_final_message.return_value = kwargs.pop("response", fake_response())
    return AnthropicProvider(api_key=None, model=model, client=client, **kwargs), client


def test_request_uses_structured_output_caching_and_fallbacks() -> None:
    p, client = provider(effort="high")
    result = p.generate_json(system="SİSTEM", user="KULLANICI", schema=SCHEMA)

    kwargs = client.beta.messages.stream.call_args.kwargs
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": SCHEMA},
    }
    assert kwargs["system"] == [
        {"type": "text", "text": "SİSTEM", "cache_control": {"type": "ephemeral"}}
    ]
    assert kwargs["messages"] == [{"role": "user", "content": "KULLANICI"}]
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in kwargs  # Opus 5.5'te düşünme her zaman açıktır; parametre gönderilmez
    assert result.text == '{"ok": true}'
    assert result.cache_read_tokens == 0


def test_haiku_and_disabled_fallbacks_send_no_fallback_parameter() -> None:
    for p, client in (provider("claude-haiku-5-5"), provider(use_fallbacks=False)):
        p.generate_json(system="s", user="u", schema=SCHEMA)
        kwargs = client.beta.messages.stream.call_args.kwargs
        assert "fallbacks" not in kwargs and "betas" not in kwargs


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (fake_response("refusal", category="cyber"), "refusal"),
        (fake_response("max_tokens"), "max_tokens"),
        (fake_response(text="  "), "empty"),
    ],
)
def test_unusable_responses_raise(response, reason: str) -> None:
    p, _ = provider(response=response)
    with pytest.raises(LLMError) as exc_info:
        p.generate_json(system="s", user="u", schema=SCHEMA)
    assert exc_info.value.reason == reason


def test_missing_api_key_is_a_configuration_error() -> None:
    with pytest.raises(LLMError) as exc_info:
        AnthropicProvider(api_key=None, model="claude-opus-5-5")
    assert exc_info.value.reason == "not_configured"


def test_daily_limit() -> None:
    limited = DailyLimitedProvider(FakeProvider(["{}", "{}", "{}"]), daily_limit=2)
    limited.generate_json(system="s", user="u", schema=SCHEMA)
    limited.generate_json(system="s", user="u", schema=SCHEMA)
    with pytest.raises(LLMError) as exc_info:
        limited.generate_json(system="s", user="u", schema=SCHEMA)
    assert exc_info.value.reason == "budget_exceeded"


def test_effort_can_be_overridden_per_call() -> None:
    p, client = provider(effort="high")
    p.generate_json(system="s", user="u", schema=SCHEMA, effort="low")
    assert client.beta.messages.stream.call_args.kwargs["output_config"]["effort"] == "low"


def _status_error(cls, status: int, message: str):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request)
    return cls(message, response=response, body=None)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (_status_error(anthropic.AuthenticationError, 401, "invalid x-api-key"), "auth"),
        (
            _status_error(
                anthropic.BadRequestError, 400, "Your credit balance is too low to access the API."
            ),
            "billing",
        ),
        (
            _status_error(anthropic.BadRequestError, 400, "output_config: invalid schema"),
            "bad_request",
        ),
        (_status_error(anthropic.InternalServerError, 529, "Overloaded"), "api_error"),
    ],
)
def test_api_errors_map_to_actionable_reasons(error, reason: str) -> None:
    p, client = provider()
    client.beta.messages.stream.side_effect = error
    with pytest.raises(LLMError) as exc_info:
        p.generate_json(system="s", user="u", schema=SCHEMA)
    assert exc_info.value.reason == reason
