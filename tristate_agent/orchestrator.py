"""
orchestrator.py — TristateOrchestrator: routing, spawn/wake/sleep policy.
Policy decisions live here. Mechanics live in AgentNode.
"""
from __future__ import annotations
import uuid
from typing import Dict, List, Optional

from .agent_node import AgentNode
from .domain_profiles import get_domain_profile, DEFAULT_DOMAIN
from .drift import compute_drift_score, cosine_similarity

# Tristate labels per PROTOCOL.md
_STATE_ACTIVE = "1"
_STATE_DORMANT = "Z"
_STATE_TERMINATED = "0"


class TristateOrchestrator:
    """
    Routes user messages to the correct AgentNode.
    Owns all spawn / wake / sleep policy decisions.
    Implements the Two-Gate spawn rule (Drift Gate + Durability Gate).
    """

    def __init__(self, domain: str = DEFAULT_DOMAIN) -> None:
        self.domain = domain
        self.profile = get_domain_profile(domain)
        self.agents: Dict[str, AgentNode] = {}
        self.agent_order: List[str] = []  # insertion order
        self.active_agent_id: Optional[str] = None
        self.total_agents_spawned: int = 0
        self._spawn_first_agent()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _new_agent_id(self) -> str:
        return f"agent_{self.total_agents_spawned}"

    def _spawn_first_agent(self) -> None:
        aid = self._new_agent_id()
        node = AgentNode(agent_id=aid, topic_label="root")
        self.agents[aid] = node
        self.agent_order.append(aid)
        self.active_agent_id = aid
        self.total_agents_spawned += 1

    def _active_agent(self) -> AgentNode:
        return self.agents[self.active_agent_id]

    def _spawn_new_agent(self, topic_label: str = "") -> AgentNode:
        """Create a new AgentNode and make it active."""
        current = self._active_agent()
        current.sleep()
        aid = self._new_agent_id()
        node = AgentNode(agent_id=aid, topic_label=topic_label)
        self.agents[aid] = node
        self.agent_order.append(aid)
        self.active_agent_id = aid
        self.total_agents_spawned += 1
        return node

    @staticmethod
    def _agent_state_label(agent: AgentNode) -> str:
        """Return PROTOCOL tristate label: 1=active, Z=dormant, 0=terminated."""
        if agent.is_active:
            return _STATE_ACTIVE
        return _STATE_DORMANT

    # ------------------------------------------------------------------
    # Three-layer wake detection (Section 6)
    # ------------------------------------------------------------------
    def _try_wake_dormant(self, message: str, embedding: Optional[list]) -> Optional[str]:
        """
        Check dormant agents for a return signal.
        Returns agent_id if one should be woken, else None.
        Layer 1: verbal cue prefix
        Layer 2: wake keyword match
        Layer 3: embedding cosine similarity vs anchor
        """
        msg_lower = message.lower()
        verbal_cues = [
            "back to", "returning to", "let's go back", "resume",
            "continuing with", "as i was saying", "earlier topic",
        ]
        has_verbal_cue = any(cue in msg_lower for cue in verbal_cues)
        for aid in reversed(self.agent_order):
            agent = self.agents[aid]
            if not agent.sleeping:
                continue
            # Layer 1
            if has_verbal_cue:
                return aid
            # Layer 2: keyword match
            for kw in agent.wake_keywords:
                if kw.lower() in msg_lower:
                    return aid
            # Layer 3: embedding similarity
            if embedding is not None and agent.anchor_embedding is not None:
                sim = cosine_similarity(embedding, agent.anchor_embedding)
                if sim >= self.profile.get("wake_similarity_threshold", 0.85):
                    return aid
        return None

    # ------------------------------------------------------------------
    # Two-Gate spawn decision (Section 5)
    # ------------------------------------------------------------------
    def _check_spawn_gates(
        self,
        agent: AgentNode,
        drift_score: float,
        new_embedding: list,
    ) -> bool:
        """
        Returns True if both Gate 1 (Drift) and Gate 2 (Durability) fire.
        """
        drift_threshold = self.profile.get("drift_threshold", 0.4)
        max_turns = self.profile.get("max_detour_turns", 4)
        durability_ratio = self.profile.get("durability_ratio", 0.3)
        # Gate 1: semantic drift
        if drift_score < drift_threshold:
            if agent.drift_marker is not None:
                agent.drift_marker = None
            return False
        # Gate 1 passed — start watch period if not already tracking
        if agent.drift_marker is None:
            agent.drift_marker = agent.turn_count
        # Gate 2a: detour turn count
        detour_turns = agent.turn_count - agent.drift_marker
        if detour_turns >= max_turns:
            return True
        # Gate 2b: token ratio
        if agent.total_tokens > 0:
            ratio = agent.shifted_tokens / agent.total_tokens
            if ratio >= durability_ratio:
                return True
        return False

    # ------------------------------------------------------------------
    # Detour reabsorption (Section 8)
    # ------------------------------------------------------------------
    def _reabsorb_detour(self, agent: AgentNode, detour_turns: List[dict]) -> None:
        """
        Fold detour turns back into the active agent as a compact note.
        Clears drift_marker and does NOT spawn.
        """
        if not detour_turns:
            return
        note_content = "[detour-note] " + " | ".join(
            t.get("content", "") for t in detour_turns if t.get("role") == "user"
        )
        agent.history.append({"role": "system", "content": note_content})
        agent.drift_marker = None

    # ------------------------------------------------------------------
    # Main routing entry-point
    # ------------------------------------------------------------------
    def route(
        self,
        message: str,
        embedding: Optional[list] = None,
        token_count: int = 0,
        topic_hint: str = "",
    ) -> AgentNode:
        """
        Receive a user message and return the AgentNode that should handle it.
        Caller is responsible for appending the message to agent.history.
        """
        active = self._active_agent()
        # 1. Check for wake signal to a dormant agent
        wake_id = self._try_wake_dormant(message, embedding)
        if wake_id is not None and wake_id != self.active_agent_id:
            active.sleep()
            target = self.agents[wake_id]
            target.wake()
            self.active_agent_id = wake_id
            return target
        # 2. Update token tracking on active agent
        if embedding is not None and active.anchor_embedding is None:
            active.anchor_embedding = embedding
        active.turn_count += 1
        active.total_tokens += token_count
        # 3. Compute drift if we have an anchor embedding
        if embedding is not None and active.anchor_embedding is not None:
            recent: List[list] = [
                t["embedding"]
                for t in active.history
                if isinstance(t.get("embedding"), list)
            ][-5:]
            drift = compute_drift_score(
                new_embedding=embedding,
                anchor_embedding=active.anchor_embedding,
                recent_embeddings=recent or None,
            )
            drift_threshold = self.profile.get("drift_threshold", 0.4)
            if drift >= drift_threshold:
                active.shifted_tokens += token_count
            if self._check_spawn_gates(active, drift, embedding):
                new_agent = self._spawn_new_agent(topic_label=topic_hint)
                new_agent.anchor_embedding = embedding
                return new_agent
        return active

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------
    def registry_snapshot(self) -> List[dict]:
        """Return a lightweight snapshot of all agents for serialization."""
        return [
            {
                "agent_id": aid,
                "topic_label": self.agents[aid].topic_label,
                "state": self._agent_state_label(self.agents[aid]),
                "turn_count": self.agents[aid].turn_count,
            }
            for aid in self.agent_order
        ]

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "active_agent_id": self.active_agent_id,
            "total_agents_spawned": self.total_agents_spawned,
            "agent_order": self.agent_order,
            "agents": {aid: self.agents[aid].to_dict() for aid in self.agent_order},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TristateOrchestrator":
        obj = cls.__new__(cls)
        obj.domain = data["domain"]
        obj.profile = get_domain_profile(obj.domain)
        obj.active_agent_id = data["active_agent_id"]
        obj.total_agents_spawned = data["total_agents_spawned"]
        obj.agent_order = data["agent_order"]
        obj.agents = {
            aid: AgentNode.from_dict(adict)
            for aid, adict in data["agents"].items()
        }
        return obj
