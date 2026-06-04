"""
WhatIf — FastAPI Backend
========================
Provides all data and computation for the React frontend.
The Bayesian engine lives in bayesian_engine.py and is
completely independent of this file.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import llm_layer
import investigations_dynamic as dyn_inv
from bayesian_engine import compute
from investigations import INVESTIGATIONS, ORDER

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="WhatIf API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
            result = compute(inv, inv.defaults)
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
