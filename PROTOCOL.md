# tristate-agent — Formal Memory Protocol

**Version**: 0.1.0  
**Status**: Active  
**Scope**: SWORD pipeline (v0.1) — conversation branching

---

## 1. Core Principle

The orchestrator NEVER holds raw conversation content. It holds only summaries, agent registry metadata, and routing logic. Raw content always lives inside agents.

---

## 2. Tristate Lifecycle

Every agent exists in exactly one of three states at any time:

| State | Symbol | Description |
|---|---|---|
| Active | `1` | In live context window, handling user messages |
| Dormant | `Z` | Full history preserved on disk, zero token cost |
| Terminated | `0` | Session ended, saved to disk, restorable |

State transitions:
```
0 (not yet spawned) → 1 (spawn)
1 (active) → Z (sleep)
Z (dormant) → 1 (wake)
1 or Z → 0 (session end — saved to disk)
```

No agent is ever permanently deleted during a live session.

---

## 3. Orchestrator Responsibilities

The orchestrator owns all policy decisions:

- **Spawn decision** — when to create a new agent
- **Wake decision** — which dormant agent to restore
- **Sleep decision** — when to put an active agent into Z-state
- **Topic drift scoring policy** — phi-decay drift calculation
- **Agent registry routing** — mapping messages to the correct agent
- **Reply path** — all agent replies go to orchestrator first, then to user

The orchestrator NEVER:
- Holds raw conversation turns
- Summarizes content directly (agents do this)
- Answers user messages without delegating to an agent

---

## 4. Agent Responsibilities

Each agent owns its own state:

- **Final summary generation** — produces summary before sleeping
- **Raw history retention** — holds complete turn-by-turn history
- **Dormant/active flag** — tracks its own tristate
- **Save/load of own context** — serializes and deserializes itself
- **Clean exit after handoff** — erases since-marker content after copying to new agent
- **Shifted token tracking** — tracks `shifted_tokens` and `total_tokens` for durability ratio

---

## 5. Two-Gate Spawn Rule

A new agent spawns ONLY when both gates confirm a durable topic shift.

### Gate 1 — Drift Gate (instantaneous)
```
drift_score >= domain_drift_threshold
```
- Computed via phi-decay weighted cosine distance from anchor embedding
- Fires immediately when semantic distance exceeds threshold
- Does NOT spawn — starts the watch period

### Gate 2 — Durability Gate (accumulates)
```
EITHER: detour_turn_count >= domain_max_turns
OR:     agent.shifted_tokens / agent.total_tokens >= domain_durability_ratio
```
- Whichever condition fires first triggers spawn
- Turn count is a hard ceiling; token ratio catches prolonged drift earlier

### Domain Thresholds

| Domain | Drift Threshold | Durability Ratio | Max Turns |
|---|---|---|---|
| `coding` | 0.40 | 0.20 | 2 |
| `scriptwriting` | 0.70 | 0.35 | 5 |
| `business_planning` research | 0.75 | 0.40 | 6 |
| `business_planning` synthesis | 0.35 | 0.15 | 1 |
| `general` | user-controlled | 0.25 | 4 |

---

## 6. Sleep Protocol (ordered steps)

1. Topic shift confirmed as durable (both gates passed)
2. **Marker placed** at the turn where drift began
3. **New agent spawns** (immediately active)
4. **Previous agent** summarizes content since marker → sends to orchestrator  
   *(orchestrator labels this summary as belonging to the new agent’s topic)*
5. **Previous agent** copies all turns since marker to new agent’s history
6. **Previous agent erases** all turns since marker from its own context  
   *(stays clean — only holds content relevant to its own topic)*
7. **Previous agent** produces final full summary of its entire history → sends to orchestrator
8. **Previous agent** enters Z-state (dormant)

### What the new agent receives at birth
- All turns since the drift marker (full fidelity, not summarized)
- Topic label assigned by orchestrator
- Wake keywords derived from content
- Drift marker position

---

## 7. Wake Protocol (ordered steps)

1. User message arrives
2. **3-layer return detection** runs in parallel:
   - Layer 1: Verbal cues ("going back to", "about X", "earlier")
   - Layer 2: Keyword matching against all dormant agent wake_keywords
   - Layer 3: Embedding similarity vs all dormant agent anchor embeddings
3. Orchestrator identifies most similar dormant agent
4. If similarity exceeds wake threshold: **dormant agent wakes**
5. Agent loads its full saved history
6. Agent resumes handling user messages
7. Previously active agent enters Z-state (sleep protocol runs)

---

## 8. Detour Reabsorption (no spawn case)

If a detour is detected but the user returns to the main topic before Gate 2 fires:

1. Return signal detected (3-layer detection)
2. Detour turns are **reabsorbed** as a compact research note in the active agent
3. No agent is spawned
4. Drift marker is cleared
5. Detour turn count resets to zero

This is always preferred over spawning. The system minimizes spawns.

---

## 9. Reply Path

```
User → Orchestrator → Active Agent → Orchestrator → User
```

- User ALWAYS communicates with orchestrator
- Orchestrator routes to the correct active agent
- Agent returns answer to orchestrator
- Orchestrator delivers to user
- Orchestrator may add master-session context before delivery
- Agents NEVER reply directly to user

---

## 10. Session Persistence — Zero Loss Contract

### Save (on session end or explicit call)

Files written:
```
session_dir/
  manifest.json      ← domain, phase, message_count, agent registry index,
                        agents_spawned_total, conversation_history
  orchestrator.json  ← master_summary, active_agent_id, session history
  agent_1.json       ← full raw history, embedding, wake_keywords,
                        topic_label, summary, sleeping state, turn_count,
                        total_tokens, shifted_tokens
  agent_N.json       ← same, one file per agent
```

Nothing is merged, compressed, or lost. Each agent’s complete raw history is preserved exactly.

### Restore (on session resume)

Restore order:
1. Read `manifest.json` → restore domain, phase, message_count, conversation_history
2. Read `orchestrator.json` → restore master_summary, active_agent_id
3. For each agent in manifest → read `agent_N.json` → re-spawn AgentNode exactly
4. Re-instantiate ParentOrchestrator with all agents loaded
5. Re-instantiate DetourManager with correct domain profile

Contract: A restored session must be indistinguishable from the original. No content loss, no state loss, no re-computation required.

---

## 11. Agent Termination Rule

- No agent is terminated during a live session
- Agents may only enter Z-state (dormant), never permanent deletion during session
- On session end: all agents (active and dormant) are saved to disk in full
- On restore: all agents are re-spawned from saved files
- Termination only occurs if user explicitly garbage-collects old sessions

---

## 12. Roadmap — v0.2 Protocol Additions (SILO)

The following are planned for v0.2 and are NOT part of this v0.1 protocol:

- SILO pipeline: Split → Index → Lookup → Orchestrate
- Ingest agent lifecycle (stateless lookup mode)
- Dual registry: ingest agents vs topic agents
- Stateless lookup: agent answers, cleans context, sleeps immediately
- Background summarization on topic switch
- Dedicated summary agent *(v0.2)*
- Mid-session upload handling
- Token budget policy by model context size

---

*This protocol is the authoritative specification for tristate-agent v0.1.0. All implementation must conform to these rules.*
