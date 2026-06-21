"""
agent_node.py — AgentNode: tristate lifecycle owner.
Policy decisions (spawn/wake/sleep) live in orchestrator.
Mechanics (state tracking, serialization, history) live here.
"""

import json
from typing import List, Optional


class AgentNode:
    """
    Represents a single agent in the tristate system.
    States: active (1), dormant (Z), terminated (0).
    """

    def __init__(self, agent_id: str, topic_label: str = ""):
        self.agent_id = agent_id
        self.topic_label = topic_label
        self.sleeping: bool = False
        self.history: List[dict] = []
        self.summary: str = ""
        self.wake_keywords: List[str] = []
        self.anchor_embedding: Optional[list] = None
        self.turn_count: int = 0
        self.total_tokens: int = 0
        self.shifted_tokens: int = 0
        self.drift_marker: Optional[int] = None  # turn index where drift started

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return not self.sleeping

    @property
    def shifted_ratio(self) -> float:
        """Fraction of agent's total tokens that are on the shifted topic."""
        if self.total_tokens == 0:
            return 0.0
        return self.shifted_tokens / self.total_tokens

    def sleep(self):
        """Put agent into Z-state (dormant)."""
        self.sleeping = True

    def wake(self):
        """Restore agent from Z-state to active."""
        self.sleeping = False

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def add_turn(self, role: str, content: str, shifted: bool = False):
        """Add a conversation turn to this agent's history."""
        self.history.append({"role": role, "content": content})
        tokens = len(content.split())
        self.total_tokens += tokens
        if shifted:
            self.shifted_tokens += tokens
        self.turn_count += 1

    def add_tokens(self, count: int, shifted: bool = False):
        """Manually track token counts (e.g. from API usage)."""
        self.total_tokens += count
        if shifted:
            self.shifted_tokens += count

    def place_drift_marker(self):
        """Mark the current turn index as the start of a drift."""
        self.drift_marker = len(self.history)

    def get_history_since_marker(self) -> List[dict]:
        """Return history turns from the drift marker onward."""
        if self.drift_marker is None:
            return []
        return self.history[self.drift_marker:]

    def clean_since_marker(self):
        """
        Erase all turns since the drift marker from this agent's context.
        Called after copying since-marker content to the new agent.
        Keeps the agent clean — only holds content relevant to its own topic.
        """
        if self.drift_marker is None:
            return
        self.history = self.history[:self.drift_marker]
        self.drift_marker = None
        self.shifted_tokens = 0

    def accept_transferred_history(self, turns: List[dict]):
        """Accept history transferred from a previous agent (since-marker content)."""
        self.history = turns + self.history
        self.turn_count = len(self.history)

    def clear_drift_marker(self):
        """Clear the drift marker without erasing content (reabsorption case)."""
        self.drift_marker = None
        self.shifted_tokens = 0

    # ------------------------------------------------------------------
    # Serialization — zero-loss save/restore
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize agent to a JSON-compatible dict. Zero loss."""
        return {
            "agent_id": self.agent_id,
            "topic_label": self.topic_label,
            "sleeping": self.sleeping,
            "history": self.history,
            "summary": self.summary,
            "wake_keywords": self.wake_keywords,
            "anchor_embedding": self.anchor_embedding,
            "turn_count": self.turn_count,
            "total_tokens": self.total_tokens,
            "shifted_tokens": self.shifted_tokens,
            "drift_marker": self.drift_marker,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentNode":
        """Restore agent from a saved dict. Zero loss."""
        agent = cls(agent_id=data["agent_id"], topic_label=data["topic_label"])
        agent.sleeping = data["sleeping"]
        agent.history = data["history"]
        agent.summary = data["summary"]
        agent.wake_keywords = data["wake_keywords"]
        agent.anchor_embedding = data["anchor_embedding"]
        agent.turn_count = data["turn_count"]
        agent.total_tokens = data["total_tokens"]
        agent.shifted_tokens = data["shifted_tokens"]
        agent.drift_marker = data.get("drift_marker")
        return agent

    def save(self, path: str):
        """Save agent to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "AgentNode":
        """Load agent from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def __repr__(self) -> str:
        state = "dormant" if self.sleeping else "active"
        return (
            f"AgentNode(id={self.agent_id!r}, topic={self.topic_label!r}, "
            f"state={state}, turns={self.turn_count}, ratio={self.shifted_ratio:.2f})"
        )
