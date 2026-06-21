"""
session_store.py — SessionStore: disk persistence for the Zero Loss Contract.

Writes / reads:
  <session_dir>/manifest.json          — session-level index
  <session_dir>/orchestrator.json      — ParentOrchestrator state
  <session_dir>/agent_<N>.json         — one file per AgentNode (full raw history)

All writes are atomic (write to .tmp then rename) to prevent corruption.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional


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
        from .parent_orchestrator import ParentOrchestrator  # avoid circular at module level

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
            # agent data lives in individual files — omit here
        }
        self._atomic_write(self.session_dir / self.ORCHESTRATOR_FILE, orch_snapshot)

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
        from .domain_profiles import get_domain_profile
        orch.domain = manifest["domain"]
        orch.profile = get_domain_profile(orch.domain)
        orch.active_agent_id = manifest["active_agent_id"]
        orch.total_agents_spawned = manifest["total_agents_spawned"]
        orch.agent_order = agent_order
        orch.agents = agents

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
