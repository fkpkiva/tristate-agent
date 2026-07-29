"""test_v02.py -- Smoke tests for tristate-agent v0.2 features.

Tests:
  1. Package imports cleanly at v0.2.0
  2. ResearchAgent instantiation + milestone + handoff
  3. WritingAgent draft + handoff to ReviewAgent
  4. ReviewAgent record_review + send_feedback
  5. TristateOrchestrator.register_agent + process_handoffs + all_milestones
  6. get_phase_profile() merge logic
  7. SiloStore ingest + query (NullEmbedder path)
  8. make_embedder('null') round-trip

Run with:  python -m pytest test_v02.py -v
       or:  python test_v02.py
"""
import sys
import os
import tempfile

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.dirname(__file__))


def _store():
  from tristate_agent.session_store import SessionStore
  return SessionStore  # just import, don't instantiate


# ---------------------------------------------------------------------------
# 1. Import smoke
# ---------------------------------------------------------------------------
def test_imports():
  import tristate_agent as ta
  assert ta.__version__ == "0.2.0"
  assert hasattr(ta, "ResearchAgent")
  assert hasattr(ta, "WritingAgent")
  assert hasattr(ta, "ReviewAgent")
  assert hasattr(ta, "PhaseAwareAgent")
  assert hasattr(ta, "SiloStore")
  assert hasattr(ta, "make_embedder")
  assert hasattr(ta, "get_phase_profile")
  print("PASS test_imports")


# ---------------------------------------------------------------------------
# 2. ResearchAgent
# ---------------------------------------------------------------------------
def test_research_agent():
  from tristate_agent.agents import ResearchAgent
  from tristate_agent.session_store import SessionStore

  with tempfile.TemporaryDirectory() as td:
    store = SessionStore(td)
    agent = ResearchAgent(agent_id="ra_0", session_store=store)

    assert agent.phase == "research"
    assert agent.drift_gate == 0.45

    agent.log_query("What is tristate logic?")
    agent.log_source("https://example.com", relevance=0.9)

    assert len(agent.queries) == 1
    assert len(agent.sources) == 1
    assert len(agent.milestones) == 2
    assert agent.milestones[0]["label"] == "query"
    assert agent.milestones[1]["label"] == "source"

    agent.handoff_to_writer("wa_0", summary="Tristate uses 1/Z/0 states.")
    handoffs = agent.drain_handoffs()
    assert len(handoffs) == 1
    assert handoffs[0]["to"] == "wa_0"
    assert handoffs[0]["reason"] == "research_complete"

  print("PASS test_research_agent")


# ---------------------------------------------------------------------------
# 3. WritingAgent
# ---------------------------------------------------------------------------
def test_writing_agent():
  from tristate_agent.agents import WritingAgent
  from tristate_agent.session_store import SessionStore

  with tempfile.TemporaryDirectory() as td:
    store = SessionStore(td)
    agent = WritingAgent(agent_id="wa_0", session_store=store)

    assert agent.phase == "writing"
    assert agent.drift_gate == 0.35

    agent.commit_draft("Draft v1 content here.", version=1)
    assert len(agent.drafts) == 1
    assert agent.latest_draft()["version"] == 1

    agent.handoff_to_reviewer("rv_0", notes="Please check tone.")
    handoffs = agent.drain_handoffs()
    assert handoffs[0]["reason"] == "draft_ready_for_review"
    assert handoffs[0]["payload"]["version"] == 1

  print("PASS test_writing_agent")


# ---------------------------------------------------------------------------
# 4. ReviewAgent
# ---------------------------------------------------------------------------
def test_review_agent():
  from tristate_agent.agents import ReviewAgent
  from tristate_agent.session_store import SessionStore

  with tempfile.TemporaryDirectory() as td:
    store = SessionStore(td)
    agent = ReviewAgent(agent_id="rv_0", session_store=store)

    assert agent.phase == "review"

    agent.record_review(version=1, decision="revise", comments="Needs more detail.")
    assert len(agent.reviews) == 1
    assert agent.latest_review()["decision"] == "revise"

    agent.send_feedback("wa_0", version=1, comments="Add section 3.")
    handoffs = agent.drain_handoffs()
    assert handoffs[0]["reason"] == "revision_requested"

    # invalid decision should raise
    try:
      agent.record_review(version=2, decision="maybe")
      assert False, "Should have raised ValueError"
    except ValueError:
      pass

  print("PASS test_review_agent")


# ---------------------------------------------------------------------------
# 5. Orchestrator handoff routing + milestone aggregation
# ---------------------------------------------------------------------------
def test_orchestrator_handoffs():
  from tristate_agent.orchestrator import TristateOrchestrator
  from tristate_agent.agents import ResearchAgent, WritingAgent
  from tristate_agent.session_store import SessionStore

  with tempfile.TemporaryDirectory() as td:
    store = SessionStore(td)
    orch = TristateOrchestrator(domain="research")

    ra = ResearchAgent(agent_id="ra_1", session_store=store)
    wa = WritingAgent(agent_id="wa_1", session_store=store)

    orch.register_agent(ra, make_active=True)
    orch.register_agent(wa)

    ra.log_query("query A")
    ra.handoff_to_writer("wa_1", summary="done")

    processed = orch.process_handoffs()
    assert len(processed) == 1
    assert orch.active_agent_id == "wa_1"

    milestones = orch.all_milestones()
    assert any(m["label"] == "query" for m in milestones)

    snap = orch.registry_snapshot()
    ra_snap = next(s for s in snap if s["agent_id"] == "ra_1")
    assert "phase" in ra_snap
    assert ra_snap["phase"] == "research"

  print("PASS test_orchestrator_handoffs")


# ---------------------------------------------------------------------------
# 6. get_phase_profile merge
# ---------------------------------------------------------------------------
def test_phase_profile():
  from tristate_agent.domain_profiles import get_phase_profile

  profile = get_phase_profile("business_planning", "research")
  assert profile["drift_threshold"] == 0.75
  assert "phases" not in profile

  profile_default = get_phase_profile("general")
  assert profile_default["drift_threshold"] == 0.50

  print("PASS test_phase_profile")


# ---------------------------------------------------------------------------
# 7. SiloStore ingest + query (NullEmbedder -- no real vectors)
# ---------------------------------------------------------------------------
def test_silo_store():
  from tristate_agent.session_store import SiloStore

  with tempfile.TemporaryDirectory() as td:
    silo = SiloStore(td)
    assert len(silo) == 0

    rid = silo.ingest("hello world", metadata={"agent_id": "ra_0"})
    assert rid.startswith("silo_0_")
    assert len(silo) == 1

    silo.ingest("second record")
    assert len(silo) == 2

    # query with null embedder returns score 0.0 for all
    results = silo.query("hello", top_k=5)
    assert len(results) == 2

    # filter_metadata
    filtered = silo.query("hello", filter_metadata={"agent_id": "ra_0"})
    assert len(filtered) == 1
    assert filtered[0]["metadata"]["agent_id"] == "ra_0"

    ids = silo.record_ids()
    assert len(ids) == 2

    silo.clear()
    assert len(silo) == 0

  print("PASS test_silo_store")


# ---------------------------------------------------------------------------
# 8. make_embedder null
# ---------------------------------------------------------------------------
def test_make_embedder_null():
  from tristate_agent.embedder import make_embedder, NullEmbedder

  embed = make_embedder("null")
  result = embed("test text")
  assert result == []

  null_obj = NullEmbedder()
  assert null_obj("anything") == []

  print("PASS test_make_embedder_null")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
  test_imports()
  test_research_agent()
  test_writing_agent()
  test_review_agent()
  test_orchestrator_handoffs()
  test_phase_profile()
  test_silo_store()
  test_make_embedder_null()
  print("\nAll v0.2 smoke tests passed.")
