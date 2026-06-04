"""
WhatIf — Investigation Definitions
====================================
Each investigation is a fully specified Bayesian Network:
  - causes with priors P(C)
  - evidence nodes with CPTs P(E|C)
  - default evidence values
  - counterfactual levers

CPTs are verified so the default evidence values produce the
target probabilities stated in the project brief:
  • Electricity: ~51 % Old fridge
  • Customers:   ~47 % New barista
  • Pastry:      placeholder (no network yet)

Discretization helpers
-----------------------
Continuous slider values are bucketed into discrete states
before looking up CPT entries.  The bucket boundaries are
chosen to match the natural language used in the "Why?" text.
"""

from bayesian_engine import (
    Investigation, Cause, EvidenceNode, Lever
)


# ===========================================================================
# Helpers
# ===========================================================================

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ===========================================================================
# INVESTIGATION 1 — Electricity bill spike
# ===========================================================================
#
# Causes: fridge, ac, lights
# Priors: P(fridge)=0.40, P(ac)=0.30, P(lights)=0.30
#
# Evidence:
#   fridgeAge   slider  0–20 yrs   → {young, mid, old}
#   newAppliance toggle bool       → {yes, no}
#   nightLights slider 0–7 /wk    → {rare, moderate, frequent}
#   season      segment            → {winter, spring, summer, fall}
#
# Default target (fridgeAge=15, newAppliance=False, nightLights=3, season=summer):
#   fridge ≈ 51.8 %   ac ≈ 16 %   lights ≈ 32 %
# ===========================================================================

def _fridge_age_disc(v):
    v = int(v)
    if v <= 5:
        return "young"
    if v <= 12:
        return "mid"
    return "old"


def _night_lights_disc(v):
    v = int(v)
    if v <= 2:
        return "rare"
    if v <= 4:
        return "moderate"
    return "frequent"


def _new_appliance_disc(v):
    return "yes" if v else "no"


def _season_disc(v):
    return str(v)   # already a string: winter/spring/summer/fall


# CPTs for electricity investigation
_ELEC_FRIDGE_AGE_CPT = {
    # A brand-new fridge almost never fails (P=0.01); an old one commonly does.
    # Low P(young|fridge) means a fresh fridge strongly argues *against* this cause.
    "fridge": {"young": 0.01, "mid": 0.54, "old": 0.45},
    "ac":     {"young": 0.33, "mid": 0.34, "old": 0.33},
    "lights": {"young": 0.33, "mid": 0.34, "old": 0.33},
}
_ELEC_NEW_APPLIANCE_CPT = {
    "fridge": {"yes": 0.15, "no": 0.85},
    "ac":     {"yes": 0.80, "no": 0.20},
    "lights": {"yes": 0.15, "no": 0.85},
}
_ELEC_NIGHT_LIGHTS_CPT = {
    "fridge": {"rare": 0.40, "moderate": 0.40, "frequent": 0.20},
    "ac":     {"rare": 0.40, "moderate": 0.40, "frequent": 0.20},
    "lights": {"rare": 0.10, "moderate": 0.45, "frequent": 0.45},
}
_ELEC_SEASON_CPT = {
    # Fridge: uniform (age not season-dependent)
    "fridge": {"winter": 0.25, "spring": 0.25, "summer": 0.25, "fall": 0.25},
    # AC: heavy summer load
    "ac":     {"winter": 0.05, "spring": 0.15, "summer": 0.60, "fall": 0.20},
    # Lights: slight winter lift (longer dark evenings)
    "lights": {"winter": 0.30, "spring": 0.25, "summer": 0.25, "fall": 0.20},
}


def _elec_fridge_age_say(raw, state, cause_id, delta):
    yrs = int(raw)
    if cause_id == "fridge":
        if state == "old":
            return f"Fridge is {yrs} yrs old — well past its efficient life, raises this"
        if state == "mid":
            return f"Fridge is {yrs} yrs old — getting old, mild upward nudge"
        return f"Fridge is only {yrs} yrs old — works against this"
    if cause_id == "ac":
        return None   # age doesn't speak to AC
    if cause_id == "lights":
        return None
    return None


def _elec_new_appliance_say(raw, state, cause_id, delta):
    if cause_id == "ac":
        if state == "yes":
            return "A new major appliance was added — points strongly to this"
        return "No new appliance added — works against this"
    if cause_id == "fridge":
        if state == "yes":
            return "New appliance added, but fridge age is still the main signal here"
        return None
    return None


def _elec_night_lights_say(raw, state, cause_id, delta):
    nights = int(raw)
    if cause_id == "lights":
        if state == "frequent":
            return f"Lights on {nights} nights/wk — raises this significantly"
        if state == "moderate":
            return f"Lights on {nights} nights/wk — mild upward effect"
        return f"Lights rarely left on ({nights}/wk) — works against this"
    return None


def _elec_season_say(raw, state, cause_id, delta):
    season = str(raw).capitalize()
    if cause_id == "ac":
        if state == "summer":
            return "Summer billing cycle — heavy cooling load, raises AC"
        return f"{season} cycle — low cooling demand, works against AC"
    if cause_id == "lights":
        if state == "winter":
            return "Winter — long dark evenings give a mild lift"
        return None
    return None


electricity = Investigation(
    id="electricity",
    title="Why did my electricity bill spike?",
    subtitle="Home · last billing cycle",
    causes=[
        Cause("fridge", "Old fridge",
              "An aging fridge draws far more power as its seals and compressor degrade."),
        Cause("ac",     "New AC unit",
              "A recently added air conditioner is a large, seasonal load."),
        Cause("lights", "Night lights left on",
              "Lights and devices left running overnight add up across a cycle."),
    ],
    priors={"fridge": 0.40, "ac": 0.30, "lights": 0.30},
    evidence_nodes=[
        EvidenceNode(
            id="fridgeAge", label="Fridge age", kind="slider",
            min=0, max=20, step=1, unit="yrs",
            fmt=lambda v: f"{int(v)} yr{'s' if int(v) != 1 else ''}",
            help="How old is your refrigerator?",
            cpt=_ELEC_FRIDGE_AGE_CPT,
            discretize=_fridge_age_disc,
            say=_elec_fridge_age_say,
        ),
        EvidenceNode(
            id="newAppliance", label="New appliance added recently", kind="toggle",
            fmt=lambda v: "Yes" if v else "No",
            help="Added a new major appliance (AC, dryer, heater) in the last few months?",
            cpt=_ELEC_NEW_APPLIANCE_CPT,
            discretize=_new_appliance_disc,
            say=_elec_new_appliance_say,
        ),
        EvidenceNode(
            id="nightLights", label="Lights on overnight", kind="slider",
            min=0, max=7, step=1, unit="/wk",
            fmt=lambda v: f"{int(v)} night{'s' if int(v) != 1 else ''}/wk",
            help="Roughly how many nights a week are lights or devices left running?",
            cpt=_ELEC_NIGHT_LIGHTS_CPT,
            discretize=_night_lights_disc,
            say=_elec_night_lights_say,
        ),
        EvidenceNode(
            id="season", label="Season", kind="segment",
            options=[
                {"id": "winter", "label": "Winter"},
                {"id": "spring", "label": "Spring"},
                {"id": "summer", "label": "Summer"},
                {"id": "fall",   "label": "Fall"},
            ],
            fmt=lambda v: str(v).capitalize(),
            help="Which season does this bill cover? Cooling load peaks in summer.",
            cpt=_ELEC_SEASON_CPT,
            discretize=_season_disc,
            say=_elec_season_say,
        ),
    ],
    defaults={
        "fridgeAge":    15,
        "newAppliance": False,
        "nightLights":  3,
        "season":       "summer",
    },
    levers=[
        Lever("fridge", "fridgeAge",    1,     "Replace the fridge",
              "swap to a new energy-efficient model"),
        Lever("ac",     "newAppliance", False, "Rule out the new appliance",
              "if it turns out it was already there"),
        Lever("lights", "nightLights",  0,     "Stop leaving lights on",
              "switch everything off overnight"),
    ],
)


# ===========================================================================
# INVESTIGATION 2 — Morning customers down
# ===========================================================================
#
# Causes: barista, weather, roadwork, price
# Priors: equal at 0.25 each
#
# Evidence:
#   baristaWeeks  slider  0–8 wks    → {none, recent, older}
#   rainyMornings slider  0–5 /wk   → {dry, moderate, heavy}
#   roadwork      toggle  bool       → {yes, no}
#   priceHike     slider  0–20 %    → {none, small, large}
#
# Default target (baristaWeeks=2, rainyMornings=2, roadwork=False, priceHike=5):
#   barista ≈ 47.2 %   weather ≈ 28.6 %   price ≈ 19.8 %   roadwork ≈ 4.5 %
# ===========================================================================

def _barista_weeks_disc(v):
    v = int(v)
    if v == 0:
        return "none"
    if v <= 3:
        return "recent"
    return "older"


def _rainy_mornings_disc(v):
    v = int(v)
    if v <= 1:
        return "dry"
    if v <= 3:
        return "moderate"
    return "heavy"


def _roadwork_disc(v):
    return "yes" if v else "no"


def _price_hike_disc(v):
    v = int(v)
    if v == 0:
        return "none"
    if v <= 5:
        return "small"
    return "large"


_CUST_BARISTA_WEEKS_CPT = {
    "barista":  {"none": 0.05, "recent": 0.65, "older": 0.30},
    "weather":  {"none": 0.45, "recent": 0.35, "older": 0.20},
    "roadwork": {"none": 0.45, "recent": 0.35, "older": 0.20},
    "price":    {"none": 0.45, "recent": 0.35, "older": 0.20},
}
_CUST_RAINY_MORNINGS_CPT = {
    "barista":  {"dry": 0.40, "moderate": 0.40, "heavy": 0.20},
    "weather":  {"dry": 0.10, "moderate": 0.45, "heavy": 0.45},
    "roadwork": {"dry": 0.40, "moderate": 0.40, "heavy": 0.20},
    "price":    {"dry": 0.40, "moderate": 0.40, "heavy": 0.20},
}
_CUST_ROADWORK_CPT = {
    "barista":  {"yes": 0.15, "no": 0.85},
    "weather":  {"yes": 0.15, "no": 0.85},
    "roadwork": {"yes": 0.85, "no": 0.15},
    "price":    {"yes": 0.15, "no": 0.85},
}
_CUST_PRICE_HIKE_CPT = {
    "barista":  {"none": 0.40, "small": 0.45, "large": 0.15},
    "weather":  {"none": 0.40, "small": 0.45, "large": 0.15},
    "roadwork": {"none": 0.40, "small": 0.45, "large": 0.15},
    "price":    {"none": 0.05, "small": 0.35, "large": 0.60},
}


def _cust_barista_weeks_say(raw, state, cause_id, delta):
    wks = int(raw)
    if cause_id == "barista":
        if state == "none":
            return "No new morning hire — works against this"
        if state == "recent":
            return f"New barista started {wks} wk ago — timing lines up with the dip"
        return f"New barista started {wks} wks ago — timing is a looser fit"
    return None


def _cust_rainy_mornings_say(raw, state, cause_id, delta):
    days = int(raw)
    if cause_id == "weather":
        if state == "heavy":
            return f"{days} wet mornings/wk — strongly raises this"
        if state == "moderate":
            return f"{days} wet mornings/wk — mild upward effect"
        return "Mostly dry mornings — works against bad-weather explanation"
    return None


def _cust_roadwork_say(raw, state, cause_id, delta):
    if cause_id == "roadwork":
        if state == "yes":
            return "Roadwork or closure reported nearby — points strongly here"
        return "No roadwork nearby — works against this"
    return None


def _cust_price_hike_say(raw, state, cause_id, delta):
    pct = int(raw)
    if cause_id == "price":
        if state == "large":
            return f"Prices up {pct}% — a real deterrent for regulars"
        if state == "small":
            return f"Prices up {pct}% — small effect on regulars"
        return "No meaningful price change — works against this"
    return None


customers = Investigation(
    id="customers",
    title="Why are morning customers down?",
    subtitle="Café · weekday 7–10 am, last 3 weeks",
    causes=[
        Cause("barista",  "New barista",
              "A new hire on the morning shift can slow service and push regulars elsewhere."),
        Cause("weather",  "Bad weather",
              "Rain and cold suppress walk-in foot traffic, especially mornings."),
        Cause("roadwork", "Nearby roadwork",
              "Construction or a closure reduces passing traffic and parking."),
        Cause("price",    "Price increase",
              "A recent price bump can push price-sensitive regulars to alternatives."),
    ],
    priors={"barista": 0.25, "weather": 0.25, "roadwork": 0.25, "price": 0.25},
    evidence_nodes=[
        EvidenceNode(
            id="baristaWeeks", label="Weeks since new barista started", kind="slider",
            min=0, max=8, step=1, unit="wks",
            fmt=lambda v: "No new hire" if int(v) == 0 else f"{int(v)} wk{'s' if int(v) != 1 else ''} ago",
            help="0 = no new morning hire. Recent hires correlate most with the dip.",
            cpt=_CUST_BARISTA_WEEKS_CPT,
            discretize=_barista_weeks_disc,
            say=_cust_barista_weeks_say,
        ),
        EvidenceNode(
            id="rainyMornings", label="Rainy mornings", kind="slider",
            min=0, max=5, step=1, unit="/wk",
            fmt=lambda v: f"{int(v)} day{'s' if int(v) != 1 else ''}/wk",
            help="How many mornings a week were wet or cold over the period?",
            cpt=_CUST_RAINY_MORNINGS_CPT,
            discretize=_rainy_mornings_disc,
            say=_cust_rainy_mornings_say,
        ),
        EvidenceNode(
            id="roadwork", label="Roadwork or closure nearby", kind="toggle",
            fmt=lambda v: "Yes" if v else "No",
            help="Any construction, lane closure, or parking loss within a block?",
            cpt=_CUST_ROADWORK_CPT,
            discretize=_roadwork_disc,
            say=_cust_roadwork_say,
        ),
        EvidenceNode(
            id="priceHike", label="Recent price increase", kind="slider",
            min=0, max=20, step=1, unit="%",
            fmt=lambda v: "No change" if int(v) == 0 else f"+{int(v)}%",
            help="How much did morning prices rise recently?",
            cpt=_CUST_PRICE_HIKE_CPT,
            discretize=_price_hike_disc,
            say=_cust_price_hike_say,
        ),
    ],
    defaults={
        "baristaWeeks":  2,
        "rainyMornings": 2,
        "roadwork":      False,
        "priceHike":     5,
    },
    levers=[
        Lever("barista",  "baristaWeeks",  0,     "Coach or reassign the new barista",
              "bring morning service back to speed"),
        Lever("weather",  "rainyMornings", 0,     "Set weather aside",
              "on a clear stretch of mornings"),
        Lever("roadwork", "roadwork",      False, "Rule out roadwork",
              "once the closure clears"),
        Lever("price",    "priceHike",     0,     "Roll back the price increase",
              "return to prior morning pricing"),
    ],
)


# ===========================================================================
# INVESTIGATION 3 — Pastry sales drop (placeholder)
# ===========================================================================

pastry = Investigation(
    id="pastry",
    title="Why did pastry sales drop?",
    subtitle="New investigation",
    causes=[],
    priors={},
    evidence_nodes=[],
    defaults={},
    levers=[],
    is_placeholder=True,
)


# ===========================================================================
# Registry
# ===========================================================================

INVESTIGATIONS = {
    "electricity": electricity,
    "customers":   customers,
    "pastry":      pastry,
}

ORDER = ["electricity", "customers", "pastry"]
