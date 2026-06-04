# WhatIf — Risk Diagnosis Tool

Describe a problem in plain language. WhatIf figures out the likely causes,
shows them as a ranked probability list, and lets you adjust evidence
(sliders / toggles) to see the probabilities update live.

```
whatif-app/
├── backend/            Python FastAPI — Bayesian engine + LLM layer
└── frontend/           React (Vite) — pixel-perfect UI
```

---

## Architecture

### Layer 1 — Bayesian Engine (`backend/bayesian_engine.py`)
A Naive-Bayes Bayesian Network with explicit Conditional Probability Tables
(CPTs) and **Inference by Enumeration**. All probability numbers come from
here. Never from the LLM. Never from softmax over a score vector.

```
P(Cause=c | E1=e1, …, En=en)
  ∝  P(Cause=c)  ×  ∏_i  P(Ei=ei | Cause=c)
```

The "Why?" panel shows each evidence node's contribution:
```
contribution(e, c) = P(c | all evidence) − P(c | all evidence except e)
```

The "What-If" panel shows the biggest counterfactual lever on the top cause.

### Layer 2 — LLM (`backend/llm_layer.py`)
Translates between human language and the Bayesian engine.
Two jobs only:
- **(a)** Free-text → evidence values (populates the sliders)
- **(b)** Top result → one readable sentence (optional)

Supports **Claude (Anthropic)** and **GPT (OpenAI)**.
If no key is configured, the app still works fully via the sliders.

---

## Quick Start

### 1. Clone / enter the project
```bash
cd whatif-app
```

### 2. Backend

```bash
cd backend

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: add API keys (see below)
cp ../.env.example .env
# edit .env

# Start the server
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## API Keys (two ways)

### Option 1 — `.env` file (persists across restarts)

Copy `.env.example` to `backend/.env` and fill in your keys:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LLM_PROVIDER=claude     # or: openai
```

### Option 2 — In-app Settings panel (session only)

Click the **Settings** button (bottom of the sidebar). You can:

- Pick a provider (Claude or GPT)
- Paste an API key (stored only in the current server session, never on disk)
- Click **Test connection** to verify the key
- A status indicator shows whether the key is valid

Keys entered via the Settings panel take priority over `.env` values for that session.

> **Never commit `.env` to git.** It is listed in `.gitignore`.

---

## Investigations

| Investigation | Top cause at defaults | Key evidence |
|---|---|---|
| Why did my electricity bill spike? | Old fridge ~52% | Fridge age, new appliance, night lights, season |
| Why are morning customers down? | New barista ~47% | Weeks since hire, rainy mornings, roadwork, price hike |
| Why did pastry sales drop? | Placeholder | — |

---

## How the Bayesian Network works (electricity example)

**Network structure**
```
           [Cause]
          /   |   \
  [FridgeAge][NewAppliance][NightLights][Season]
```

**Prior**: `P(fridge)=0.40, P(ac)=0.30, P(lights)=0.30`

**CPT sample** — `P(FridgeAge_level | Cause)`:
| Level | fridge | ac | lights |
|---|---|---|---|
| young (0–5 yrs) | 0.15 | 0.33 | 0.33 |
| mid (6–12 yrs)  | 0.40 | 0.34 | 0.34 |
| old (13+ yrs)   | 0.45 | 0.33 | 0.33 |

**Inference by enumeration** (from `bayesian_engine.py`):
```python
numerators = {
  "fridge": P(fridge) * P(old|fridge) * P(no|fridge) * P(mod|fridge) * P(summer|fridge),
  "ac":     P(ac)     * P(old|ac)     * P(no|ac)     * P(mod|ac)     * P(summer|ac),
  "lights": P(lights) * P(old|lights) * P(no|lights) * P(mod|lights) * P(summer|lights),
}
Z = sum(numerators.values())
posteriors = {c: n / Z for c, n in numerators.items()}
# → fridge ≈ 51.8%, lights ≈ 32%, ac ≈ 16%
```

All CPTs are defined explicitly in `backend/investigations.py`.
The math is transparent and verifiable.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | Python 3.11 + FastAPI + Uvicorn |
| Bayesian engine | Pure Python (no external BN library) |
| LLM (optional) | Anthropic SDK / OpenAI SDK |
| Storage | In-memory (no database) |

---

## Project structure

```
whatif-app/
├── backend/
│   ├── bayesian_engine.py   # BN inference by enumeration (standalone, no LLM)
│   ├── investigations.py    # CPTs + investigation definitions
│   ├── llm_layer.py         # Claude / GPT translation layer
│   ├── main.py              # FastAPI routes
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── api.js
│   │   ├── components/
│   │   │   ├── BarChart.jsx
│   │   │   ├── EvidenceControls.jsx
│   │   │   ├── ExplanationPanel.jsx
│   │   │   ├── Icons.jsx
│   │   │   ├── NLPInput.jsx
│   │   │   ├── Pct.jsx
│   │   │   ├── SettingsPanel.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   └── WhyPanel.jsx
│   │   └── hooks/
│   │       └── useWhatIf.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env.example
├── .gitignore
└── README.md
```
