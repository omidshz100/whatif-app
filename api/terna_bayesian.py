"""
Terna Landslide Bayesian Network
==================================
Computes P(landslide | evidence) for a power transmission pylon using
exact Bayesian inference by enumeration (Naive Bayes structure).

Network structure:
  landslide_event → [rainfall_24h, soil_moisture, slope, soil_type, forecast_rain]

All CPTs are hand-tuned to encode domain knowledge:
  high rainfall + high moisture + steep slope + clay soil → high risk

In production: the evidence values come from ERA5 re-analysis + terrain APIs.
The math here is independent of the data source.
"""

from __future__ import annotations
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Prior P(landslide)
# Base rate of a landslide affecting a pylon on any given day in a
# high-risk Italian Apennine corridor.
# ---------------------------------------------------------------------------
PRIOR = {"yes": 0.05, "no": 0.95}

# ---------------------------------------------------------------------------
# Discretization helpers
# ---------------------------------------------------------------------------

def _disc_rainfall(v: float) -> str:
    """Bucket cumulative 24-72h rainfall (mm) into named states."""
    if v < 20:   return "dry"
    if v < 60:   return "moderate"
    if v < 120:  return "heavy"
    return "extreme"

def _disc_moisture(v: float) -> str:
    """Bucket soil moisture index (0-1) into named states."""
    if v < 0.40: return "low"
    if v < 0.70: return "medium"
    return "high"

def _disc_slope(v: float) -> str:
    """Bucket terrain slope (degrees) into named states."""
    if v < 10:  return "flat"
    if v < 20:  return "gentle"
    if v < 30:  return "steep"
    return "very_steep"

# ---------------------------------------------------------------------------
# Conditional Probability Tables  P(evidence_state | landslide)
# Columns sum to 1.0 for each landslide value.
# ---------------------------------------------------------------------------
CPTS: Dict[str, Dict[str, Dict[str, float]]] = {
    "rainfall_24h": {
        "yes": {"dry": 0.04, "moderate": 0.11, "heavy": 0.35, "extreme": 0.50},
        "no":  {"dry": 0.52, "moderate": 0.28, "heavy": 0.14, "extreme": 0.06},
    },
    "soil_moisture": {
        "yes": {"low": 0.04, "medium": 0.16, "high": 0.80},
        "no":  {"low": 0.52, "medium": 0.34, "high": 0.14},
    },
    "slope": {
        "yes": {"flat": 0.02, "gentle": 0.08, "steep": 0.28, "very_steep": 0.62},
        "no":  {"flat": 0.36, "gentle": 0.34, "steep": 0.20, "very_steep": 0.10},
    },
    "soil_type": {
        "yes": {"clay": 0.62, "sand": 0.28, "rock": 0.10},
        "no":  {"clay": 0.28, "sand": 0.42, "rock": 0.30},
    },
    "forecast_rain": {
        "yes": {"yes": 0.82, "no": 0.18},
        "no":  {"yes": 0.32, "no": 0.68},
    },
}

# Evidence variable metadata (used by the frontend for sliders / labels)
EVIDENCE_META = [
    {
        "id": "rainfall_24h",
        "label": "Cumulative rainfall (24-72h)",
        "kind": "slider", "min": 0, "max": 200, "step": 5, "unit": "mm",
        "help": "Total precipitation accumulated over the last 24-72 hours (ERA5: total_precipitation).",
    },
    {
        "id": "soil_moisture",
        "label": "Soil moisture / saturation",
        "kind": "slider", "min": 0, "max": 1, "step": 0.05, "unit": "",
        "help": "Volumetric soil water content 0-1 (ERA5: volumetric_soil_water_layer_1).",
    },
    {
        "id": "slope",
        "label": "Terrain slope",
        "kind": "slider", "min": 0, "max": 45, "step": 1, "unit": "°",
        "help": "Average slope of the hillside around the pylon (from DEM).",
    },
    {
        "id": "soil_type",
        "label": "Soil type",
        "kind": "segment",
        "options": [
            {"id": "clay", "label": "Clay"},
            {"id": "sand", "label": "Sand"},
            {"id": "rock", "label": "Rock"},
        ],
        "help": "Dominant soil / bedrock type at the pylon location.",
    },
    {
        "id": "forecast_rain",
        "label": "Heavy rain forecast (next 6h)",
        "kind": "toggle",
        "help": "Is intense rainfall (>10mm/h) expected in the next 6 hours?",
    },
]


def _discretize(evidence: Dict[str, Any]) -> Dict[str, str]:
    """Map raw evidence values to their discrete state names."""
    return {
        "rainfall_24h":  _disc_rainfall(float(evidence.get("rainfall_24h", 20))),
        "soil_moisture": _disc_moisture(float(evidence.get("soil_moisture", 0.45))),
        "slope":         _disc_slope(float(evidence.get("slope", 15))),
        "soil_type":     str(evidence.get("soil_type", "clay")),
        "forecast_rain": "yes" if evidence.get("forecast_rain", False) else "no",
    }


def compute_risk(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bayesian inference by enumeration.

    P(landslide=yes | e1…e5) ∝ P(yes) × ∏_i P(e_i | yes)

    Returns:
      risk         – posterior probability of landslide (0-100, rounded 1 dp)
      states       – discretized state for each variable
      contributions – per-variable delta (pp) showing how much each variable
                     pushes the risk above/below the prior
    """
    states = _discretize(evidence)

    # Joint unnormalized probabilities
    joint: Dict[str, float] = {}
    for lv in ("yes", "no"):
        p = PRIOR[lv]
        for var, state in states.items():
            p *= CPTS[var][lv][state]
        joint[lv] = p

    total = joint["yes"] + joint["no"]
    risk = (joint["yes"] / total) if total > 0 else 0.0

    # Per-variable contribution: risk_with_all - risk_without_this_variable
    # "without" = remove this variable's factor from both numerator & denominator
    contributions: List[Dict] = []
    for var in CPTS:
        joint_wo: Dict[str, float] = {}
        for lv in ("yes", "no"):
            p = PRIOR[lv]
            for v2, s2 in states.items():
                if v2 != var:
                    p *= CPTS[v2][lv][s2]
            joint_wo[lv] = p
        total_wo = joint_wo["yes"] + joint_wo["no"]
        risk_wo = (joint_wo["yes"] / total_wo) if total_wo > 0 else 0.0
        delta = risk - risk_wo

        meta = next(m for m in EVIDENCE_META if m["id"] == var)
        contributions.append({
            "id":    var,
            "label": meta["label"],
            "state": states[var],
            "delta": round(delta * 100, 1),
        })

    contributions.sort(key=lambda c: abs(c["delta"]), reverse=True)

    return {
        "risk":          round(risk * 100, 1),
        "states":        states,
        "contributions": contributions,
    }
