"""OpenRouter adapter — drop-in replacement for the anthropic module."""

import os
from openai import OpenAI

DEFAULT_MODEL = os.getenv("AI_MODEL", "anthropic/claude-sonnet-4-6")


class _Msg:
    def __init__(self, text):
        self.content = [type('C', (), {'text': text})()]


class _Messages:
    def __init__(self, client):
        self._c = client

    def create(self, model=None, max_tokens=2000, messages=None, **kwargs):
        r = self._c.chat.completions.create(
            model=model or DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=messages or [],
        )
        return _Msg(r.choices[0].message.content)


class _Client:
    def __init__(self):
        self.messages = _Messages(OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        ))


def Anthropic():
    return _Client()
