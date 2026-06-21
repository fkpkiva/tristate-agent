"""
domain_profiles.py — Per-domain spawn thresholds and configuration.
Orchestrator loads these on session start after domain classification.
"""

from typing import Dict, Any

DEFAULT_DOMAIN = "general"

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
        "research": {
            "drift_threshold": 0.75,
            "durability_ratio": 0.40,
            "max_detour_turns": 6,
            "detour_reabsorb": True,
            "decay_rate": 1.618,
        },
        "synthesis": {
            "drift_threshold": 0.35,
            "durability_ratio": 0.15,
            "max_detour_turns": 1,
            "detour_reabsorb": False,
            "decay_rate": 1.618,
        },
        "drift_threshold": 0.55,
        "durability_ratio": 0.30,
        "max_detour_turns": 4,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
        "wake_similarity_threshold": 0.82,
        "description": "Business strategy, market analysis, planning",
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
        "wake_similarity_threshold": 0.87,
        "description": "Technical documentation, engineering, science",
    },
}


def get_domain_profile(domain: str) -> Dict[str, Any]:
    """
    Return the profile dict for a given domain name.
    Falls back to DEFAULT_DOMAIN (\"general\") if not found.
    """
    profile = DOMAIN_PROFILES.get(domain)
    if profile is None:
        profile = DOMAIN_PROFILES[DEFAULT_DOMAIN]
    return profile


def list_domains():
    """Return all registered domain names."""
    return list(DOMAIN_PROFILES.keys())
