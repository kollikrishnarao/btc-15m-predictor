"""
Base agent class — all specialist agents inherit from this.
Provides common LLM calling, structured output, and logging.
"""
from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import anthropic

from config.constants import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL

log = logging.getLogger(__name__)


@dataclass
class AgentSignal:
    """Output format from every specialist agent."""
    dimension: str
    score: float          # 0.0–1.0, 0.5 = neutral
    confidence: float    # How sure this agent is of its score
    regime: str           # TRENDING_UP / TRENDING_DOWN / RANGING / VOLATILE
    key_signals: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    raw_reasoning: str = ""
    latency_ms: float = 0.0


class BaseAgent(ABC):
    """
    Abstract base for all specialist agents.
    Subclasses define: name, model, system_prompt, analyze_dimensions().
    """

    name: str = "BASE_AGENT"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1024
    temperature: float = 0.3

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self._client: Optional[anthropic.AsyncAnthropic] = None

    async def __aenter__(self):
        if self.api_key:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=ANTHROPIC_BASE_URL,
            )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The agent's system prompt — must be overridden."""
        ...

    @abstractmethod
    async def analyze(self, state, reflection: dict) -> dict[str, AgentSignal]:
        """Produce signals keyed by dimension name (one per dimension owned)."""
        ...

    @abstractmethod
    def build_prompt(self, state, reflection: dict) -> str:
        """Build the analysis prompt from market state."""
        ...

    async def call_llm(self, user_prompt: str, system_prompt: str = "",
                       max_tokens: Optional[int] = None) -> tuple[str, float]:
        """Call the LLM and return (text, latency_ms)."""
        if not self._client:
            log.warning(f"{self.name}: no API key — returning neutral signal")
            return "", 0.0

        t0 = asyncio.get_event_loop().time()
        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=self.temperature,
                system=(system_prompt or self.system_prompt),
                messages=[{"role": "user", "content": user_prompt}],
            )
            latency = (asyncio.get_event_loop().time() - t0) * 1000
            text = ""
            for block in resp.content:
                if block.type == "text":
                    text += block.text
            return text, latency
        except Exception as e:
            log.error(f"{self.name} LLM call failed: {e}")
            return "", 0.0

    def parse_signal_json(self, raw: str) -> dict:
        """Parse a JSON signal from LLM output."""
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
