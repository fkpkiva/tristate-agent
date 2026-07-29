"""agents.py – Specialised AgentNode subclasses for v0.2.

Defines ResearchAgent, WritingAgent, and ReviewAgent, each with
phase-aware drift thresholds and milestone tracking.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .agent_node import AgentNode
from .drift import compute_drift_score


# ---------------------------------------------------------------------------
# Phase label constants (matches PROTOCOL.md tristate labels)
# ---------------------------------------------------------------------------
PHASE_RESEARCH = "research"
PHASE_WRITING = "writing"
PHASE_REVIEW = "review"


# ---------------------------------------------------------------------------
# Drift threshold presets per phase
# ---------------------------------------------------------------------------
DRIFT_THRESHOLDS: Dict[str, Dict[str, float]] = {
  PHASE_RESEARCH: {"drift_gate": 0.45, "durability_gate": 0.30},
  PHASE_WRITING:  {"drift_gate": 0.35, "durability_gate": 0.25},
  PHASE_REVIEW:   {"drift_gate": 0.40, "durability_gate": 0.28},
}


class PhaseAwareAgent(AgentNode):
  """Base mixin that adds phase tracking and milestone management."""

  def __init__(
    self,
    agent_id: str,
    domain: str,
    phase: str,
    session_store: Any,
    *,
    embed_fn: Optional[Any] = None,
    **kwargs: Any,
  ) -> None:
    if phase not in DRIFT_THRESHOLDS:
      raise ValueError(f"Unknown phase '{phase}'. Choose from {list(DRIFT_THRESHOLDS)}.")

    thresholds = DRIFT_THRESHOLDS[phase]
    super().__init__(
      agent_id=agent_id,
      domain=domain,
      session_store=session_store,
      embed_fn=embed_fn,
      drift_gate=thresholds["drift_gate"],
      durability_gate=thresholds["durability_gate"],
      **kwargs,
    )
    self._phase: str = phase
    self._milestones: List[Dict[str, Any]] = []
    self._cross_branch_requests: List[Dict[str, Any]] = []

  # ------------------------------------------------------------------
  # Phase accessors
  # ------------------------------------------------------------------
  @property
  def phase(self) -> str:
    return self._phase

  def transition_phase(self, new_phase: str) -> None:
    """Move to a new workflow phase and update drift thresholds."""
    if new_phase not in DRIFT_THRESHOLDS:
      raise ValueError(f"Unknown phase '{new_phase}'.")
    self._phase = new_phase
    thresholds = DRIFT_THRESHOLDS[new_phase]
    self.drift_gate = thresholds["drift_gate"]
    self.durability_gate = thresholds["durability_gate"]

  # ------------------------------------------------------------------
  # Milestone tracking
  # ------------------------------------------------------------------
  def add_milestone(self, label: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Record a named milestone with optional metadata."""
    record = {
      "label": label,
      "phase": self._phase,
      "timestamp": time.time(),
      "metadata": metadata or {},
    }
    self._milestones.append(record)

  @property
  def milestones(self) -> List[Dict[str, Any]]:
    return list(self._milestones)

  def latest_milestone(self) -> Optional[Dict[str, Any]]:
    return self._milestones[-1] if self._milestones else None

  # ------------------------------------------------------------------
  # Cross-branch (micro-wake) handoff
  # ------------------------------------------------------------------
  def request_handoff(
    self,
    target_agent_id: str,
    payload: Dict[str, Any],
    reason: str = "",
  ) -> None:
    """Queue a micro-wake handoff request to another agent."""
    self._cross_branch_requests.append(
      {
        "from": self.agent_id,
        "to": target_agent_id,
        "payload": payload,
        "reason": reason,
        "timestamp": time.time(),
      }
    )

  def drain_handoffs(self) -> List[Dict[str, Any]]:
    """Return and clear all pending handoff requests."""
    pending = list(self._cross_branch_requests)
    self._cross_branch_requests.clear()
    return pending

  # ------------------------------------------------------------------
  # Snapshot extension – persist phase + milestones
  # ------------------------------------------------------------------
  def snapshot(self) -> Dict[str, Any]:
    base = super().snapshot()
    base["phase"] = self._phase
    base["milestones"] = list(self._milestones)
    return base


# ---------------------------------------------------------------------------
# Specialised agent types
# ---------------------------------------------------------------------------

class ResearchAgent(PhaseAwareAgent):
  """Agent specialised for research and information gathering.

  Characteristics
  ---------------
  - Higher drift gate tolerance (exploratory by nature).
  - Tracks sources and queries as milestones.
  - Can hand off synthesis tasks to a WritingAgent.
  """

  def __init__(
    self,
    agent_id: str,
    session_store: Any,
    *,
    embed_fn: Optional[Any] = None,
    **kwargs: Any,
  ) -> None:
    super().__init__(
      agent_id=agent_id,
      domain="research",
      phase=PHASE_RESEARCH,
      session_store=session_store,
      embed_fn=embed_fn,
      **kwargs,
    )
    self._queries: List[str] = []
    self._sources: List[str] = []

  def log_query(self, query: str) -> None:
    """Record a research query."""
    self._queries.append(query)
    self.add_milestone("query", {"query": query})

  def log_source(self, source: str, relevance: float = 1.0) -> None:
    """Record a source reference."""
    self._sources.append(source)
    self.add_milestone("source", {"source": source, "relevance": relevance})

  @property
  def queries(self) -> List[str]:
    return list(self._queries)

  @property
  def sources(self) -> List[str]:
    return list(self._sources)

  def handoff_to_writer(
    self,
    target_agent_id: str,
    summary: str,
  ) -> None:
    """Trigger a micro-wake handoff to a WritingAgent with research summary."""
    self.request_handoff(
      target_agent_id=target_agent_id,
      payload={
        "summary": summary,
        "queries": self._queries,
        "sources": self._sources,
      },
      reason="research_complete",
    )


class WritingAgent(PhaseAwareAgent):
  """Agent specialised for drafting and editing content.

  Characteristics
  ---------------
  - Lower drift gate (tighter focus on current draft).
  - Tracks draft versions as milestones.
  - Can request review via handoff to ReviewAgent.
  """

  def __init__(
    self,
    agent_id: str,
    session_store: Any,
    *,
    embed_fn: Optional[Any] = None,
    **kwargs: Any,
  ) -> None:
    super().__init__(
      agent_id=agent_id,
      domain="writing",
      phase=PHASE_WRITING,
      session_store=session_store,
      embed_fn=embed_fn,
      **kwargs,
    )
    self._drafts: List[Dict[str, Any]] = []

  def commit_draft(self, content: str, version: int) -> None:
    """Save a draft version and mark it as a milestone."""
    record = {"version": version, "content": content, "timestamp": time.time()}
    self._drafts.append(record)
    self.add_milestone("draft_committed", {"version": version, "length": len(content)})

  @property
  def drafts(self) -> List[Dict[str, Any]]:
    return list(self._drafts)

  def latest_draft(self) -> Optional[Dict[str, Any]]:
    return self._drafts[-1] if self._drafts else None

  def handoff_to_reviewer(
    self,
    target_agent_id: str,
    notes: str = "",
  ) -> None:
    """Trigger a micro-wake handoff to a ReviewAgent."""
    latest = self.latest_draft()
    self.request_handoff(
      target_agent_id=target_agent_id,
      payload={
        "draft": latest["content"] if latest else "",
        "version": latest["version"] if latest else 0,
        "notes": notes,
      },
      reason="draft_ready_for_review",
    )


class ReviewAgent(PhaseAwareAgent):
  """Agent specialised for quality review and feedback.

  Characteristics
  ---------------
  - Balanced drift gate.
  - Tracks review decisions (approve / revise / reject).
  - Can loop feedback back to a WritingAgent.
  """

  DECISION_APPROVE = "approve"
  DECISION_REVISE = "revise"
  DECISION_REJECT = "reject"

  def __init__(
    self,
    agent_id: str,
    session_store: Any,
    *,
    embed_fn: Optional[Any] = None,
    **kwargs: Any,
  ) -> None:
    super().__init__(
      agent_id=agent_id,
      domain="review",
      phase=PHASE_REVIEW,
      session_store=session_store,
      embed_fn=embed_fn,
      **kwargs,
    )
    self._reviews: List[Dict[str, Any]] = []

  def record_review(
    self,
    version: int,
    decision: str,
    comments: str = "",
  ) -> None:
    """Record a review decision."""
    if decision not in (
      self.DECISION_APPROVE,
      self.DECISION_REVISE,
      self.DECISION_REJECT,
    ):
      raise ValueError(f"Invalid decision '{decision}'.")
    record = {
      "version": version,
      "decision": decision,
      "comments": comments,
      "timestamp": time.time(),
    }
    self._reviews.append(record)
    self.add_milestone("review", {"version": version, "decision": decision})

  @property
  def reviews(self) -> List[Dict[str, Any]]:
    return list(self._reviews)

  def latest_review(self) -> Optional[Dict[str, Any]]:
    return self._reviews[-1] if self._reviews else None

  def send_feedback(
    self,
    target_agent_id: str,
    version: int,
    comments: str,
  ) -> None:
    """Hand off revision feedback to a WritingAgent."""
    self.request_handoff(
      target_agent_id=target_agent_id,
      payload={"version": version, "comments": comments},
      reason="revision_requested",
    )
