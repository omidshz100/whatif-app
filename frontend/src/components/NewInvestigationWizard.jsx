/**
 * NewInvestigationWizard
 * Multi-step flow: input → (loading) → review/edit → confirm
 *
 * Steps:
 *   "input"    – problem description or manual trigger
 *   "loading"  – LLM is generating the spec
 *   "review"   – user inspects and edits proposed structure
 *   "manual"   – build from scratch (no LLM), same UI as "review" but empty
 *   "creating" – POSTing to /api/investigations
 */

import { useState, useRef, useEffect } from 'react';
import { api } from '../api.js';
import { IconPlus, IconSpinner } from './Icons.jsx';

// ---------------------------------------------------------------------------
// Icon helpers
// ---------------------------------------------------------------------------
function IconTrash({ s = 14 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M3 4h10M6 4V2.5a.5.5 0 01.5-.5h3a.5.5 0 01.5.5V4M5 4l.5 9h5l.5-9"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function KindIcon({ kind, s = 14 }) {
  if (kind === 'slider') return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 8h12M10 5v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
  if (kind === 'toggle') return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="4.5" width="13" height="7" rx="3.5" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="11" cy="8" r="2.2" fill="currentColor" opacity=".5" />
    </svg>
  );
  // segment
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="4.5" width="4" height="7" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <rect x="6" y="4.5" width="4" height="7" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <rect x="10.5" y="4.5" width="4" height="7" rx="2" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Spec helpers
// ---------------------------------------------------------------------------

function makeCauseId(label) {
  return label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || `cause_${Date.now()}`;
}

function makeEvId(label) {
  return label.replace(/[^a-zA-Z0-9 ]+/g, '').split(' ')
    .map((w, i) => i === 0 ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase())
    .join('') || `ev_${Date.now()}`;
}

function newCause(label = '') {
  return { id: makeCauseId(label || `cause_${Date.now()}`), label, hint: '' };
}

function newEvNode(label = '', kind = 'slider') {
  const id = makeEvId(label || `ev_${Date.now()}`);
  const base = { id, label, kind, help: '', default: kind === 'toggle' ? false : 0,
    min: 0, max: 100, step: 10, unit: '%' };
  if (kind === 'slider') {
    return { ...base, states: [
      { id: 'low',  label: 'Low',  max_threshold: 40 },
      { id: 'high', label: 'High', max_threshold: 100 },
    ], associations: {} };
  }
  if (kind === 'toggle') {
    return { ...base, states: [
      { id: 'yes', label: 'Yes' },
      { id: 'no',  label: 'No' },
    ], associations: {} };
  }
  return { ...base, states: [], options: [], associations: {} };
}

function ensureAssociations(spec) {
  const causeIds = spec.causes.map(c => c.id);
  return {
    ...spec,
    evidence_nodes: spec.evidence_nodes.map(ev => {
      const assocs = { ...ev.associations };
      const stateIds = ev.states.map(s => s.id);
      // Fill in missing cause/state combinations with strength=1
      causeIds.forEach(cid => {
        if (!assocs[cid]) {
          assocs[cid] = {};
        }
        stateIds.forEach(sid => {
          if (assocs[cid][sid] == null) assocs[cid][sid] = 1;
        });
      });
      return { ...ev, associations: assocs };
    }),
    priors: Object.fromEntries(causeIds.map(cid => [cid, spec.priors?.[cid] ?? 1])),
    levers: (spec.levers || []).filter(l =>
      causeIds.includes(l.cause_id) &&
      spec.evidence_nodes.some(e => e.id === l.evidence_id)
    ),
  };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InlineEdit({ value, onChange, placeholder, className, small }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || '');

  useEffect(() => { if (!editing) setDraft(value || ''); }, [value, editing]);

  function commit() {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed !== (value || '')) onChange(trimmed);
  }

  if (editing) {
    return (
      <input
        autoFocus
        className={`inline-edit-input${small ? ' small' : ''}${className ? ' ' + className : ''}`}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter') { e.preventDefault(); commit(); }
          if (e.key === 'Escape') { setEditing(false); setDraft(value || ''); }
        }}
      />
    );
  }

  return (
    <span
      className={`inline-edit-text${small ? ' small' : ''}${className ? ' ' + className : ''}`}
      onClick={() => { setDraft(value || ''); setEditing(true); }}
      title="Click to edit"
    >
      {value || <span className="inline-edit-ph">{placeholder}</span>}
    </span>
  );
}

function CauseCard({ cause, onChange, onDelete }) {
  return (
    <div className="wiz-cause-card">
      <InlineEdit
        value={cause.label}
        placeholder="Add cause label…"
        className="wiz-cause-label"
        onChange={label => onChange({ ...cause, label, id: makeCauseId(label) })}
      />
      <button className="wiz-icon-btn danger" onClick={onDelete} title="Remove cause" type="button">
        <IconTrash s={13} />
      </button>
    </div>
  );
}

function EvNodeCard({ ev, onChange, onDelete }) {
  return (
    <div className="wiz-ev-card">
      <div className="wiz-ev-head">
        <span className="wiz-ev-kind-icon"><KindIcon kind={ev.kind} s={13} /></span>
        <InlineEdit
          value={ev.label}
          placeholder="Evidence label…"
          className="wiz-ev-label"
          onChange={label => onChange({ ...ev, label, id: makeEvId(label) })}
        />
        {ev.kind === 'slider' && (
          <InlineEdit
            value={ev.unit || ''}
            placeholder="unit"
            small
            className="wiz-ev-unit"
            onChange={unit => onChange({ ...ev, unit })}
          />
        )}
        <select
          className="wiz-ev-kind-select"
          value={ev.kind}
          onChange={e => onChange(newEvNode(ev.label, e.target.value))}
        >
          <option value="slider">Slider</option>
          <option value="toggle">Toggle</option>
          <option value="segment">Segment</option>
        </select>
        <button className="wiz-icon-btn danger" onClick={onDelete} title="Remove" type="button">
          <IconTrash s={13} />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main wizard
// ---------------------------------------------------------------------------

export function NewInvestigationWizard({ onCreated, onCancel }) {
  const [step, setStep] = useState('input');   // input | loading | review | manual | creating
  const [problem, setProblem] = useState('');
  const [spec, setSpec] = useState(null);
  const [error, setError] = useState(null);
  const [llmAvailable, setLlmAvailable] = useState(true);
  const textareaRef = useRef(null);

  // ---- Step: input -------------------------------------------------------
  async function handleGenerate() {
    if (!problem.trim()) return;
    setStep('loading');
    setError(null);
    try {
      const res = await api.generateInvestigation(problem.trim());
      if (res.error) {
        setError(res.message || 'Generation failed.');
        setLlmAvailable(res.llm_available !== false);
        setStep('input');
      } else {
        setSpec(res.spec);
        setStep('review');
      }
    } catch (e) {
      setError(e.message);
      setStep('input');
    }
  }

  function handleManual() {
    setSpec({
      title: problem.trim() ? `Why did ${problem.trim().toLowerCase().replace(/^why\s+/i,'').replace(/\?$/, '')}?` : '',
      subtitle: '',
      causes: [newCause(''), newCause('')],
      priors: {},
      evidence_nodes: [newEvNode('', 'slider'), newEvNode('', 'toggle')],
      levers: [],
    });
    setStep('manual');
  }

  // ---- Step: review/manual -----------------------------------------------
  function updateCause(index, updated) {
    setSpec(prev => {
      const causes = [...prev.causes];
      causes[index] = updated;
      return { ...prev, causes };
    });
  }
  function removeCause(index) {
    setSpec(prev => ({ ...prev, causes: prev.causes.filter((_, i) => i !== index) }));
  }
  function addCause() {
    setSpec(prev => ({ ...prev, causes: [...prev.causes, newCause('')] }));
  }

  function updateEv(index, updated) {
    setSpec(prev => {
      const evidence_nodes = [...prev.evidence_nodes];
      evidence_nodes[index] = updated;
      return { ...prev, evidence_nodes };
    });
  }
  function removeEv(index) {
    setSpec(prev => ({ ...prev, evidence_nodes: prev.evidence_nodes.filter((_, i) => i !== index) }));
  }
  function addEv() {
    setSpec(prev => ({ ...prev, evidence_nodes: [...prev.evidence_nodes, newEvNode('', 'slider')] }));
  }

  // ---- Confirm -----------------------------------------------------------
  async function handleConfirm() {
    // Validate minimums
    const validCauses = spec.causes.filter(c => c.label.trim());
    const validEvs = spec.evidence_nodes.filter(e => e.label.trim());
    if (validCauses.length < 2) {
      setError('Add at least 2 named causes before confirming.');
      return;
    }
    if (validEvs.length < 1) {
      setError('Add at least 1 evidence variable.');
      return;
    }
    setError(null);
    setStep('creating');

    const finalSpec = ensureAssociations({
      ...spec,
      title: spec.title?.trim() || `New investigation`,
      subtitle: spec.subtitle?.trim() || '',
      causes: validCauses,
      evidence_nodes: validEvs,
    });

    try {
      const inv = await api.createInvestigation(finalSpec);
      onCreated(inv);
    } catch (e) {
      setError(e.message);
      setStep('review');
    }
  }

  // ========================================================================
  // Render
  // ========================================================================

  if (step === 'loading') {
    return (
      <div className="wiz-shell">
        <div className="wiz-loading">
          <IconSpinner s={28} />
          <p className="wiz-loading-text">Proposing network structure…</p>
          <p className="wiz-loading-sub">The AI is suggesting causes and evidence — you'll review everything next.</p>
        </div>
      </div>
    );
  }

  if (step === 'creating') {
    return (
      <div className="wiz-shell">
        <div className="wiz-loading">
          <IconSpinner s={28} />
          <p className="wiz-loading-text">Building investigation…</p>
        </div>
      </div>
    );
  }

  if (step === 'input') {
    return (
      <div className="wiz-shell">
        <div className="wiz-input-card">
          <h1 className="wiz-title">New Investigation</h1>
          <p className="wiz-input-label">What problem do you want to diagnose?</p>
          <textarea
            ref={textareaRef}
            className="wiz-textarea"
            value={problem}
            autoFocus
            onChange={e => setProblem(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleGenerate(); }}
            placeholder={'e.g. "My online store\'s sales dropped last month after we changed our ad spend"\n\nor "Why did our app\'s crash rate spike after the last deployment?"'}
            rows={4}
          />

          {error && <div className="wiz-error">{error}</div>}

          <div className="wiz-input-actions">
            <button
              className="wiz-btn primary"
              onClick={handleGenerate}
              disabled={!problem.trim()}
              title={!llmAvailable ? 'No LLM key — configure one in Settings' : ''}
            >
              {!llmAvailable
                ? '✨ Generate (needs API key)'
                : '✨ Generate with AI'}
            </button>
            <button className="wiz-btn secondary" onClick={handleManual}>
              Build manually →
            </button>
          </div>

          <p className="wiz-input-note">
            {llmAvailable
              ? 'The AI proposes causes and evidence — you review and confirm everything before it\'s built. All probabilities come from the Bayesian engine, never the LLM.'
              : 'No LLM API key is configured. Use "Build manually" to create the investigation by hand, or add a key in Settings.'}
          </p>

          <button className="wiz-cancel-link" onClick={onCancel}>← Cancel</button>
        </div>
      </div>
    );
  }

  // step === 'review' or 'manual'
  const isManual = step === 'manual';
  return (
    <div className="wiz-shell">
      <div className="wiz-review">
        {/* Header */}
        <div className="wiz-review-head">
          <div>
            <h1 className="wiz-title" style={{ marginBottom: 6 }}>
              {isManual ? 'Build investigation' : 'Review proposed structure'}
            </h1>
            <input
              className="wiz-subtitle-input"
              value={spec?.title || ''}
              placeholder="Investigation title (e.g. 'Why did X happen?')"
              onChange={e => setSpec(prev => ({ ...prev, title: e.target.value }))}
            />
          </div>
          <div className="wiz-review-actions">
            <button className="wiz-btn ghost" onClick={() => setStep('input')}>← Back</button>
            <button className="wiz-btn primary" onClick={handleConfirm}>
              Confirm &amp; Build →
            </button>
          </div>
        </div>

        {error && <div className="wiz-error">{error}</div>}

        {/* Two-column grid */}
        <div className="wiz-review-grid">
          {/* Causes column */}
          <div className="wiz-col-card">
            <div className="wiz-col-head">
              <span className="wiz-col-title">Causes</span>
              <span className="wiz-col-hint">Mutually exclusive explanations</span>
            </div>
            <div className="wiz-cause-list">
              {spec.causes.map((c, i) => (
                <CauseCard
                  key={c.id + i}
                  cause={c}
                  onChange={updated => updateCause(i, updated)}
                  onDelete={() => removeCause(i)}
                />
              ))}
            </div>
            <button className="wiz-add-btn" onClick={addCause} type="button">
              <IconPlus s={13} /> Add cause
            </button>
          </div>

          {/* Evidence column */}
          <div className="wiz-col-card">
            <div className="wiz-col-head">
              <span className="wiz-col-title">Evidence variables</span>
              <span className="wiz-col-hint">Observable clues — become sliders and toggles</span>
            </div>
            <div className="wiz-ev-list">
              {spec.evidence_nodes.map((ev, i) => (
                <EvNodeCard
                  key={ev.id + i}
                  ev={ev}
                  onChange={updated => updateEv(i, updated)}
                  onDelete={() => removeEv(i)}
                />
              ))}
            </div>
            <button className="wiz-add-btn" onClick={addEv} type="button">
              <IconPlus s={13} /> Add evidence variable
            </button>
          </div>
        </div>

        {/* Bottom hint */}
        <p className="wiz-review-hint">
          {isManual
            ? 'Add at least 2 causes and 1 evidence variable. Associations between evidence and causes are set automatically; you can fine-tune them later via the sliders.'
            : 'Edit labels, remove items you don\'t need, or add your own. The Bayesian engine takes over once you confirm — no LLM is involved after this point.'}
        </p>
      </div>
    </div>
  );
}
