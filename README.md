# tristate-agent

> LLM memory branching via tristate agents — SWORD conversation pipeline + SILO ingest pipeline.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-green)](CHANGELOG.md)

---

## What is tristate-agent?

Most LLM memory systems are **binary**: a message is either in the context window (active) or discarded (gone). Once a conversation grows long enough, older content is truncated and the model loses the thread.

**tristate-agent** introduces a third state — **dormant (Z-state)** — borrowed from electronics tristate logic (high / low / high-impedance). An agent in the Z-state is:
- Not consuming active context window tokens
- Fully preserved in memory with complete history
- Instantly restorable when its topic is referenced again

This means long, multi-topic conversations never lose context — they branch, sleep, and wake.

---

## The Tristate Model

| State | Symbol | Meaning |
|---|---|---|
| Active | `1` | Currently handling user messages, in live context |
| Dormant | `Z` | Sleeping — full history preserved, zero token cost |
| Terminated | `0` | Session ended — saved to disk, restorable |

This maps directly to the analogy:
- **Binary computers**: 0 and 1
- **Quantum computers**: 0, 1, and superposition
- **tristate-agent**: active, dormant, and Z-state

---

## Two Coordinated Pipelines

### SWORD — Conversation Branching Pipeline (v0.1)

| Letter | Step | Function |
|---|---|---|
| **S** | Score | Phi-decay drift scoring across recent turns |
| **W** | Watch | Two-gate durability check (turn count + context ratio) |
| **O** | Orchestrate | Parent registry coordination, agent routing |
| **R** | Recall | 3-layer return detection (verbal → keyword → embedding) |
| **D** | Detour | Short tangents reabsorbed; durable shifts spawn/wake agents |

### SILO — Content Ingestion Pipeline (v0.2, planned)

| Letter | Step | Function |
|---|---|---|
| **S** | Split | Structure-aware content splitting (chapters, sections, themes) |
| **I** | Index | Section agents digest and embed their assigned content |
| **L** | Lookup | Stateless retrieval — agents answer, clean context, sleep |
| **O** | Orchestrate | Same orchestrator manages both ingest and conversation agents |

---

## Core Architecture

```
ORCHESTRATOR (always lightweight — holds summaries only, never raw content)
    │
    ├── Topic Agent A  💤 dormant  (background-summarized before sleeping)
    ├── Topic Agent B  🟢 active   (currently answering user)
    └── Topic Agent C  💤 dormant
```

**Key rule**: The orchestrator NEVER holds raw conversation content. It holds only:
- Agent registry (id, topic label, summary, wake keywords)
- Master session summary
- Routing and coordination logic

Raw content always lives inside agents.

---

## Spawn & Sleep Rules

### Two-Gate Spawn Rule
A new agent spawns only when BOTH gates confirm a durable topic shift:

```
Gate 1 — DRIFT GATE (instantaneous)
  drift_score >= domain_threshold
  → detour is semantically real → start watching

Gate 2 — DURABILITY GATE (accumulates)
  EITHER: detour_turn_count >= domain_max_turns
  OR:     shifted_tokens / agent_total_tokens >= durability_ratio
  → shift is durable → SPAWN
```

### Sleep Protocol
1. Topic shift confirmed as durable
2. Marker placed at drift start
3. New agent spawns
4. Previous agent summarizes content since marker → sends to orchestrator
5. Previous agent copies content since marker to new agent
6. Previous agent erases content since marker from its own context (stays clean)
7. Previous agent produces final full summary → sends to orchestrator
8. Previous agent enters Z-state (dormant)

### Wake Protocol
1. User message triggers return signal detection (3-layer: verbal cues → keywords → embedding)
2. Orchestrator identifies most similar dormant agent
3. Dormant agent wakes, loads full history
4. Resumes handling user messages

---

## Session Persistence — Zero Loss

Every session is fully serializable. Nothing is lost between sessions.

```python
# Save at end of session
orchestrator.save("~/.tristate/my_session")

# Restore next session — full continuity
orchestrator = TristateOrchestrator.restore(
    "~/.tristate/my_session", client, embed_fn
)
reply = orchestrator.chat("Where were we?")
```

Saved structure:
```
my_session/
  manifest.json       ← session index, domain, phase, agent registry
  orchestrator.json   ← master summary, active agent ID
  agent_1.json        ← full raw history, embeddings, wake keywords
  agent_2.json        ← full raw history, embeddings, wake keywords
  agent_N.json        ← one file per agent, no limit
```

---

## Installation

```bash
pip install git+https://github.com/fkpkiva/tristate-agent.git
```

Or clone and install locally:
```bash
git clone https://github.com/fkpkiva/tristate-agent.git
cd tristate-agent
pip install -e ".[dev]"
```

---

## Quick Start

```python
from tristate_agent import TristateOrchestrator
from openai import OpenAI
import numpy as np

client = OpenAI(api_key="your-api-key")

def embed_fn(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return np.array(response.data[0].embedding)

orchestrator = TristateOrchestrator(client, embed_fn)

# Start chatting — orchestrator and Agent 1 initialize on first message
reply = orchestrator.chat("I'm writing a Roman drama script set in 44 BC.")
print(reply)

# Topics branch automatically as conversation evolves
reply = orchestrator.chat("What really happened on the Ides of March?")
print(reply)

# Save session — zero loss
orchestrator.save("~/.tristate/roman_drama")
```

---

## Domain Profiles

Spawn sensitivity adapts to the conversation domain:

| Domain | Drift Threshold | Durability Ratio | Turns Before Spawn |
|---|---|---|---|
| `coding` | 0.40 | 0.20 | 2 |
| `scriptwriting` | 0.70 | 0.35 | 5 |
| `business_planning` (research) | 0.75 | 0.40 | 6 |
| `business_planning` (synthesis) | 0.35 | 0.15 | 1 |
| `general` | user-controlled | 0.25 | 4 |

---

## Why This Matters

**For cloud models (GPT-4o, Claude, Gemini):**
- Even a 1M token window fills fast: 2-3 books + conversation = context overflow
- Longer prompts degrade response quality even before the hard limit
- tristate-agent keeps the active window lean by sleeping inactive branches

**For local models (Llama, Mistral, Qwen via Ollama):**
- Context windows are 4k–32k tokens in practice
- Without branching, conversations become useless after a few dozen turns
- tristate-agent makes local LLMs viable for long, complex sessions

---

## Roadmap

```
v0.1.0  NOW
  SWORD pipeline — conversation branching
  Two-gate spawn rule (drift + durability)
  Tristate lifecycle (Active / Dormant / Terminated)
  Zero-loss session persistence
  Formal PROTOCOL.md
  Unit tests

v0.2.0  PLANNED
  SILO pipeline — content ingestion (books, papers, corpora)
  Dual registry (ingest agents + topic agents)
  Stateless lookup agents
  Background summarization on topic switch
  Dedicated summary agent
  Async support

v0.3.0  PLANNED
  Benchmark evaluation vs linear chat-plus-summary baselines
  Token efficiency measurements
  Recall accuracy over long sessions
  Local LLM support (Ollama)
  arXiv paper
```

---

## Project Structure

```
tristate-agent/
├── tristate_agent/
│   ├── __init__.py
│   ├── orchestrator.py       ← TristateOrchestrator — main entry point
│   ├── parent_orchestrator.py ← agent registry + routing
│   ├── agent_node.py         ← AgentNode — tristate lifecycle
│   ├── drift.py              ← phi-decay drift scoring
│   ├── detour.py             ← two-gate spawn + detour management
│   ├── domain_profiles.py    ← per-domain thresholds
│   └── session_store.py      ← zero-loss save/restore
├── tests/
├── examples/
├── PROTOCOL.md               ← formal memory protocol spec
├── CHANGELOG.md
└── pyproject.toml
```

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Author

**fkpkiva** — [github.com/fkpkiva](https://github.com/fkpkiva)

*tristate-agent is an architecture and protocol release. Benchmark evaluation is planned for v0.3.0.*
