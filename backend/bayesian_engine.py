"""
WhatIf — Bayesian Engine
========================
Implements a Naive-Bayes Bayesian Network for causal diagnosis.

Network structure (one per investigation):

    [Cause]  ←  mutually-exclusive, exhaustive prior
       |
       ├──→ [Evidence_1]
       ├──→ [Evidence_2]
       └──→ [Evidence_n]

Each evidence node has a CPT: P(E=e | Cause=c) for every
discrete state e and every cause c.

Inference by Enumeration
------------------------
Because there are no hidden variables beyond Cause itself,
inference by enumeration is explicit and fast:

    P(Cause=c | E1=e1, …, En=en)
        ∝  P(Cause=c)  ×  ∏_i  P(Ei=ei | Cause=c)

The normalisation constant Z = Σ_c numerator(c) is computed
last so we can return calibrated posteriors.

Contributions (for the "Why?" panel)
--------------------------------------
How much did evidence i shift P(Cause=c)?

    contribution(i, c) = P(c | all evidence)
                       − P(c | all evidence except i)

Positive ↑ means this evidence raised the probability;
negative ↓ means it lowered it.

Counterfactuals (for the What-If panel)
-----------------------------------------
For each lever (an evidence node → forced value), we recompute
P(top_cause | modified evidence) and return the delta.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EvidenceNode:
    """
    One observable variable that informs the cause.

    id          : unique string key (matches the slider/toggle id in the UI)
    label       : human-readable name
    kind        : "slider" | "toggle" | "segment"
    cpt         : {cause_id → {discrete_state → probability}}
                  Must sum to 1.0 for each cause_id.
    discretize  : maps a raw UI value to a discrete_state string
    options     : for segment controls — list of {id, label} dicts
    min/max/step: for slider controls
    unit        : display suffix (e.g. "yrs")
    fmt         : formats the raw value for display (e.g. "15 yrs")
    help        : tooltip text
    say         : generates human-readable text explaining the contribution
                  signature: (raw_value, discrete_state, cause_id, delta) → str | None
    """
    id: str
    label: str
    kind: str                          # "slider" | "toggle" | "segment"
    cpt: Dict[str, Dict[str, float]]   # {cause_id: {state: prob}}
    discretize: Callable[[Any], str]
    help: str = ""
    options: List[Dict] = field(default_factory=list)
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    unit: str = ""
    fmt: Optional[Callable[[Any], str]] = None
    say: Optional[Callable[[Any, str, str, float], Optional[str]]] = None


@dataclass
class Cause:
    id: str
    label: str
    hint: str = ""


@dataclass
class Lever:
    """A counterfactual action: set evidence `evidence_id` to `to_value`."""
    cause_id: str          # which top-cause this lever addresses
    evidence_id: str       # which evidence node to override
    to_value: Any          # the value to force
    verb: str              # short action phrase (e.g. "Replace the fridge")
    detail: str            # parenthetical detail


@dataclass
class Investigation:
    id: str
    title: str
    subtitle: str
    causes: List[Cause]
    priors: Dict[str, float]           # {cause_id: prior probability}
    evidence_nodes: List[EvidenceNode]
    defaults: Dict[str, Any]           # {evidence_id: default raw value}
    levers: List[Lever]
    is_placeholder: bool = False


# ---------------------------------------------------------------------------
# Core inference
# ---------------------------------------------------------------------------

def _joint_numerator(inv: Investigation, values: Dict[str, Any], cause_id: str) -> float:
    """
    P(Cause=cause_id) × ∏_i P(Ei=discretize(values[i]) | Cause=cause_id)

    This is the unnormalised posterior numerator for one cause value.
    """
    p = inv.priors[cause_id]
    for ev in inv.evidence_nodes:
        raw = values[ev.id]
        state = ev.discretize(raw)
        p *= ev.cpt[cause_id].get(state, 1e-9)   # 1e-9 guards against missing states
    return p


def infer(inv: Investigation, values: Dict[str, Any]) -> Dict[str, float]:
    """
    Inference by enumeration over all cause values.
    Returns {cause_id: posterior_probability}.
    """
    numerators = {c.id: _joint_numerator(inv, values, c.id) for c in inv.causes}
    Z = sum(numerators.values())
    if Z == 0:
        # Degenerate case: uniform fallback
        n = len(inv.causes)
        return {c.id: 1.0 / n for c in inv.causes}
    return {cid: num / Z for cid, num in numerators.items()}


def _infer_without(inv: Investigation, values: Dict[str, Any],
                   exclude_ev_id: str) -> Dict[str, float]:
    """Inference excluding one evidence node (for contribution calculation)."""
    numerators = {}
    for c in inv.causes:
        p = inv.priors[c.id]
        for ev in inv.evidence_nodes:
            if ev.id == exclude_ev_id:
                continue
            raw = values[ev.id]
            state = ev.discretize(raw)
            p *= ev.cpt[c.id].get(state, 1e-9)
        numerators[c.id] = p
    Z = sum(numerators.values())
    if Z == 0:
        n = len(inv.causes)
        return {c.id: 1.0 / n for c in inv.causes}
    return {cid: num / Z for cid, num in numerators.items()}


# ---------------------------------------------------------------------------
# Contribution ("Why?") computation
# ---------------------------------------------------------------------------

@dataclass
class Contribution:
    evidence_id: str
    evidence_label: str
    delta: float       # signed change in P(cause) due to this evidence
    text: str          # human-readable explanation


@dataclass
class CauseResult:
    cause_id: str
    label: str
    hint: str
    p: float
    contributions: List[Contribution]


@dataclass
class ComputeResult:
    results: List[CauseResult]          # sorted best→worst
    top: CauseResult
    biggest_driver: Optional["BiggestDriver"]


@dataclass
class BiggestDriver:
    top_label: str
    before: float
    after: float
    delta: float                        # signed pp (negative = drop)
    lever_verb: str
    lever_detail: str


def compute(inv: Investigation, values: Dict[str, Any]) -> ComputeResult:
    """
    Full inference + contribution + counterfactual for an investigation.
    """
    posteriors = infer(inv, values)

    # --- contributions for every cause ---
    results: List[CauseResult] = []
    for cause in inv.causes:
        cid = cause.id
        p_with = posteriors[cid]
        contribs: List[Contribution] = []

        for ev in inv.evidence_nodes:
            # Does this evidence node even distinguish this cause from others?
            # It does if the CPT row for this cause is non-uniform across states.
            p_without = _infer_without(inv, values, ev.id)[cid]
            delta = p_with - p_without
            # Only include non-trivial contributions (|delta| > 0.002)
            if abs(delta) < 0.002:
                continue
            raw = values[ev.id]
            state = ev.discretize(raw)
            text = None
            if ev.say:
                text = ev.say(raw, state, cid, delta)
            if text is None:
                direction = "raises" if delta > 0 else "lowers"
                text = f"{ev.label}: {direction} this cause's probability"
            contribs.append(Contribution(
                evidence_id=ev.id,
                evidence_label=ev.label,
                delta=delta,
                text=text,
            ))

        # Sort by absolute impact, largest first
        contribs.sort(key=lambda c: abs(c.delta), reverse=True)
        results.append(CauseResult(
            cause_id=cid,
            label=cause.label,
            hint=cause.hint,
            p=p_with,
            contributions=contribs,
        ))

    results.sort(key=lambda r: r.p, reverse=True)
    top = results[0]

    # --- biggest driver (counterfactual) ---
    best_driver: Optional[BiggestDriver] = None
    top_levers = [l for l in inv.levers if l.cause_id == top.cause_id]
    for lever in top_levers:
        modified = {**values, lever.evidence_id: lever.to_value}
        p_after = infer(inv, modified)[top.cause_id]
        delta = p_after - top.p
        if best_driver is None or abs(delta) > abs(best_driver.delta):
            best_driver = BiggestDriver(
                top_label=top.label,
                before=top.p,
                after=p_after,
                delta=delta,
                lever_verb=lever.verb,
                lever_detail=lever.detail,
            )

    return ComputeResult(results=results, top=top, biggest_driver=best_driver)
