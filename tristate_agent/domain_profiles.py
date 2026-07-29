"""
domain_profiles.py – Per-domain spawn thresholds and configuration.

v0.2 additions:
  - Phase-aware sub-profiles (research / writing / review).
  - Helper get_phase_profile() for PhaseAwareAgent threshold resolution.
  - Dedicated profiles for research, writing, and review domains.
"""
from typing import Any, Dict, Optional

DEFAULT_DOMAIN = "general"

# ---------------------------------------------------------------------------
# Domain Profiles
# Each top-level key is a domain name.  Optional "phases" sub-dict holds
# phase-specific overrides used by PhaseAwareAgent / specialized agents.
# ---------------------------------------------------------------------------
DOMAIN_PROFILES: Dict[str, Any] = {
  "coding": {
    "drift_threshold": 0.40,
    "durability_ratio": 0.20,
    "max_detour_turns": 2,
    "detour_reabsorb": True,
    "decay_rate": 1.618,  # phi
    "wake_similarity_threshold": 0.85,
    "description": "Software development, debugging, code review",
  },
  "scriptwriting": {
    "drift_threshold": 0.70,
    "durability_ratio": 0.35,
    "max_detour_turns": 5,
    "detour_reabsorb": True,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.80,
    "description": "Film scripts, drama, creative writing",
  },
  "business_planning": {
    "drift_threshold": 0.55,
    "durability_ratio": 0.30,
    "max_detour_turns": 4,
    "detour_reabsorb": True,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.82,
    "description": "Business strategy, market analysis, planning",
    "phases": {
      "research": {
        "drift_threshold": 0.75,
        "durability_ratio": 0.40,
        "max_detour_turns": 6,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
      },
      "writing": {
        "drift_threshold": 0.35,
        "durability_ratio": 0.15,
        "max_detour_turns": 1,
        "detour_reabsorb": False,
        "decay_rate": 1.618,
      },
      "review": {
        "drift_threshold": 0.40,
        "durability_ratio": 0.20,
        "max_detour_turns": 2,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
      },
    },
  },
  "general": {
    "drift_threshold": 0.50,
    "durability_ratio": 0.25,
    "max_detour_turns": 4,
    "detour_reabsorb": True,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.85,
    "description": "General-purpose conversation",
  },
  "technical": {
    "drift_threshold": 0.45,
    "durability_ratio": 0.22,
    "max_detour_turns": 3,
    "detour_reabsorb": True,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.85,
    "description": "Technical documentation and analysis",
  },
  # -----------------------------------------------------------------------
  # v0.2 specialised agent domains
  # -----------------------------------------------------------------------
  "research": {
    "drift_threshold": 0.45,
    "durability_ratio": 0.30,
    "max_detour_turns": 6,
    "detour_reabsorb": True,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.78,
    "description": "Information gathering, literature review, fact finding",
    "phases": {
      "research": {
        "drift_threshold": 0.45,
        "durability_ratio": 0.30,
        "max_detour_turns": 6,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
      },
    },
  },
  "writing": {
    "drift_threshold": 0.35,
    "durability_ratio": 0.25,
    "max_detour_turns": 3,
    "detour_reabsorb": False,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.88,
    "description": "Content drafting, editing, revision",
    "phases": {
      "writing": {
        "drift_threshold": 0.35,
        "durability_ratio": 0.25,
        "max_detour_turns": 3,
        "detour_reabsorb": False,
        "decay_rate": 1.618,
      },
    },
  },
  "review": {
    "drift_threshold": 0.40,
    "durability_ratio": 0.28,
    "max_detour_turns": 4,
    "detour_reabsorb": True,
    "decay_rate": 1.618,
    "wake_similarity_threshold": 0.86,
    "description": "Quality review, feedback, approval workflows",
    "phases": {
      "review": {
        "drift_threshold": 0.40,
        "durability_ratio": 0.28,
        "max_detour_turns": 4,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
      },
    },
  },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_domain_profile(domain: str) -> Dict[str, Any]:
  """Return top-level profile for *domain*, falling back to DEFAULT_DOMAIN."""
  return DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES[DEFAULT_DOMAIN])


def get_phase_profile(
  domain: str,
  phase: Optional[str] = None,
) -> Dict[str, Any]:
  """Return phase-specific overrides merged on top of domain defaults.

  If *phase* is None or no phase sub-profile exists, returns the domain
  top-level profile unchanged.

  Merge order: domain defaults <- phase overrides.
  """
  profile = dict(get_domain_profile(domain))
  if phase and "phases" in profile:
    phase_overrides = profile["phases"].get(phase, {})
    profile.update(phase_overrides)
  # Remove nested phases key from result – callers don't need it.
  profile.pop("phases", None)
  return profile


def list_domains() -> list:
  """Return sorted list of registered domain names."""
  return sorted(DOMAIN_PROFILES.keys())
