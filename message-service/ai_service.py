from typing import List
import httpx
from database import Message

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


class AIService:
    @staticmethod
    async def _generate(prompt: str) -> str:
        """Generate non-streaming text through the configured local Ollama model."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    OLLAMA_URL,
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                )
            except httpx.RequestError:
                raise ValueError("AI service is unavailable. Is Ollama running?")

            if response.status_code != 200:
                raise ValueError("AI service is unavailable. Is Ollama running?")

            data = response.json()
            text = data.get("response", "").strip()
            if not text:
                raise ValueError("AI service returned an empty response.")
            return text

    @classmethod
    async def summarize_inbox(cls, messages: List[Message]) -> str:
        """Ask the model for a short summary of active feedback messages."""
        if not messages:
            raise ValueError("No messages to summarize.")

        lines = []
        for m in messages:
            tag = f" [{m.category}]" if m.category else ""
            lines.append(f"-{tag} {m.content}")
        feedback_block = "\n".join(lines)

        prompt = (
            "You are summarizing anonymous feedback messages sent to one person's inbox. "
            "Read the messages below and write a short summary (3-5 sentences) covering the "
            "main themes, the overall sentiment, and any standout messages. "
            "Do not list every message individually.\n\n"
            f"Messages:\n{feedback_block}\n\nSummary:"
        )
        return await cls._generate(prompt)

    @classmethod
    async def suggest_reply(cls, message: Message) -> str:
        """Ask the model for a short draft reply to one feedback message."""
        category_hint = f" (category: {message.category})" if message.category else ""
        prompt = (
            "Someone received this anonymous feedback message"
            f"{category_hint}: \"{message.content}\"\n\n"
            "Write one short, friendly, casual draft reply from the inbox owner, "
            "1-3 sentences. Return only the reply text, with no quotes or preamble."
        )
        return await cls._generate(prompt)
