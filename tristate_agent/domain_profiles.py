"""
domain_profiles.py — Per-domain spawn thresholds and configuration.
Orchestrator loads these on session start after domain classification.
"""

DOMAIN_PROFILES = {
    "coding": {
        "drift_threshold": 0.40,
        "durability_ratio": 0.20,
        "detour_max_turns": 2,
        "detour_reabsorb": True,
        "decay_rate": 1.618,  # phi
        "description": "Software development, debugging, code review",
    },
    "scriptwriting": {
        "drift_threshold": 0.70,
        "durability_ratio": 0.35,
        "detour_max_turns": 5,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
        "description": "Film scripts, drama, creative writing",
    },
    "business_planning": {
        "research": {
            "drift_threshold": 0.75,
            "durability_ratio": 0.40,
            "detour_max_turns": 6,
            "detour_reabsorb": True,
            "decay_rate": 1.618,
        },
        "synthesis": {
            "drift_threshold": 0.35,
            "durability_ratio": 0.15,
            "detour_max_turns": 1,
            "detour_reabsorb": False,
            "decay_rate": 1.618,
        },
        "description": "Business strategy, planning, investor prep",
    },
    "general": {
        "drift_threshold": None,  # user-controlled, no auto-spawn
        "durability_ratio": 0.25,
        "detour_max_turns": 4,
        "detour_reabsorb": True,
        "decay_rate": 1.618,
        "description": "General conversation, no specific domain",
    },
}

DEFAULT_DOMAIN = "general"


def get_profile(domain: str, phase: str = "research") -> dict:
    """
    Return the active profile dict for a given domain and phase.
    For business_planning, phase selects research or synthesis sub-profile.
    """
    if domain not in DOMAIN_PROFILES:
        domain = DEFAULT_DOMAIN

    profile = DOMAIN_PROFILES[domain]

    if domain == "business_planning":
        sub = profile.get(phase, profile["research"])
        return {
            **sub,
            "domain": domain,
            "phase": phase,
            "description": profile["description"],
        }

    return {
        **profile,
        "domain": domain,
        "phase": "default",
    }
