"""
WhatIf — FastAPI Backend
========================
Provides all data and computation for the React frontend.
The Bayesian engine lives in bayesian_engine.py and is
completely independent of this file.
"""

from __future__ import annotations
import os
import sys
from typing import Any, Dict, List, Optional

# Vercel runs functions from the project root, so we need to add the api/
# directory to sys.path so sibling modules (llm_layer, bayesian_engine, etc.) resolve.
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import llm_layer
import investigations_dynamic as dyn_inv
from bayesian_engine import compute
from investigations import INVESTIGATIONS, ORDER
from terna_bayesian import compute_risk as terna_compute_risk, EVIDENCE_META as TERNA_EVIDENCE_META
import terna_synthetic as terna_syn

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="WhatIf API", version="1.0.0")

_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
# Vercel injects VERCEL_URL (no scheme) for every deployment
_vercel_url = os.getenv("VERCEL_URL")
if _vercel_url:
    _origins.append(f"https://{_vercel_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ContributionOut(BaseModel):
    evidence_id: str
    evidence_label: str
    delta: float
    text: str


class CauseResultOut(BaseModel):
    cause_id: str
    label: str
    hint: str
    p: float
    contributions: List[ContributionOut]


class BiggestDriverOut(BaseModel):
    top_label: str
    before: float
    after: float
    delta: float
    lever_verb: str
    lever_detail: str


class ComputeOut(BaseModel):
    results: List[CauseResultOut]
    top: CauseResultOut
    biggest_driver: Optional[BiggestDriverOut]
    llm_summary: Optional[str] = None


class EvidenceNodeOut(BaseModel):
    id: str
    label: str
    kind: str
    help: str
    options: List[Dict[str, str]]
    min: Optional[float]
    max: Optional[float]
    step: Optional[float]
    unit: str
    default: Any


class CauseOut(BaseModel):
    id: str
    label: str
    hint: str


class InvestigationOut(BaseModel):
    id: str
    title: str
    subtitle: str
    is_placeholder: bool
    causes: List[CauseOut]
    evidence_nodes: List[EvidenceNodeOut]
    defaults: Dict[str, Any]


class InvestigationSummaryOut(BaseModel):
    id: str
    title: str
    subtitle: str
    is_placeholder: bool
    top_label: Optional[str]
    top_p: Optional[float]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lookup(inv_id: str):
    """Find investigation in built-in registry or dynamic registry."""
    if inv_id in INVESTIGATIONS:
        return INVESTIGATIONS[inv_id]
    inv = dyn_inv.get(inv_id)
    if inv:
        return inv
    return None


def _inv_to_out(inv_id: str) -> InvestigationOut:
    inv = _lookup(inv_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    evidence_out = []
    for ev in inv.evidence_nodes:
        evidence_out.append(EvidenceNodeOut(
            id=ev.id,
            label=ev.label,
            kind=ev.kind,
            help=ev.help,
            options=ev.options,
            min=ev.min,
            max=ev.max,
            step=ev.step,
            unit=ev.unit,
            default=inv.defaults.get(ev.id),
        ))
    return InvestigationOut(
        id=inv.id,
        title=inv.title,
        subtitle=inv.subtitle,
        is_placeholder=inv.is_placeholder,
        causes=[CauseOut(id=c.id, label=c.label, hint=c.hint) for c in inv.causes],
        evidence_nodes=evidence_out,
        defaults=inv.defaults,
    )


def _result_to_out(result) -> ComputeOut:
    results_out = [
        CauseResultOut(
            cause_id=r.cause_id,
            label=r.label,
            hint=r.hint,
            p=r.p,
            contributions=[
                ContributionOut(
                    evidence_id=c.evidence_id,
                    evidence_label=c.evidence_label,
                    delta=c.delta,
                    text=c.text,
                )
                for c in r.contributions
            ],
        )
        for r in result.results
    ]
    top_out = results_out[0]
    driver_out = None
    if result.biggest_driver:
        bd = result.biggest_driver
        driver_out = BiggestDriverOut(
            top_label=bd.top_label,
            before=bd.before,
            after=bd.after,
            delta=bd.delta,
            lever_verb=bd.lever_verb,
            lever_detail=bd.lever_detail,
        )
    return ComputeOut(results=results_out, top=top_out, biggest_driver=driver_out)


# ---------------------------------------------------------------------------
# Routes — investigations
# ---------------------------------------------------------------------------

# Cache default-evidence results for built-in investigations so warm requests
# don't recompute on every call (results are deterministic given fixed inputs).
_default_results: dict = {
    inv_id: compute(INVESTIGATIONS[inv_id], INVESTIGATIONS[inv_id].defaults)
    for inv_id in ORDER
    if not INVESTIGATIONS[inv_id].is_placeholder
}


@app.get("/api/investigations", response_model=List[InvestigationSummaryOut])
def list_investigations():
    """List all investigations (built-in + dynamic) with their top result."""
    summaries = []
    # Built-in, in order
    for inv_id in ORDER:
        inv = INVESTIGATIONS[inv_id]
        top_label = None
        top_p = None
        if not inv.is_placeholder:
            result = _default_results[inv_id]
            top_label = result.top.label
            top_p = result.top.p
        summaries.append(InvestigationSummaryOut(
            id=inv.id, title=inv.title, subtitle=inv.subtitle,
            is_placeholder=inv.is_placeholder,
            top_label=top_label, top_p=top_p,
        ))
    # Dynamic (user-created), appended at end
    for inv_id in dyn_inv.all_ids():
        inv = dyn_inv.get(inv_id)
        result = compute(inv, inv.defaults)
        summaries.append(InvestigationSummaryOut(
            id=inv.id, title=inv.title, subtitle=inv.subtitle,
            is_placeholder=False,
            top_label=result.top.label, top_p=result.top.p,
        ))
    return summaries


@app.get("/api/investigations/{inv_id}", response_model=InvestigationOut)
def get_investigation(inv_id: str):
    if _lookup(inv_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return _inv_to_out(inv_id)


# ---------------------------------------------------------------------------
# Routes — create new investigation
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    problem_text: str


class GenerateOut(BaseModel):
    spec: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    llm_available: bool = True


@app.post("/api/investigations/generate", response_model=GenerateOut)
def generate_investigation(req: GenerateRequest):
    """Ask the LLM to propose a Bayesian network structure for a problem."""
    if not req.problem_text.strip():
        raise HTTPException(status_code=400, detail="problem_text is required")
    result = llm_layer.generate_structure(req.problem_text)
    if "error" in result:
        return GenerateOut(
            error=result["error"],
            message=result.get("message", "LLM generation failed."),
            llm_available=result["error"] != "no_llm",
        )
    return GenerateOut(spec=result["spec"], llm_available=True)


class CreateRequest(BaseModel):
    spec: Dict[str, Any]


@app.post("/api/investigations", response_model=InvestigationOut)
def create_investigation(req: CreateRequest):
    """
    Confirm a spec (LLM-generated or hand-built) and create the investigation.
    Returns the full InvestigationOut so the frontend can immediately display it.
    """
    spec = req.spec
    if not spec.get("title") or not spec.get("causes"):
        raise HTTPException(status_code=400, detail="Spec must have a title and at least one cause.")
    if len(spec.get("causes", [])) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 causes.")
    try:
        inv = dyn_inv.create(spec)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not build investigation: {e}")
    return _inv_to_out(inv.id)


# ---------------------------------------------------------------------------
# Routes — compute
# ---------------------------------------------------------------------------

class ComputeRequest(BaseModel):
    evidence: Dict[str, Any]
    with_llm_summary: bool = False


@app.post("/api/investigations/{inv_id}/compute", response_model=ComputeOut)
def compute_investigation(inv_id: str, req: ComputeRequest):
    inv = _lookup(inv_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if inv.is_placeholder:
        raise HTTPException(status_code=400, detail="Investigation not yet configured")

    # Fill missing evidence fields with defaults
    evidence = {**inv.defaults, **req.evidence}

    result = compute(inv, evidence)
    out = _result_to_out(result)

    if req.with_llm_summary and len(result.results) >= 2:
        out.llm_summary = llm_layer.summarise_result(
            top_label=result.results[0].label,
            top_p=result.results[0].p,
            second_label=result.results[1].label,
            second_p=result.results[1].p,
            investigation_title=inv.title,
        )

    return out


# ---------------------------------------------------------------------------
# Routes — LLM evidence extraction
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    text: str


class ExtractOut(BaseModel):
    evidence: Dict[str, Any]
    llm_available: bool
    message: Optional[str] = None


@app.post("/api/investigations/{inv_id}/extract-evidence", response_model=ExtractOut)
def extract_evidence(inv_id: str, req: ExtractRequest):
    inv = _lookup(inv_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if inv.is_placeholder:
        raise HTTPException(status_code=400, detail="Investigation not yet configured")

    if not llm_layer.is_available():
        return ExtractOut(
            evidence=inv.defaults,
            llm_available=False,
            message="No LLM API key configured — using default evidence values. "
                    "Add a key in Settings to enable natural language input.",
        )

    extracted = llm_layer.extract_evidence(req.text, inv)
    if extracted is None:
        return ExtractOut(
            evidence=inv.defaults,
            llm_available=True,
            message="Could not parse LLM response. Using default evidence values.",
        )
    return ExtractOut(evidence=extracted, llm_available=True)


# ---------------------------------------------------------------------------
# Routes — settings
# ---------------------------------------------------------------------------

class SettingsRequest(BaseModel):
    provider: Optional[str] = None   # "claude" | "openai"
    api_key: Optional[str] = None


class SettingsOut(BaseModel):
    provider: str
    has_key: bool
    key_source: str                   # "session" | "env" | "none"


class TestConnectionOut(BaseModel):
    ok: bool
    message: str
    provider: str


@app.get("/api/settings", response_model=SettingsOut)
def get_settings():
    provider = llm_layer.get_provider()
    session_key = llm_layer.session_state.get(
        "claude_key" if provider == "claude" else "openai_key"
    )
    env_key = os.getenv("ANTHROPIC_API_KEY" if provider == "claude" else "OPENAI_API_KEY")
    has_key = bool(session_key or env_key)
    if session_key:
        source = "session"
    elif env_key:
        source = "env"
    else:
        source = "none"
    return SettingsOut(provider=provider, has_key=has_key, key_source=source)


@app.post("/api/settings", response_model=SettingsOut)
def update_settings(req: SettingsRequest):
    if req.provider in ("claude", "openai"):
        llm_layer.session_state["provider"] = req.provider
    if req.api_key:
        provider = req.provider or llm_layer.get_provider()
        if provider == "claude":
            llm_layer.session_state["claude_key"] = req.api_key
        elif provider == "openai":
            llm_layer.session_state["openai_key"] = req.api_key
    return get_settings()


@app.post("/api/settings/test", response_model=TestConnectionOut)
def test_connection():
    result = llm_layer.test_connection()
    return TestConnectionOut(**result)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Terna — Landslide Risk for Transmission Pylons
# ---------------------------------------------------------------------------

# Terna resilience action table
# Maps Bayesian risk level + terrain context to one of five operational categories.
def _terna_action(risk: float, slope: float = 15.0, soil_type: str = "clay") -> dict:
    """Return structured Terna-aligned action for a given risk level and terrain."""
    if risk >= 75:
        return {
            "action_category":  "Response",
            "action_condition": "Active landslide on asset — critical Bayesian posterior (≥75%)",
            "action_impact":    "Imminent line outage; cascading fault risk across grid segment",
            "action":           "Bypass + emergency plan",
        }
    if risk >= 55:
        return {
            "action_category":  "Mitigation",
            "action_condition": "Landslide triggered near asset — debris flow within 100–200 m",
            "action_impact":    "Line span at risk; load redistribution and alternate routing required",
            "action":           "Network redundancy / alternative configuration",
        }
    if risk >= 30:
        if slope >= 30 and soil_type == "clay":
            return {
                "action_category":  "Prevention",
                "action_condition": "Repeated high-risk conditions — steep clay terrain with heavy rainfall",
                "action_impact":    "Long-term foundation degradation; pylon stability at risk over multiple events",
                "action":           "Relocation / line burial",
            }
        return {
            "action_category":  "Prevention",
            "action_condition": "Probable landslide — cumulative rainfall exceeds threshold on susceptible terrain",
            "action_impact":    "Foundation degradation and potential mass movement threatening asset",
            "action":           "Foundation reinforcement / structural verification",
        }
    return {
        "action_category":  "Monitoring",
        "action_condition": "Alert phase — risk within acceptable bounds, no immediate trigger",
        "action_impact":    "No current network impact; maintaining operational awareness",
        "action":           "Monitoring + early warning",
    }


def _all_risks(pylon_id: str):
    """Compute risk for every hour in the 48h forecast (cached via module)."""
    slots = terna_syn.get_forecast(pylon_id, 48)
    return [terna_compute_risk(s)["risk"] for s in slots]


@app.get("/api/terna/pylons")
def terna_list_pylons(hour: int = 0):
    """All pylons with their risk at the given forecast hour."""
    result = []
    for pylon in terna_syn.PYLONS:
        risks = _all_risks(pylon["id"])
        current = risks[min(hour, len(risks) - 1)]
        peak_h  = int(max(range(len(risks)), key=lambda i: risks[i]))
        result.append({
            "id":          pylon["id"],
            "name":        pylon["name"],
            "lat":         pylon["lat"],
            "lon":         pylon["lon"],
            "description": pylon["description"],
            "slope":       pylon["slope"],
            "soil_type":   pylon["soil_type"],
            "risk":        current,
            "peak_risk":   risks[peak_h],
            "peak_hour":   peak_h,
        })
    return result


@app.get("/api/terna/forecast")
def terna_full_forecast(hours: int = 48):
    """48h risk forecast for all pylons (used to draw sparklines / timelines)."""
    result = {}
    for pylon in terna_syn.PYLONS:
        slots = terna_syn.get_forecast(pylon["id"], hours)
        result[pylon["id"]] = [
            {"hour": s["hour"], "risk": terna_compute_risk(s)["risk"]}
            for s in slots
        ]
    return result


@app.get("/api/terna/pylons/{pylon_id}/detail")
def terna_pylon_detail(pylon_id: str, hour: int = 0):
    """Full Bayesian breakdown for a pylon at a specific forecast hour."""
    pylon = terna_syn.PYLON_MAP.get(pylon_id)
    if not pylon:
        raise HTTPException(status_code=404, detail="Pylon not found")
    slots   = terna_syn.get_forecast(pylon_id, 48)
    slot    = slots[min(hour, len(slots) - 1)]
    risk_out = terna_compute_risk(slot)
    risks   = [terna_compute_risk(s)["risk"] for s in slots]
    peak_h  = int(max(range(len(risks)), key=lambda i: risks[i]))
    return {
        **pylon,
        "hour":          hour,
        "evidence":      slot,
        "risk":          risk_out["risk"],
        "states":        risk_out["states"],
        "contributions": risk_out["contributions"],
        "evidence_meta": TERNA_EVIDENCE_META,
        "peak_hour":     peak_h,
        "peak_risk":     risks[peak_h],
        "all_risks":     risks,
    }


@app.get("/api/terna/alerts")
def terna_alerts(threshold: float = 45.0, hour: int = 0):
    """Pylons whose peak risk (next 48h) exceeds `threshold`, sorted by urgency."""
    alerts = []
    for pylon in terna_syn.PYLONS:
        risks    = _all_risks(pylon["id"])
        peak_h   = int(max(range(len(risks)), key=lambda i: risks[i]))
        peak_r   = risks[peak_h]
        current  = risks[min(hour, len(risks) - 1)]
        if peak_r < threshold:
            continue
        if peak_r >= 75:
            severity = "critical"
        elif peak_r >= 55:
            severity = "high"
        else:
            severity = "medium"
        action_plan = _terna_action(peak_r, pylon.get("slope", 15), pylon.get("soil_type", "clay"))
        alerts.append({
            "pylon_id":     pylon["id"],
            "name":         pylon["name"],
            "lat":          pylon["lat"],
            "lon":          pylon["lon"],
            "current_risk": current,
            "peak_risk":    peak_r,
            "peak_hour":    peak_h,
            "severity":     severity,
            **action_plan,
        })
    alerts.sort(key=lambda a: a["peak_risk"], reverse=True)
    return alerts
