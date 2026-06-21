"""
parent_orchestrator.py — ParentOrchestrator: session-level hub.
Holds the master summary, session history metadata, and
coordinates between TristateOrchestrator and SessionStore.
The orchestrator NEVER holds raw conversation content (Protocol §1).
"""

from __future__ import annotations

from typing import List, Optional

from .orchestrator import TristateOrchestrator
from .domain_profiles import DEFAULT_DOMAIN


class ParentOrchestrator:
    """
    Session-level coordinator.
    - Owns master_summary and session_history (lightweight metadata only).
    - Delegates per-turn routing to TristateOrchestrator.
    - Acts as the public API: user messages come in, agent responses go out.
    """

    def __init__(
        self,
        domain: str = DEFAULT_DOMAIN,
        session_id: Optional[str] = None,
    ) -> None:
        import uuid
        self.session_id: str = session_id or str(uuid.uuid4())
        self.domain = domain
        self.master_summary: str = ""
        self.session_history: List[dict] = []   # lightweight turn metadata
        self.message_count: int = 0
        self.orchestrator = TristateOrchestrator(domain=domain)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        message: str,
        role: str = "user",
        embedding: Optional[list] = None,
        token_count: int = 0,
        topic_hint: str = "",
    ) -> str:
        """
        Route an incoming message to the correct agent.
        Returns the agent_id that will handle the message.
        The caller is responsible for appending the message to agent.history.
        """
        self.message_count += 1

        # Route via TristateOrchestrator
        agent = self.orchestrator.route(
            message=message,
            embedding=embedding,
            token_count=token_count,
            topic_hint=topic_hint,
        )

        # Append the raw turn to the agent (Zero Loss Contract)
        turn: dict = {"role": role, "content": message}
        if embedding is not None:
            turn["embedding"] = embedding
        agent.history.append(turn)

        # Record lightweight metadata in session_history
        self.session_history.append({
            "turn": self.message_count,
            "role": role,
            "agent_id": agent.agent_id,
            "token_count": token_count,
        })

        return agent.agent_id

    def record_response(
        self,
        agent_id: str,
        content: str,
        token_count: int = 0,
        embedding: Optional[list] = None,
    ) -> None:
        """
        Append an assistant response to the specified agent's history.
        """
        agent = self.orchestrator.agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent_id: {agent_id}")

        turn: dict = {"role": "assistant", "content": content}
        if embedding is not None:
            turn["embedding"] = embedding
        agent.history.append(turn)
        agent.total_tokens += token_count

        self.message_count += 1
        self.session_history.append({
            "turn": self.message_count,
            "role": "assistant",
            "agent_id": agent_id,
            "token_count": token_count,
        })

    def update_master_summary(self, summary: str) -> None:
        """Update the top-level session summary (does NOT touch agent histories)."""
        self.master_summary = summary

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def active_agent(self):
        """Return the currently active AgentNode."""
        return self.orchestrator._active_agent()

    def agent_registry(self) -> List[dict]:
        """Lightweight snapshot of all agents."""
        return self.orchestrator.registry_snapshot()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "domain": self.domain,
            "master_summary": self.master_summary,
            "message_count": self.message_count,
            "session_history": self.session_history,
            "orchestrator": self.orchestrator.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ParentOrchestrator":
        obj = cls.__new__(cls)
        obj.session_id = data["session_id"]
        obj.domain = data["domain"]
        obj.master_summary = data["master_summary"]
        obj.message_count = data["message_count"]
        obj.session_history = data["session_history"]
        obj.orchestrator = TristateOrchestrator.from_dict(data["orchestrator"])
        return obj
