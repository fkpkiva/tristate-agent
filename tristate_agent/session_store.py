"""
session_store.py -- SessionStore: disk persistence for the Zero Loss Contract.

Writes / reads:
  <session_dir>/manifest.json       -- session-level index
  <session_dir>/orchestrator.json   -- ParentOrchestrator state
  <session_dir>/agent_<N>.json      -- one file per AgentNode (full raw history)
All writes are atomic (write to .tmp then rename) to prevent corruption.

v0.2 additions:
  SiloStore -- lightweight RAG ingest/query store backed by a JSON
  vector index (no external dependencies).  Swap the _backend for
  chromadb when available.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class SessionStore:
  """
  Handles all disk I/O for a tristate-agent session.
  Conforms to the Zero Loss Contract: no content is merged or
  compressed during save/load operations.
  """

  MANIFEST_FILE = "manifest.json"
  ORCHESTRATOR_FILE = "orchestrator.json"

  def __init__(self, session_dir: str) -> None:
    self.session_dir = Path(session_dir)
    self.session_dir.mkdir(parents=True, exist_ok=True)

  # ------------------------------------------------------------------
  # Atomic write helper
  # ------------------------------------------------------------------
  def _atomic_write(self, path: Path, data: dict) -> None:
    """Write JSON atomically: tmp file -> rename."""
    dir_ = path.parent
    with tempfile.NamedTemporaryFile(
      mode="w",
      encoding="utf-8",
      dir=dir_,
      delete=False,
      suffix=".tmp",
    ) as fh:
      json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp_path = fh.name
    os.replace(tmp_path, path)

  def _read_json(self, path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
      return json.load(fh)

  # ------------------------------------------------------------------
  # Save
  # ------------------------------------------------------------------
  def save(self, parent_orch) -> None:
    """
    Persist a ParentOrchestrator to disk.
    Each AgentNode is saved to its own file (Zero Loss Contract).
    """
    orch = parent_orch.orchestrator

    # 1. Save each agent individually
    for aid, agent in orch.agents.items():
      agent_path = self.session_dir / f"{aid}.json"
      self._atomic_write(agent_path, agent.to_dict())

    # 2. Save orchestrator state (without raw agent histories)
    orch_snapshot = {
      "domain": orch.domain,
      "active_agent_id": orch.active_agent_id,
      "total_agents_spawned": orch.total_agents_spawned,
      "agent_order": orch.agent_order,
    }
    self._atomic_write(
      self.session_dir / self.ORCHESTRATOR_FILE, orch_snapshot
    )

    # 3. Save manifest
    manifest = {
      "session_id": parent_orch.session_id,
      "domain": parent_orch.domain,
      "master_summary": parent_orch.master_summary,
      "message_count": parent_orch.message_count,
      "session_history": parent_orch.session_history,
      "active_agent_id": orch.active_agent_id,
      "total_agents_spawned": orch.total_agents_spawned,
      "agent_order": orch.agent_order,
    }
    self._atomic_write(self.session_dir / self.MANIFEST_FILE, manifest)

  # ------------------------------------------------------------------
  # Load
  # ------------------------------------------------------------------
  def load(self):
    """
    Restore a ParentOrchestrator from disk.
    Returns a fully reconstructed ParentOrchestrator instance.
    Raises FileNotFoundError if session_dir has no manifest.
    """
    from .parent_orchestrator import ParentOrchestrator
    from .orchestrator import TristateOrchestrator
    from .agent_node import AgentNode
    from .domain_profiles import get_domain_profile

    manifest_path = self.session_dir / self.MANIFEST_FILE
    if not manifest_path.exists():
      raise FileNotFoundError(
        f"No session manifest found at {manifest_path}. "
        "Cannot restore session."
      )
    manifest = self._read_json(manifest_path)
    agent_order = manifest["agent_order"]

    # Load each agent from its own file
    agents = {}
    for aid in agent_order:
      agent_path = self.session_dir / f"{aid}.json"
      if not agent_path.exists():
        raise FileNotFoundError(
          f"Agent file missing: {agent_path}. Session may be corrupted."
        )
      agents[aid] = AgentNode.from_dict(self._read_json(agent_path))

    # Reconstruct TristateOrchestrator
    orch = TristateOrchestrator.__new__(TristateOrchestrator)
    orch.domain = manifest["domain"]
    orch.profile = get_domain_profile(orch.domain)
    orch.active_agent_id = manifest["active_agent_id"]
    orch.total_agents_spawned = manifest["total_agents_spawned"]
    orch.agent_order = agent_order
    orch.agents = agents
    orch._pending_handoffs = []

    # Reconstruct ParentOrchestrator
    po = ParentOrchestrator.__new__(ParentOrchestrator)
    po.session_id = manifest["session_id"]
    po.domain = manifest["domain"]
    po.master_summary = manifest["master_summary"]
    po.message_count = manifest["message_count"]
    po.session_history = manifest["session_history"]
    po.orchestrator = orch
    return po

  # ------------------------------------------------------------------
  # Helpers
  # ------------------------------------------------------------------
  def session_exists(self) -> bool:
    """Return True if a valid session manifest exists on disk."""
    return (self.session_dir / self.MANIFEST_FILE).exists()

  def list_agent_files(self) -> list:
    """Return sorted list of agent JSON file paths in this session."""
    return sorted(self.session_dir.glob("agent_*.json"))

  def manifest(self) -> Optional[dict]:
    """Load and return the manifest dict, or None if not found."""
    path = self.session_dir / self.MANIFEST_FILE
    if not path.exists():
      return None
    return self._read_json(path)


# ---------------------------------------------------------------------------
# v0.2  SiloStore -- lightweight RAG ingest / query store
# ---------------------------------------------------------------------------

EmbedFn = Callable[[str], List[float]]


class SiloStore:
  """
  SILO ingest pipeline: stores (text, embedding, metadata) records and
  supports nearest-neighbour retrieval by cosine similarity.

  Backend is a plain JSON file so it works with zero extra dependencies.
  When chromadb is installed the ChromaBackend can be swapped in.

  Usage
  -----
    silo = SiloStore("./my_silo", embed_fn=make_embedder('null'))
    silo.ingest("Research note about topic X", metadata={"agent": "agent_0"})
    results = silo.query("topic X", top_k=3)
  """

  SILO_FILE = "silo_index.json"

  def __init__(
    self,
    silo_dir: str,
    embed_fn: Optional[EmbedFn] = None,
  ) -> None:
    self.silo_dir = Path(silo_dir)
    self.silo_dir.mkdir(parents=True, exist_ok=True)
    self._embed_fn: EmbedFn = embed_fn or self._null_embed
    self._records: List[Dict[str, Any]] = []
    self._load()

  # ------------------------------------------------------------------
  # Null embed fallback (returns empty vector)
  # ------------------------------------------------------------------
  @staticmethod
  def _null_embed(text: str) -> List[float]:
    return []

  # ------------------------------------------------------------------
  # Persistence
  # ------------------------------------------------------------------
  def _index_path(self) -> Path:
    return self.silo_dir / self.SILO_FILE

  def _load(self) -> None:
    path = self._index_path()
    if path.exists():
      with open(path, "r", encoding="utf-8") as fh:
        self._records = json.load(fh)
    else:
      self._records = []

  def _save(self) -> None:
    path = self._index_path()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
      json.dump(self._records, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

  # ------------------------------------------------------------------
  # Ingest
  # ------------------------------------------------------------------
  def ingest(
    self,
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
  ) -> str:
    """Embed and store a text chunk. Returns the record ID."""
    record_id = f"silo_{len(self._records)}_{int(time.time())}"
    embedding = self._embed_fn(text)
    record = {
      "id": record_id,
      "text": text,
      "embedding": embedding,
      "metadata": metadata or {},
      "timestamp": time.time(),
    }
    self._records.append(record)
    self._save()
    return record_id

  def ingest_agent_history(
    self,
    agent,
    *,
    roles: Tuple[str, ...] = ("user", "assistant"),
  ) -> List[str]:
    """Ingest all history turns from an AgentNode.

    Only turns whose role is in *roles* are ingested.
    Returns list of record IDs.
    """
    ids: List[str] = []
    for turn in agent.history:
      if turn.get("role") not in roles:
        continue
      content = turn.get("content", "")
      if not content:
        continue
      rid = self.ingest(
        content,
        metadata={
          "agent_id": agent.agent_id,
          "role": turn["role"],
        },
      )
      ids.append(rid)
    return ids

  # ------------------------------------------------------------------
  # Query
  # ------------------------------------------------------------------
  @staticmethod
  def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
      return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
      return 0.0
    return dot / (norm_a * norm_b)

  def query(
    self,
    text: str,
    top_k: int = 5,
    min_score: float = 0.0,
    filter_metadata: Optional[Dict[str, Any]] = None,
  ) -> List[Dict[str, Any]]:
    """Return top_k most similar records to *text*.

    Each result dict contains: id, text, score, metadata, timestamp.
    """
    query_emb = self._embed_fn(text)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for rec in self._records:
      # metadata filter
      if filter_metadata:
        if not all(
          rec["metadata"].get(k) == v
          for k, v in filter_metadata.items()
        ):
          continue
      score = self._cosine(query_emb, rec["embedding"])
      if score >= min_score:
        scored.append((score, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
      {
        "id": rec["id"],
        "text": rec["text"],
        "score": score,
        "metadata": rec["metadata"],
        "timestamp": rec["timestamp"],
      }
      for score, rec in scored[:top_k]
    ]

  # ------------------------------------------------------------------
  # Helpers
  # ------------------------------------------------------------------
  def __len__(self) -> int:
    return len(self._records)

  def clear(self) -> None:
    """Remove all records and persist the empty index."""
    self._records = []
    self._save()

  def record_ids(self) -> List[str]:
    """Return list of all record IDs in insertion order."""
    return [r["id"] for r in self._records]
