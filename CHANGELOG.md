# Changelog

All notable changes to tristate-agent are documented here.

---

## [0.1.0] — 2026-06-22

### Initial Protocol Release

This is the first public release of tristate-agent. It is an architecture and protocol release. Benchmark evaluation is planned for v0.3.0.

### Added

**Core Architecture**
- Tristate agent lifecycle: Active (`1`) / Dormant (`Z`) / Terminated (`0`)
- Orchestrator as pure coordinator — never holds raw conversation content
- Agent registry with topic labels, summaries, and wake keywords
- Reply path: User → Orchestrator → Agent → Orchestrator → User

**SWORD Pipeline — Conversation Branching**
- **S**core: Phi-decay weighted drift scoring
- **W**atch: Two-gate durability check
- **O**rchestrate: Parent registry coordination and agent routing
- **R**ecall: 3-layer return detection (verbal cues → keywords → embeddings)
- **D**etour: Short tangent reabsorption + durable shift spawning

**Two-Gate Spawn Rule**
- Gate 1 (Drift): `drift_score >= domain_drift_threshold`
- Gate 2 (Durability): `turn_count >= max_turns` OR `shifted_tokens / total_tokens >= durability_ratio`
- Domain-specific thresholds for coding, scriptwriting, business planning, general

**Sleep Protocol**
- Marker placed at drift start
- Since-marker content summarized and sent to orchestrator
- Since-marker content copied to new agent
- Since-marker content erased from previous agent (clean separation)
- Final full summary sent to orchestrator before sleeping

**Wake Protocol**
- 3-layer return detection: verbal cues, keyword matching, embedding similarity
- Full history restored from saved state
- Zero-loss context restoration

**Session Persistence — Zero Loss**
- `orchestrator.save(path)` — saves all agents + orchestrator state to directory
- `TristateOrchestrator.restore(path, client, embed_fn)` — full session restore
- Per-agent JSON files: full raw history, embeddings, wake keywords, all metadata
- `manifest.json`: session index, domain, phase, agent registry, agents_spawned_total
- `orchestrator.json`: master summary, active agent ID
- Contract: restored session indistinguishable from original

**Domain Profiles**
- Per-domain drift thresholds and durability ratios
- Phase-aware business planning (research vs synthesis modes)

**Formal Protocol**
- `PROTOCOL.md` — 12-section authoritative specification
- Covers: tristate lifecycle, orchestrator responsibilities, agent responsibilities,
  two-gate spawn rule, sleep protocol, wake protocol, detour reabsorption,
  reply path, session persistence contract, agent termination rule

**Tests**
- `test_agent_node.py` — tristate lifecycle, shifted ratio, clean-since-marker
- `test_detour.py` — two-gate spawn, detour reabsorption
- `test_drift.py` — phi-decay scoring
- `test_session_store.py` — save/restore zero-loss contract

---

## Roadmap

### [0.2.0] — Planned

**SILO Pipeline — Content Ingestion**
- **S**plit: Structure-aware content splitting (chapters, sections, themes)
- **I**ndex: Section agents digest and embed assigned content
- **L**ookup: Stateless retrieval — agents answer, clean context, sleep
- **O**rchestrate: Unified orchestrator manages ingest + conversation agents

**Additional v0.2 Features**
- Dual registry: ingest agents vs topic agents
- Inventory agent (Agent 1) as last-resort lookup
- Two-path ingest: direct (content < 50% model context) vs structural (content > 50%)
- Background summarization on topic switch
- Dedicated summary agent *(v0.2)*
- Mid-session upload handling
- Token budget policy by model context size
- Async support (`achat()`)

### [0.3.0] — Planned

- Benchmark evaluation vs linear chat-plus-summary baselines
- Token efficiency measurements across session lengths
- Recall accuracy curves (50, 100, 200 turns)
- Correct branch wake rate evaluation
- Save/restore loss rate evaluation
- Local LLM support (Ollama / LlamaCpp)
- arXiv paper submission
