"""agent/llm.py with a fake Gemini client: no key, no network."""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors
from pydantic import BaseModel

from agent.llm import LLMError, model_name, structured


class Pick(BaseModel):
    ids: list[str]
    reason: str


class FakeGemini:
    """Stands in for genai.Client: returns (or raises) the queued replies in order."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(text=reply)


def api_error(code):
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": "boom", "status": "X"}})


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FAST", "flash-model")
    monkeypatch.delenv("GEMINI_MODEL_SMART", raising=False)


async def test_returns_validated_model_with_temperature_0_and_schema():
    fake = FakeGemini('{"ids": ["a", "b"], "reason": "same market"}')
    out = await structured("pick", Pick, system="be strict", client=fake)
    assert out == Pick(ids=["a", "b"], reason="same market")
    call = fake.calls[0]
    assert call["model"] == "flash-model"
    assert call["config"].temperature == 0
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_schema is Pick
    assert call["config"].system_instruction == "be strict"


@pytest.mark.parametrize(
    "first", [api_error(429), api_error(503), httpx.ConnectError("down"), "not json", None]
)
async def test_retries_transient_failures_then_succeeds(first):
    fake = FakeGemini(first, '{"ids": [], "reason": "ok"}')
    out = await structured("pick", Pick, backoff=0, client=fake)
    assert out.reason == "ok" and len(fake.calls) == 2


async def test_gives_up_after_retries():
    fake = FakeGemini(api_error(503), api_error(503), api_error(503))
    with pytest.raises(LLMError, match="after 3 attempts"):
        await structured("pick", Pick, backoff=0, client=fake)
    assert len(fake.calls) == 3


async def test_client_errors_are_not_retried():
    fake = FakeGemini(api_error(400))
    with pytest.raises(LLMError, match="400"):
        await structured("pick", Pick, backoff=0, client=fake)
    assert len(fake.calls) == 1


def test_model_names_from_env(monkeypatch):
    assert model_name("smart") == "flash-model"  # smart falls back to fast
    monkeypatch.setenv("GEMINI_MODEL_SMART", "pro-model")
    assert model_name("smart") == "pro-model"
    monkeypatch.setenv("GEMINI_MODEL_FAST", "")
    with pytest.raises(LLMError, match="GEMINI_MODEL_FAST"):
        model_name()
