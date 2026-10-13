import asyncio
import json

import httpx
import pytest

from ai_service import AIService, OLLAMA_MODEL, OLLAMA_URL
from database import Message


def stub_model_response(monkeypatch, response_data, status_code=200):
    original_async_client = httpx.AsyncClient
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(status_code, json=response_data)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    return requests


def test_generate_returns_trimmed_model_response(monkeypatch):
    stub_model_response(monkeypatch, {"response": "  A useful summary.  "})

    result = asyncio.run(AIService._generate("Summarize these notes."))

    assert result == "A useful summary."


def test_generate_sends_prompt_to_configured_model(monkeypatch):
    requests = stub_model_response(monkeypatch, {"response": "Result"})

    asyncio.run(AIService._generate("Summarize these notes."))

    assert str(requests[0].url) == OLLAMA_URL
    assert json.loads(requests[0].content) == {
        "model": OLLAMA_MODEL,
        "prompt": "Summarize these notes.",
        "stream": False,
    }


def test_generate_reports_non_success_status(monkeypatch):
    stub_model_response(monkeypatch, {"detail": "unavailable"}, status_code=503)

    with pytest.raises(ValueError, match="AI service is unavailable"):
        asyncio.run(AIService._generate("Prompt"))


def test_generate_reports_empty_model_response(monkeypatch):
    stub_model_response(monkeypatch, {"response": "  "})

    with pytest.raises(ValueError, match="AI service returned an empty response"):
        asyncio.run(AIService._generate("Prompt"))


def test_generate_maps_connection_failure_to_unavailable(monkeypatch):
    original_async_client = httpx.AsyncClient

    async def handler(_request):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    with pytest.raises(ValueError, match="AI service is unavailable"):
        asyncio.run(AIService._generate("Prompt"))


def test_summarize_inbox_formats_messages_for_generation(monkeypatch):
    prompts = []

    async def generate(prompt):
        prompts.append(prompt)
        return "Main themes are appreciation."

    monkeypatch.setattr(AIService, "_generate", staticmethod(generate))
    messages = [
        Message(content="You are thoughtful", category="Compliment"),
        Message(content="Keep going", category=None),
    ]

    result = asyncio.run(AIService.summarize_inbox(messages))

    assert result == "Main themes are appreciation."
    assert "[Compliment] You are thoughtful" in prompts[0]
    assert "- Keep going" in prompts[0]


def test_summarize_inbox_rejects_empty_list(monkeypatch):
    async def should_not_generate(_prompt):
        pytest.fail("Empty summaries must be rejected before generation")

    monkeypatch.setattr(AIService, "_generate", staticmethod(should_not_generate))

    with pytest.raises(ValueError, match="No messages to summarize."):
        asyncio.run(AIService.summarize_inbox([]))


def test_suggest_reply_includes_message_and_category(monkeypatch):
    prompts = []

    async def generate(prompt):
        prompts.append(prompt)
        return "Thanks for sharing."

    monkeypatch.setattr(AIService, "_generate", staticmethod(generate))
    message = Message(content="I like your work", category="Compliment")

    result = asyncio.run(AIService.suggest_reply(message))

    assert result == "Thanks for sharing."
    assert "category: Compliment" in prompts[0]
    assert '"I like your work"' in prompts[0]


def test_suggest_reply_works_without_category(monkeypatch):
    prompts = []

    async def generate(prompt):
        prompts.append(prompt)
        return "Thank you."

    monkeypatch.setattr(AIService, "_generate", staticmethod(generate))

    asyncio.run(AIService.suggest_reply(Message(content="A note", category=None)))

    assert "(category:" not in prompts[0]
