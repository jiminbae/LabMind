"""Small reviewed chemistry reference used to enrich already-validated CAS data.

This is deliberately not a broad chemical database.  A missing CAS returns no
structure or safety classification rather than a best guess, so chemistry
meaning searches fail closed for unreviewed material.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


CHEMISTRY_CATALOG: dict[str, dict[str, Any]] = {
    "64-17-5": {
        "smiles": "CCO",
        "labels": ["Flammable liquid", "Protic solvent", "Organic compound"],
        "constraints": [
            "Flammable",
            "Keep away from oxidizers",
            "Ambient temperature",
        ],
        "confidence": 0.97,
        "rationale": "A volatile protic solvent with a low flash point.",
    },
    "67-56-1": {
        "smiles": "CO",
        "labels": ["Flammable liquid", "Protic solvent", "Organic compound"],
        "constraints": ["Flammable", "Keep away from oxidizers"],
        "confidence": 0.97,
        "rationale": "A volatile flammable alcohol requiring compatible storage.",
    },
    "75-05-8": {
        "smiles": "CC#N",
        "labels": ["Flammable liquid", "Organic compound"],
        "constraints": ["Flammable", "Keep away from oxidizers"],
        "confidence": 0.95,
        "rationale": "A volatile organic nitrile solvent with flammability controls.",
    },
    "7647-01-0": {
        "smiles": "Cl",
        "labels": ["Brønsted acid", "Inorganic compound"],
        "constraints": ["Corrosive", "Segregate from bases"],
        "confidence": 0.98,
        "rationale": "A strong inorganic acid requiring corrosive segregation.",
    },
    "7647-14-5": {
        "smiles": "[Na+].[Cl-]",
        "labels": ["Inorganic compound"],
        "constraints": ["Ambient temperature"],
        "confidence": 0.98,
        "rationale": "A stable inorganic salt under normal laboratory conditions.",
    },
    "64-19-7": {
        "smiles": "CC(=O)O",
        "labels": ["Brønsted acid", "Organic compound"],
        "constraints": ["Corrosive", "Flammable", "Segregate from bases"],
        "confidence": 0.97,
        "rationale": "An organic acid with corrosive and combustible hazards.",
    },
    "67-68-5": {
        "smiles": "CS(C)=O",
        "labels": ["Organic compound"],
        "constraints": ["Ambient temperature"],
        "confidence": 0.96,
        "rationale": "A stable polar organic solvent under normal storage conditions.",
    },
    "77-86-1": {
        "smiles": "NC(CO)(CO)CO",
        "labels": ["Organic compound"],
        "constraints": ["Ambient temperature"],
        "confidence": 0.96,
        "rationale": "A stable organic buffering base under normal storage conditions.",
    },
    "7550-45-0": {
        "smiles": "Cl[Ti](Cl)(Cl)Cl",
        "labels": ["Lewis acid", "Inorganic compound", "Moisture reactive"],
        "constraints": ["Corrosive", "Water reactive", "Segregate from bases"],
        "confidence": 0.94,
        "rationale": "A strong Lewis acid that reacts vigorously with moisture.",
    },
    "109-72-8": {
        "smiles": "[Li]CCCC",
        "labels": ["Organometallic", "Pyrophoric", "Reducing agent"],
        "constraints": [
            "Flammable",
            "Water reactive",
            "Keep away from acids",
            "Locked storage",
        ],
        "confidence": 0.96,
        "rationale": "An organolithium reagent requiring inert, tightly controlled storage.",
    },
    "76189-55-4": {
        "smiles": (
            "P(c1ccccc1)(c1ccccc1)c1ccc2ccccc2c1-"
            "c1c(P(c2ccccc2)c2ccccc2)ccc2ccccc12"
        ),
        "labels": [
            "Chiral ligand",
            "Phosphine ligand",
            "Organophosphorus compound",
        ],
        "constraints": ["Ambient temperature", "Keep away from oxidizers"],
        "confidence": 0.93,
        "rationale": "A chiral bisphosphine ligand used in asymmetric catalysis.",
    },
    "210169-54-3": {
        "smiles": (
            "C1OC2=C(O1)C(=C(C=C2)P(C3=CC=CC=C3)C4=CC=CC=C4)"
            "C5=C(C=CC6=C5OCO6)P(C7=CC=CC=C7)C8=CC=CC=C8"
        ),
        "labels": [
            "Chiral ligand",
            "Phosphine ligand",
            "Organophosphorus compound",
        ],
        "constraints": ["Ambient temperature", "Keep away from oxidizers"],
        "confidence": 0.91,
        "rationale": "A chiral bisphosphine ligand used in asymmetric transformations.",
    },
}


def catalog_profile(cas_number: str | None) -> dict[str, Any] | None:
    """Return an isolated reference profile, if this CAS has one."""

    if not cas_number:
        return None
    profile = CHEMISTRY_CATALOG.get(cas_number.strip())
    return deepcopy(profile) if profile else None


def smiles_for_cas(cas_number: str | None) -> str | None:
    """Return only reviewed structure data; never infer SMILES from a name."""

    profile = catalog_profile(cas_number)
    return str(profile["smiles"]) if profile and profile.get("smiles") else None
