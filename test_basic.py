"""
test_basic.py — local smoke test for tristate-agent v0.1.0
No API or external dependencies needed.

Run:
    pip install -e .
    python test_basic.py
"""

import random
import json
import os
import shutil

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"

def check(label, condition):
    print(f"  {PASS if condition else FAIL}  {label}")
    if not condition:
        raise AssertionError(f"FAILED: {label}")


def fake_embedding(seed, dim=8):
    """Deterministic fake embedding vector."""
    random.seed(seed)
    return [random.uniform(-1, 1) for _ in range(dim)]


def opposing_embedding(seed, dim=8):
    """Embedding roughly opposite to fake_embedding(seed)."""
    base = fake_embedding(seed, dim)
    return [-x for x in base]


SESSION_DIR = "/tmp/tristate_test_session"

if os.path.exists(SESSION_DIR):
    shutil.rmtree(SESSION_DIR)

print("\n=" * 50)
print("tristate-agent v0.1.0 — smoke test")
print("=" * 50)

from tristate_agent import ParentOrchestrator, SessionStore

# ------------------------------------------------------------------ #
print("\n[1] Basic routing — single agent stays active")
# ------------------------------------------------------------------ #
po = ParentOrchestrator(domain="general")

aid0 = po.ingest("Tell me about Python", embedding=fake_embedding(1), token_count=10)
check("First message goes to agent_0", aid0 == "agent_0")
po.record_response(aid0, "Python is a programming language.", token_count=12)

aid1 = po.ingest("How do I use lists?", embedding=fake_embedding(1), token_count=8)
check("Same-topic message stays on agent_0", aid1 == "agent_0")
po.record_response(aid1, "Lists use square brackets.", token_count=10)

check("History has 2 user + 2 assistant turns",
      len(po.orchestrator.agents["agent_0"].history) == 4)

# ------------------------------------------------------------------ #
print("\n[2] Drift spawn — high-drift messages trigger new agent")
# ------------------------------------------------------------------ #
spawned = False
for i in range(8):
    emb = opposing_embedding(1)  # maximally different from Python anchor
    emb[i % 8] += 0.5 + i * 0.1  # vary slightly each turn
    aid = po.ingest(
        f"What is the best recipe for pasta? Turn {i}",
        embedding=emb,
        token_count=25,
        topic_hint="cooking"
    )
    if aid != "agent_0":
        spawned = True
        spawned_id = aid
        break
    po.record_response(aid, f"Pasta answer {i}", token_count=20)

check("A new agent was spawned after high-drift turns", spawned)
check("New agent id is agent_1", spawned_id == "agent_1")
print(f"    Spawned at turn {i+1}: {spawned_id}")

registry = po.agent_registry()
check("Registry has 2 agents", len(registry) == 2)
check("agent_0 is dormant (state=Z)", registry[0]["state"] == "Z")
check("agent_1 is active (state=1)", registry[1]["state"] == "1")

# ------------------------------------------------------------------ #
print("\n[3] Wake detection — verbal cue wakes dormant agent")
# ------------------------------------------------------------------ #
wake_aid = po.ingest(
    "back to Python — how do I use dictionaries?",
    embedding=fake_embedding(1),
    token_count=10
)
check("Verbal cue 'back to' wakes agent_0", wake_aid == "agent_0")
check("agent_0 is now active again",
      po.orchestrator.agents["agent_0"].sleeping == False)

# ------------------------------------------------------------------ #
print("\n[4] Session save & restore (Zero Loss Contract)")
# ------------------------------------------------------------------ #
store = SessionStore(SESSION_DIR)
store.save(po)

manifest_path = os.path.join(SESSION_DIR, "manifest.json")
check("manifest.json exists", os.path.exists(manifest_path))
check("agent_0.json exists", os.path.exists(os.path.join(SESSION_DIR, "agent_0.json")))
check("agent_1.json exists", os.path.exists(os.path.join(SESSION_DIR, "agent_1.json")))

with open(manifest_path) as f:
    manifest = json.load(f)
check("Manifest has correct session_id", manifest["session_id"] == po.session_id)
check("Manifest has 2 agents", len(manifest["agent_order"]) == 2)

# Restore
po2 = store.load()
check("Restored session_id matches", po2.session_id == po.session_id)
check("Restored active agent matches",
      po2.orchestrator.active_agent_id == po.orchestrator.active_agent_id)
check("Restored agent_0 history length matches",
      len(po2.orchestrator.agents["agent_0"].history) ==
      len(po.orchestrator.agents["agent_0"].history))
check("Restored total_agents_spawned matches",
      po2.orchestrator.total_agents_spawned == po.orchestrator.total_agents_spawned)

# ------------------------------------------------------------------ #
print("\n[5] agent_node serialization round-trip")
# ------------------------------------------------------------------ #
agent0 = po.orchestrator.agents["agent_0"]
d = agent0.to_dict()
from tristate_agent import AgentNode
restored = AgentNode.from_dict(d)
check("agent_id preserved", restored.agent_id == agent0.agent_id)
check("topic_label preserved", restored.topic_label == agent0.topic_label)
check("history length preserved", len(restored.history) == len(agent0.history))
check("turn_count preserved", restored.turn_count == agent0.turn_count)

# ------------------------------------------------------------------ #
print("\n" + "=" * 50)
print("All tests passed!")
print("=" * 50)

# Cleanup
shutil.rmtree(SESSION_DIR)
