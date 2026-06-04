"""
WhatIf — Dynamic Investigation Builder
=======================================
Converts a user-confirmed spec (produced by the LLM or entered manually)
into a live Investigation object that the Bayesian engine can compute.

Spec format (same JSON that the frontend sends):
{
  "title":    "Why did X happen?",
  "subtitle": "Context · timeframe",
  "causes": [{"id": "c1", "label": "...", "hint": "..."}],
  "priors":   {"c1": 1, "c2": 1},         # relative weights, normalised here
  "evidence_nodes": [
    {
      "id": "ev1", "label": "...", "kind": "slider",
      "min": 0, "max": 100, "step": 10, "unit": "%",
      "default": 30, "help": "...",
      "states": [
        {"id": "low",  "label": "Low (< 30%)",  "max_threshold": 30},
        {"id": "high", "label": "High (≥ 30%)", "max_threshold": 100}
      ],
      "associations": {
        "c1": {"low": 3, "high": 7},   # relative strengths, normalised to CPT
        "c2": {"low": 6, "high": 4}
      }
    }
  ],
  "levers": [
    {"cause_id": "c1", "evidence_id": "ev1", "to_value": 80,
     "verb": "...", "detail": "..."}
  ]
}

CPT generation
--------------
association strengths are relative weights — the backend normalises them so
each cause's distribution sums to 1.  This means the LLM only needs to
provide *relative* intuitions, not exact probabilities.

Missing associations default to uniform across states.
"""

from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional

from bayesian_engine import Investigation, Cause, EvidenceNode, Lever

# ---------------------------------------------------------------------------
# In-memory registry for user-created investigations
# ---------------------------------------------------------------------------
DYNAMIC_REGISTRY: Dict[str, Investigation] = {}


# ---------------------------------------------------------------------------
# CPT / discretize / fmt builders
# ---------------------------------------------------------------------------

def _make_cpt(ev_spec: dict, cause_ids: List[str]) -> Dict[str, Dict[str, float]]:
    """Convert association strengths → normalised CPT."""
    state_ids = [s["id"] for s in ev_spec["states"]]
    assocs = ev_spec.get("associations", {})
    cpt: Dict[str, Dict[str, float]] = {}
    for cid in cause_ids:
        raw = assocs.get(cid, {})
        scores = {sid: float(raw.get(sid, 1)) for sid in state_ids}
        total = sum(scores.values()) or 1.0
        cpt[cid] = {sid: scores[sid] / total for sid in state_ids}
    return cpt


def _make_slider_discretize(states: List[dict]):
    """Ordered threshold lookup: value ≤ max_threshold → that state's id."""
    ordered = sorted(states, key=lambda s: s.get("max_threshold", float("inf")))
    ids = [s["id"] for s in ordered]
    thresholds = [s.get("max_threshold", float("inf")) for s in ordered]

    def disc(v):
        fv = float(v)
        for i, thresh in enumerate(thresholds):
            if fv <= thresh:
                return ids[i]
        return ids[-1]
    return disc


def _make_toggle_discretize():
    return lambda v: "yes" if v else "no"


def _make_segment_discretize():
    return lambda v: str(v)


def _make_fmt(ev_spec: dict):
    kind = ev_spec["kind"]
    unit = ev_spec.get("unit", "")
    states = ev_spec.get("states", [])
    state_label_map = {s["id"]: s["label"] for s in states}

    if kind == "toggle":
        return lambda v: "Yes" if v else "No"
    if kind == "segment":
        opts = {o["id"]: o["label"] for o in ev_spec.get("options", states)}
        return lambda v: opts.get(str(v), str(v))
    # slider
    def fmt(v):
        vi = int(round(float(v)))
        if not unit:
            return str(vi)
        return f"{vi} {unit}"
    return fmt


def _make_say(ev_label: str, states: List[dict]):
    state_label_map = {s["id"]: s["label"] for s in states}

    def say(raw, state: str, cause_id: str, delta: float) -> Optional[str]:
        if abs(delta) < 0.025:
            return None
        state_label = state_label_map.get(state, state)
        direction = "raises" if delta > 0 else "lowers"
        return f"{ev_label}: {state_label} — {direction} this cause"
    return say


# ---------------------------------------------------------------------------
# Build Investigation from spec dict
# ---------------------------------------------------------------------------

def build_from_spec(spec: dict) -> Investigation:
    """
    Create a fully functional Investigation object from a user-confirmed spec.
    Returns the Investigation (the caller must store it in DYNAMIC_REGISTRY).
    """
    inv_id = spec.get("id") or f"dyn_{uuid.uuid4().hex[:8]}"
    cause_ids = [c["id"] for c in spec["causes"]]

    # Normalise priors
    raw_priors = {c["id"]: float(spec.get("priors", {}).get(c["id"], 1)) for c in spec["causes"]}
    total_prior = sum(raw_priors.values()) or 1.0
    priors = {cid: raw_priors[cid] / total_prior for cid in cause_ids}

    # Build Cause objects
    causes = [
        Cause(id=c["id"], label=c["label"], hint=c.get("hint", ""))
        for c in spec["causes"]
    ]

    # Build EvidenceNode objects
    ev_nodes: List[EvidenceNode] = []
    for ev_spec in spec.get("evidence_nodes", []):
        kind = ev_spec["kind"]
        states = ev_spec.get("states", [])
        cpt = _make_cpt(ev_spec, cause_ids)

        if kind == "slider":
            disc = _make_slider_discretize(states)
        elif kind == "toggle":
            disc = _make_toggle_discretize()
        else:
            disc = _make_segment_discretize()

        ev_nodes.append(EvidenceNode(
            id=ev_spec["id"],
            label=ev_spec["label"],
            kind=kind,
            cpt=cpt,
            discretize=disc,
            help=ev_spec.get("help", ""),
            options=ev_spec.get("options", []),
            min=ev_spec.get("min"),
            max=ev_spec.get("max"),
            step=ev_spec.get("step"),
            unit=ev_spec.get("unit", ""),
            fmt=_make_fmt(ev_spec),
            say=_make_say(ev_spec["label"], states),
        ))

    # Build Levers
    levers = [
        Lever(
            cause_id=l["cause_id"],
            evidence_id=l["evidence_id"],
            to_value=l["to_value"],
            verb=l["verb"],
            detail=l.get("detail", ""),
        )
        for l in spec.get("levers", [])
    ]

    # Build defaults dict
    defaults = {ev_spec["id"]: ev_spec.get("default") for ev_spec in spec.get("evidence_nodes", [])}

    return Investigation(
        id=inv_id,
        title=spec["title"],
        subtitle=spec.get("subtitle", ""),
        causes=causes,
        priors=priors,
        evidence_nodes=ev_nodes,
        defaults=defaults,
        levers=levers,
        is_placeholder=False,
    )


def create(spec: dict) -> Investigation:
    """Build and register a new dynamic investigation. Returns it."""
    inv = build_from_spec(spec)
    DYNAMIC_REGISTRY[inv.id] = inv
    return inv


def get(inv_id: str) -> Optional[Investigation]:
    return DYNAMIC_REGISTRY.get(inv_id)


def all_ids() -> List[str]:
    return list(DYNAMIC_REGISTRY.keys())
