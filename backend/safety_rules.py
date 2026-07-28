"""Deterministic, fail-closed storage assignment rules.

AI outputs labels and constraints only.  This module is the sole authority for
the recommended location, and human review is required whenever the rule set
cannot make a safe unambiguous decision.
"""

from __future__ import annotations

from typing import Iterable


STORAGE_CONSTRAINT_OPTIONS = (
    "Ambient temperature",
    "Corrosive",
    "Flammable",
    "Keep away from acids",
    "Keep away from oxidizers",
    "Locked storage",
    "Refrigerated",
    "Segregate from bases",
    "Water reactive",
)


def determine_storage_location(constraints: Iterable[str]) -> dict[str, str]:
    """Return a safe recommendation for a reviewed set of allowed constraints."""

    constraint_set = {str(value).strip() for value in constraints if str(value).strip()}
    supported = set(STORAGE_CONSTRAINT_OPTIONS)
    conflicting = (
        {"Refrigerated", "Flammable"} <= constraint_set
        or {"Corrosive", "Flammable"} <= constraint_set
    )
    if (
        not constraint_set
        or not constraint_set <= supported
        or conflicting
        or "Water reactive" in constraint_set
        or "Locked storage" in constraint_set
    ):
        return {
            "location": "Manual Review Required",
            "rule": (
                "SR-01 — Unknown, conflicting, reactive, or restricted constraints "
                "require safety review."
            ),
        }
    if "Refrigerated" in constraint_set:
        return {
            "location": "Refrigerated Storage",
            "rule": "SR-02 — Refrigerated materials remain in temperature-controlled storage.",
        }
    if "Corrosive" in constraint_set:
        return {
            "location": "Corrosives Cabinet",
            "rule": "SR-03 — Corrosives are segregated from general and flammable stock.",
        }
    if "Flammable" in constraint_set:
        return {
            "location": "Flammable Cabinet B",
            "rule": "SR-04 — Flammable liquids are assigned to an approved cabinet.",
        }
    return {
        "location": "General Shelf A",
        "rule": "SR-05 — Ambient material with no special segregation rule.",
    }
