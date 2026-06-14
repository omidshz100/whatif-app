"""
Terna Synthetic ERA5-like Time-Series Data
============================================
Generates synthetic hourly weather + terrain data for 7 demo pylons
located in the Campania region (southern Italy).

Variable names mirror ERA5 / ECMWF conventions:
  total_precipitation        → rainfall_24h  (mm, cumulative)
  volumetric_soil_water      → soil_moisture  (0-1 index)
  terrain slope (from DEM)   → slope          (degrees)
  lithology class            → soil_type      (clay | sand | rock)

TO SWAP IN REAL DATA
--------------------
Replace `get_forecast(pylon_id)` with a function that:
  1. Calls the CDS (Copernicus Climate Data Store) ERA5 API using
     the pylon's lat/lon and the desired time window.
  2. Fetches slope/soil_type from a terrain/lithology REST service.
  3. Returns a list of dicts with the same keys used here.
Everything downstream (Bayesian engine, FastAPI routes, frontend) is
data-source-agnostic and requires no changes.

The challenge specification explicitly permits synthetic/simplified
datasets for the prototype phase.
"""

from __future__ import annotations
import math
import random
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Pylon registry
# 7 demo pylons across Campania — positions chosen to reflect realistic
# high-risk terrain (Apennine slopes, volcanic flanks, coastal bluffs).
# ---------------------------------------------------------------------------
PYLONS: List[Dict[str, Any]] = [
    {
        "id": "A47",
        "name": "Pylon A47 — Monte Somma",
        "lat": 40.847, "lon": 14.432,
        "slope": 35.0,
        "soil_type": "clay",
        "description": "Steep volcanic flank of Monte Somma (Vesuvius complex). "
                       "Clay-rich pyroclastic soils highly susceptible to shallow landslides.",
        "scenario": "spike_early",   # risk peaks ~hour 16 → "tomorrow 16:00"
    },
    {
        "id": "B23",
        "name": "Pylon B23 — Avellino Hills",
        "lat": 40.915, "lon": 14.789,
        "slope": 26.0,
        "soil_type": "clay",
        "description": "Hilly terrain east of Naples. Clay-dominant Apennine soils, "
                       "known for slow-moving slides after prolonged rain.",
        "scenario": "spike_mid",     # peaks ~hour 28
    },
    {
        "id": "C11",
        "name": "Pylon C11 — Sorrento Peninsula",
        "lat": 40.627, "lon": 14.375,
        "slope": 22.0,
        "soil_type": "sand",
        "description": "Limestone-sand cliffs of the Sorrento peninsula. "
                       "Sandy soils reduce risk vs clay, but steep grade is a factor.",
        "scenario": "spike_late",    # peaks ~hour 36
    },
    {
        "id": "D08",
        "name": "Pylon D08 — Benevento Plain",
        "lat": 41.132, "lon": 14.785,
        "slope": 6.0,
        "soil_type": "rock",
        "description": "Flat Calore river valley. Stable bedrock — this pylon "
                       "serves as the low-risk reference in the demo.",
        "scenario": "safe",
    },
    {
        "id": "E15",
        "name": "Pylon E15 — Caserta Foothills",
        "lat": 41.073, "lon": 14.333,
        "slope": 14.0,
        "soil_type": "sand",
        "description": "Gentle slopes below the Tifatini ridge. Sandy-loam soils, "
                       "low to moderate risk.",
        "scenario": "low",
    },
    {
        "id": "F31",
        "name": "Pylon F31 — Cilento Coast",
        "lat": 40.285, "lon": 15.022,
        "slope": 29.0,
        "soil_type": "clay",
        "description": "Steep clay bluffs of the Cilento national park. "
                       "Persistent medium-to-high risk during wet season.",
        "scenario": "medium",
    },
    {
        "id": "G44",
        "name": "Pylon G44 — Matese Mountains",
        "lat": 41.398, "lon": 14.395,
        "slope": 31.0,
        "soil_type": "sand",
        "description": "High-altitude Matese massif. Rocky-sand mix; "
                       "risk spikes during rapid snowmelt events.",
        "scenario": "spike_mid2",    # peaks ~hour 22
    },
]

PYLON_MAP: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PYLONS}

# ---------------------------------------------------------------------------
# Time-series scenario generators
# Each scenario produces 48 hourly evidence dicts mimicking a realistic
# weather event (e.g. a Mediterranean low-pressure system tracking NE).
# ---------------------------------------------------------------------------

def _cosine_ramp(hour: int, h0: int, h1: int, v0: float, v1: float) -> float:
    """Smooth cosine-eased interpolation between two values."""
    if hour <= h0: return v0
    if hour >= h1: return v1
    t = (hour - h0) / (h1 - h0)
    t_s = (1 - math.cos(t * math.pi)) / 2
    return v0 + (v1 - v0) * t_s


def _build_series(scenario: str, hours: int = 48) -> List[Dict[str, Any]]:
    rng = random.Random(7)   # fixed seed → deterministic, reproducible demo

    def jitter(amp: float) -> float:
        return rng.uniform(-amp, amp)

    result = []
    for h in range(hours):

        if scenario == "spike_early":
            # Rain front arrives fast; peaks hour 14-18; clears by hour 36
            if h <= 16:
                rain = _cosine_ramp(h, 0, 14, 8, 158)
                moist = _cosine_ramp(h, 2, 14, 0.44, 0.93)
            else:
                rain = _cosine_ramp(h, 16, 38, 158, 22)
                moist = _cosine_ramp(h, 18, 48, 0.93, 0.52)
            frain = 10 <= h <= 20

        elif scenario == "spike_mid":
            if h <= 28:
                rain = _cosine_ramp(h, 8, 26, 6, 118)
                moist = _cosine_ramp(h, 10, 26, 0.40, 0.86)
            else:
                rain = _cosine_ramp(h, 28, 48, 118, 28)
                moist = _cosine_ramp(h, 30, 48, 0.86, 0.48)
            frain = 20 <= h <= 32

        elif scenario == "spike_late":
            if h <= 36:
                rain = _cosine_ramp(h, 20, 34, 10, 88)
                moist = _cosine_ramp(h, 22, 34, 0.36, 0.74)
            else:
                rain = _cosine_ramp(h, 36, 48, 88, 18)
                moist = _cosine_ramp(h, 38, 48, 0.74, 0.42)
            frain = 28 <= h <= 40

        elif scenario == "spike_mid2":
            if h <= 22:
                rain = _cosine_ramp(h, 6, 20, 12, 102)
                moist = _cosine_ramp(h, 8, 20, 0.50, 0.82)
            else:
                rain = _cosine_ramp(h, 22, 42, 102, 18)
                moist = _cosine_ramp(h, 24, 48, 0.82, 0.46)
            frain = 14 <= h <= 26

        elif scenario == "medium":
            rain = 38 + 28 * math.sin(h * math.pi / 20) + jitter(6)
            moist = 0.55 + 0.12 * math.sin(h * math.pi / 24) + jitter(0.02)
            frain = h % 12 < 5

        elif scenario == "low":
            rain = 14 + 9 * math.sin(h * math.pi / 18) + jitter(4)
            moist = 0.34 + 0.07 * math.sin(h * math.pi / 24) + jitter(0.02)
            frain = h % 18 < 3

        else:  # safe
            rain = 4 + 2 * math.sin(h * math.pi / 20) + jitter(1)
            moist = 0.18 + 0.04 * math.sin(h * math.pi / 24) + jitter(0.01)
            frain = False

        result.append({
            "hour":          h,
            # ERA5-like variable names in comments for traceability
            "rainfall_24h":  max(0.0, round(rain + jitter(2), 1)),   # total_precipitation (mm)
            "soil_moisture": max(0.0, min(1.0, round(moist + jitter(0.01), 3))),  # volumetric_soil_water
            "forecast_rain": bool(frain),
        })

    return result


# Module-level cache — forecasts are deterministic so computing once is enough
_forecast_cache: Dict[str, List[Dict[str, Any]]] = {}


def get_forecast(pylon_id: str, hours: int = 48) -> List[Dict[str, Any]]:
    """
    Return `hours` hourly evidence dicts for a given pylon.
    Terrain data (slope, soil_type) is merged into every slot so
    compute_risk() always receives the full evidence vector.
    """
    cache_key = f"{pylon_id}:{hours}"
    if cache_key not in _forecast_cache:
        pylon = PYLON_MAP.get(pylon_id)
        if not pylon:
            return []
        slots = _build_series(pylon["scenario"], hours)
        for slot in slots:
            slot["slope"]     = pylon["slope"]
            slot["soil_type"] = pylon["soil_type"]
        _forecast_cache[cache_key] = slots
    return _forecast_cache[cache_key]
