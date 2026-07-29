"""
tristate-agent v0.2.0
LLM memory branching via tristate agents.
SWORD conversation pipeline + SILO ingest pipeline (v0.2).

v0.2 additions: ResearchAgent, WritingAgent, ReviewAgent,
PhaseAwareAgent, embedder utilities, phase-aware domain profiles,
SiloStore RAG ingest/query pipeline.
"""

from .orchestrator import TristateOrchestrator
from .agent_node import AgentNode
from .parent_orchestrator import ParentOrchestrator
from .session_store import SessionStore, SiloStore

# v0.2 specialised agents
from .agents import (
  PhaseAwareAgent,
  ResearchAgent,
  WritingAgent,
  ReviewAgent,
  PHASE_RESEARCH,
  PHASE_WRITING,
  PHASE_REVIEW,
  DRIFT_THRESHOLDS,
)

# v0.2 embedder utilities
from .embedder import (
  OllamaEmbedder,
  OpenAIEmbedder,
  NullEmbedder,
  make_embedder,
)

# v0.2 domain profile helpers
from .domain_profiles import (
  get_domain_profile,
  get_phase_profile,
  list_domains,
  DOMAIN_PROFILES,
  DEFAULT_DOMAIN,
)

__version__ = "0.2.0"
__author__ = "fkpkiva"

__all__ = [
  # Core v0.1
  "TristateOrchestrator",
  "AgentNode",
  "ParentOrchestrator",
  "SessionStore",
  # v0.2 SILO
  "SiloStore",
  # v0.2 agents
  "PhaseAwareAgent",
  "ResearchAgent",
  "WritingAgent",
  "ReviewAgent",
  "PHASE_RESEARCH",
  "PHASE_WRITING",
  "PHASE_REVIEW",
  "DRIFT_THRESHOLDS",
  # v0.2 embedder
  "OllamaEmbedder",
  "OpenAIEmbedder",
  "NullEmbedder",
  "make_embedder",
  # v0.2 domain profiles
  "get_domain_profile",
  "get_phase_profile",
  "list_domains",
  "DOMAIN_PROFILES",
  "DEFAULT_DOMAIN",
]
