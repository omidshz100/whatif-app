"""
WhatIf — LLM Translation Layer
================================
The LLM does exactly two jobs:

  (a) Given the user's free-text problem description, map it to
      a set of evidence values for the active investigation.
      Returns: {evidence_id: value} — the same keys the sliders use.

  (b) Given the Bayesian engine's ranked results, produce a single
      readable sentence summarising the top finding.
      Returns: str

The LLM NEVER outputs a probability number.  All numbers come from
bayesian_engine.py.  If no API key is available, both functions
return None and the app continues with sliders only.

Provider support
----------------
  • Claude (Anthropic)  — uses claude-haiku-4-5-20251001 for speed/cost
  • OpenAI GPT          — uses gpt-4o-mini for speed/cost

Keys can come from two sources (session key takes priority):
  1. Environment variables (ANTHROPIC_API_KEY / OPENAI_API_KEY)
  2. The in-app Settings panel (stored in session_state below)
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional

# Session-level override (set via /api/settings, cleared on restart)
session_state: Dict[str, Any] = {
    "provider":     None,   # "claude" | "openai" | None → use env default
    "claude_key":   None,
    "openai_key":   None,
}


def get_provider() -> str:
    """Active provider: session override → env var → "claude" fallback."""
    if session_state["provider"]:
        return session_state["provider"]
    return os.getenv("LLM_PROVIDER", "claude")


def get_api_key(provider: str) -> Optional[str]:
    """Effective API key: session override → env var."""
    if provider == "claude":
        return session_state["claude_key"] or os.getenv("ANTHROPIC_API_KEY")
    if provider == "openai":
        return session_state["openai_key"] or os.getenv("OPENAI_API_KEY")
    return None


def is_available() -> bool:
    return bool(get_api_key(get_provider()))


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _evidence_schema(investigation) -> str:
    """Describe evidence fields in a way an LLM can fill in."""
    lines = []
    for ev in investigation.evidence_nodes:
        if ev.kind == "slider":
            lines.append(
                f'  "{ev.id}": {ev.min}–{ev.max} (number, {ev.unit})'
                f' — {ev.help}'
            )
        elif ev.kind == "toggle":
            lines.append(f'  "{ev.id}": true or false — {ev.help}')
        elif ev.kind == "segment":
            opts = ", ".join(f'"{o["id"]}"' for o in ev.options)
            lines.append(f'  "{ev.id}": one of [{opts}] — {ev.help}')
    return "\n".join(lines)


def _extract_prompt(text: str, investigation) -> str:
    defaults_json = json.dumps(investigation.defaults)
    schema = _evidence_schema(investigation)
    return f"""You are a helper for a diagnostic reasoning tool called WhatIf.
The user described their problem in plain language.  Your job is to extract
evidence values that will feed into a Bayesian network.

Investigation: "{investigation.title}"
Causes being considered: {', '.join(c.label for c in investigation.causes)}

Evidence fields to fill (return ONLY a JSON object with these keys):
{schema}

Default values (use these for any field the user's text doesn't address):
{defaults_json}

User's description:
\"\"\"{text}\"\"\"

Return ONLY a valid JSON object with the evidence values.  Do not add
explanations, markdown fences, or any text outside the JSON object.
Never invent a probability number — your job is only to fill the evidence fields."""


def _summarise_prompt(top_label: str, top_pct: int, second_label: str, second_pct: int,
                      investigation_title: str) -> str:
    return f"""You are a helper for a diagnostic reasoning tool called WhatIf.
The Bayesian engine has just computed these probabilities for the investigation
"{investigation_title}":

  Most likely cause:   {top_label} ({top_pct}%)
  Second most likely:  {second_label} ({second_pct}%)

Write ONE short sentence (max 20 words) that communicates the top finding in
plain English.  Do NOT repeat the percentage numbers — just name the cause and
say it's the most likely explanation.  Be direct and factual."""


# ---------------------------------------------------------------------------
# Claude implementation
# ---------------------------------------------------------------------------

def _call_claude(prompt: str, key: str, max_tokens: int = 256) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------

def _call_openai(prompt: str, key: str, max_tokens: int = 256) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, max_tokens: int = 256) -> Optional[str]:
    """Dispatch to the active provider; return None if unavailable."""
    provider = get_provider()
    key = get_api_key(provider)
    if not key:
        return None
    if provider == "claude":
        return _call_claude(prompt, key, max_tokens=max_tokens)
    if provider == "openai":
        return _call_openai(prompt, key, max_tokens=max_tokens)
    return None


def extract_evidence(text: str, investigation) -> Optional[Dict[str, Any]]:
    """
    Ask the LLM to map free-text to evidence values.
    Returns dict of evidence values, or None if LLM is unavailable.
    The values are clamped/coerced to valid ranges before returning.
    """
    if not text.strip() or not is_available():
        return None
    prompt = _extract_prompt(text, investigation)
    try:
        raw = _call_llm(prompt)
        if not raw:
            return None
        # Strip any accidental markdown fences
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)
    except Exception:
        return None

    # Coerce and clamp values to valid ranges
    result: Dict[str, Any] = {}
    for ev in investigation.evidence_nodes:
        if ev.id not in data:
            result[ev.id] = investigation.defaults[ev.id]
            continue
        val = data[ev.id]
        if ev.kind == "slider" and ev.min is not None and ev.max is not None:
            try:
                val = float(val)
                val = max(ev.min, min(ev.max, val))
                if ev.step == 1:
                    val = int(round(val))
            except (TypeError, ValueError):
                val = investigation.defaults[ev.id]
        elif ev.kind == "toggle":
            if isinstance(val, str):
                val = val.lower() in ("true", "yes", "1")
            else:
                val = bool(val)
        elif ev.kind == "segment":
            valid_ids = {o["id"] for o in ev.options}
            if val not in valid_ids:
                val = investigation.defaults[ev.id]
        result[ev.id] = val
    return result


def summarise_result(top_label: str, top_p: float,
                     second_label: str, second_p: float,
                     investigation_title: str) -> Optional[str]:
    """
    Generate a one-sentence plain-English summary.
    Returns None if LLM is unavailable.
    """
    if not is_available():
        return None
    prompt = _summarise_prompt(
        top_label, round(top_p * 100),
        second_label, round(second_p * 100),
        investigation_title,
    )
    try:
        return _call_llm(prompt)
    except Exception:
        return None


def test_connection() -> Dict[str, Any]:
    """
    Make a cheap test call and report success or the error message.
    Returns {"ok": bool, "message": str, "provider": str}.
    """
    provider = get_provider()
    key = get_api_key(provider)
    if not key:
        return {"ok": False, "message": "No API key configured.", "provider": provider}
    try:
        result = _call_llm("Reply with the single word: OK")
        if result and "OK" in result.upper():
            return {"ok": True,  "message": f"Connected to {provider} successfully.",
                    "provider": provider}
        return {"ok": True, "message": f"Connected to {provider} (response: {result}).",
                "provider": provider}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "provider": provider}


# ---------------------------------------------------------------------------
# Investigation structure generation
# ---------------------------------------------------------------------------

_GENERATE_SYSTEM = """You are a Bayesian network designer for a diagnostic reasoning tool called WhatIf.

Given a plain-language problem description, you produce a small Bayesian network spec in JSON.

RULES:
- 3-5 CAUSES (mutually exclusive explanations).
- 3-5 EVIDENCE VARIABLES (observable clues that help distinguish causes).
- Cause ids: lowercase, underscores, no spaces (e.g. "seo_drop").
- Evidence ids: camelCase (e.g. "organicTraffic").
- Priors: positive integers (relative weights only — will be normalised).
- Associations: integer strengths 1-10 per (cause, state) — higher means more likely.
  Do NOT output probability numbers; only relative integer strengths.
- States for sliders: ordered ascending by max_threshold; last state's max_threshold
  should be >= ev.max so it captures the top of the range.
- For toggles: exactly two states with ids "yes" and "no"; default is true or false.
- For segments: states must match options ids exactly; no max_threshold needed.
- Levers: one per top cause, pointing at the evidence that most controls it.
- title: starts with "Why…?"
- subtitle: very short context (e.g. "E-commerce · last month").

Return ONLY the JSON object — no markdown fences, no explanation."""

_GENERATE_EXAMPLE = """Example output for "My café's morning revenue is down":

{
  "title": "Why is morning café revenue down?",
  "subtitle": "Café · last 3 weeks",
  "causes": [
    {"id": "new_barista",    "label": "New barista",       "hint": "A new hire slows service and disrupts regulars."},
    {"id": "bad_weather",    "label": "Bad weather",       "hint": "Wet mornings suppress walk-in foot traffic."},
    {"id": "price_increase", "label": "Price increase",    "hint": "A price hike pushes price-sensitive regulars away."},
    {"id": "roadwork",       "label": "Nearby roadwork",   "hint": "Construction reduces parking and passing traffic."}
  ],
  "priors": {"new_barista": 1, "bad_weather": 1, "price_increase": 1, "roadwork": 1},
  "evidence_nodes": [
    {
      "id": "weeksSinceHire", "label": "Weeks since new barista started",
      "kind": "slider", "min": 0, "max": 8, "step": 1, "unit": "wks",
      "default": 2, "help": "0 = no new morning hire.",
      "states": [
        {"id": "none",   "label": "No hire",       "max_threshold": 0},
        {"id": "recent", "label": "Recent (1-3w)", "max_threshold": 3},
        {"id": "older",  "label": "Older (4w+)",   "max_threshold": 8}
      ],
      "associations": {
        "new_barista":    {"none": 1, "recent": 8, "older": 4},
        "bad_weather":    {"none": 4, "recent": 4, "older": 4},
        "price_increase": {"none": 4, "recent": 4, "older": 4},
        "roadwork":       {"none": 4, "recent": 4, "older": 4}
      }
    },
    {
      "id": "roadworkNearby", "label": "Roadwork or closure nearby",
      "kind": "toggle", "default": false, "help": "Any construction within a block?",
      "states": [
        {"id": "yes", "label": "Yes"},
        {"id": "no",  "label": "No"}
      ],
      "associations": {
        "new_barista":    {"yes": 2, "no": 8},
        "bad_weather":    {"yes": 2, "no": 8},
        "price_increase": {"yes": 2, "no": 8},
        "roadwork":       {"yes": 8, "no": 2}
      }
    }
  ],
  "levers": [
    {"cause_id": "new_barista",    "evidence_id": "weeksSinceHire",  "to_value": 0, "verb": "Remove or retrain the new barista",   "detail": "restore morning service quality"},
    {"cause_id": "bad_weather",    "evidence_id": "weeksSinceHire",  "to_value": 0, "verb": "Wait for clear mornings",             "detail": "set weather aside"},
    {"cause_id": "price_increase", "evidence_id": "weeksSinceHire",  "to_value": 0, "verb": "Roll back the price increase",        "detail": "return to prior pricing"},
    {"cause_id": "roadwork",       "evidence_id": "roadworkNearby",  "to_value": false, "verb": "Wait for roadwork to clear",      "detail": "once the closure ends"}
  ]
}"""


def _repair_spec(spec: dict) -> dict:
    """Auto-fix common LLM omissions so minor format gaps don't fail the user."""
    cause_ids = [c["id"] for c in spec.get("causes", [])]

    for ev in spec.get("evidence_nodes", []):
        kind = ev.get("kind", "slider")

        # Auto-generate missing states
        if not ev.get("states"):
            if kind == "toggle":
                ev["states"] = [
                    {"id": "yes", "label": "Yes"},
                    {"id": "no",  "label": "No"},
                ]
            elif kind == "segment":
                opts = ev.get("options", [])
                if opts:
                    ev["states"] = [{"id": o["id"], "label": o["label"]} for o in opts]
                else:
                    ev["states"] = [
                        {"id": "low",  "label": "Low"},
                        {"id": "mid",  "label": "Mid"},
                        {"id": "high", "label": "High"},
                    ]
            else:  # slider
                lo = float(ev.get("min", 0))
                hi = float(ev.get("max", 100))
                mid = (lo + hi) / 2
                ev["states"] = [
                    {"id": "low",  "label": "Low",  "max_threshold": mid},
                    {"id": "high", "label": "High", "max_threshold": hi},
                ]

        state_ids = [s["id"] for s in ev["states"]]

        # Auto-generate missing associations (neutral weight = 1)
        if not ev.get("associations"):
            ev["associations"] = {cid: {sid: 1 for sid in state_ids} for cid in cause_ids}
        else:
            for cid in cause_ids:
                if cid not in ev["associations"]:
                    ev["associations"][cid] = {sid: 1 for sid in state_ids}
                else:
                    for sid in state_ids:
                        if sid not in ev["associations"][cid]:
                            ev["associations"][cid][sid] = 1

        # Fix default if missing
        if ev.get("default") is None:
            if kind == "toggle":
                ev["default"] = False
            elif kind == "segment" and state_ids:
                ev["default"] = state_ids[0]
            else:
                ev["default"] = ev.get("min", 0)

    return spec


def _validate_spec(spec: dict) -> Optional[str]:
    """Return an error message if the spec is structurally invalid, else None."""
    if not spec.get("title"):
        return "Missing title"
    if not spec.get("causes"):
        return "Missing causes"
    cause_ids = {c["id"] for c in spec["causes"]}
    for c in spec["causes"]:
        if not c.get("id") or not c.get("label"):
            return f"Cause missing id or label: {c}"
    for ev in spec.get("evidence_nodes", []):
        if not ev.get("id") or not ev.get("label") or not ev.get("kind"):
            return f"Evidence node missing required fields: {ev}"
        if not ev.get("states"):
            return f"Evidence node '{ev['id']}' has no states"
        for cid in ev.get("associations", {}):
            if cid not in cause_ids:
                return f"Association references unknown cause '{cid}' in evidence '{ev['id']}'"
    return None


def generate_structure(problem_text: str) -> Dict[str, Any]:
    """
    Ask the LLM to propose a Bayesian network structure for a problem.
    Returns {"spec": {...}} on success or {"error": "..."} on failure.
    The returned spec is ready to be shown to the user for review/editing.
    """
    if not is_available():
        return {"error": "no_llm",
                "message": "No LLM API key configured. Use the Settings panel to add one, "
                           "or choose Build Manually to create the investigation by hand."}

    prompt = (
        f"{_GENERATE_SYSTEM}\n\n"
        f"{_GENERATE_EXAMPLE}\n\n"
        f"Now generate a spec for this problem:\n\"{problem_text}\"\n\n"
        "Return ONLY the JSON object."
    )
    try:
        raw = _call_llm(prompt, max_tokens=4096)
        if not raw:
            return {"error": "empty", "message": "LLM returned an empty response."}
        # Strip accidental markdown fences
        clean = raw.strip()
        for fence in ("```json", "```"):
            if clean.startswith(fence):
                clean = clean[len(fence):]
        clean = clean.rstrip("`").strip()

        spec = json.loads(clean)
    except json.JSONDecodeError as e:
        return {"error": "parse", "message": f"Could not parse LLM response as JSON: {e}",
                "raw": raw[:500]}
    except Exception as e:
        return {"error": "llm", "message": str(e)}

    spec = _repair_spec(spec)
    err = _validate_spec(spec)
    if err:
        return {"error": "invalid_spec", "message": f"LLM produced an invalid spec: {err}",
                "raw": raw[:500]}

    return {"spec": spec}
