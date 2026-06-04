import { useState } from 'react';
import { IconHelp } from './Icons.jsx';

function HelpTip({ text }) {
  if (!text) return null;
  return (
    <span className="help" tabIndex={0}>
      <IconHelp />
      <span className="help-bubble">{text}</span>
    </span>
  );
}

function EditableLabel({ label, help, onRename }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(label);

  function commit() {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed && trimmed !== label) onRename(trimmed);
    else setDraft(label);
  }

  if (editing) {
    return (
      <span className="ev-label">
        <input
          autoFocus
          className="ev-label-input"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={e => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') { setEditing(false); setDraft(label); }
          }}
        />
        <HelpTip text={help} />
      </span>
    );
  }

  return (
    <span className="ev-label">
      <span
        className="ev-label-text"
        onClick={() => { setDraft(label); setEditing(true); }}
        title="Click to rename"
      >
        {label}
      </span>
      <HelpTip text={help} />
    </span>
  );
}

function SliderControl({ ev, value, onChange, onRename }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const pct = ((value - ev.min) / (ev.max - ev.min)) * 100;
  const formatted = ev.fmt ? ev.fmt(value) : `${value}${ev.unit || ''}`;

  function startEdit() {
    setDraft(String(value));
    setEditing(true);
  }

  function commitEdit() {
    setEditing(false);
    const num = parseFloat(draft);
    if (!isNaN(num)) {
      const clamped = Math.max(ev.min, Math.min(ev.max, num));
      const stepped = ev.step === 1 ? Math.round(clamped) : clamped;
      onChange(stepped);
    }
  }

  return (
    <div className="ev-field">
      <div className="ev-top">
        <EditableLabel label={ev.label} help={ev.help} onRename={onRename} />
        {editing ? (
          <span className="ev-value-edit-wrap">
            <input
              autoFocus
              className="ev-value-input"
              type="number"
              min={ev.min} max={ev.max} step={ev.step ?? 1}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={e => {
                if (e.key === 'Enter') commitEdit();
                if (e.key === 'Escape') setEditing(false);
              }}
            />
            {ev.unit && <span className="ev-value-unit">{ev.unit}</span>}
          </span>
        ) : (
          <span className="ev-value ev-value-clickable" onClick={startEdit} title="Click to type a value">
            {formatted}
          </span>
        )}
      </div>
      <input
        type="range"
        min={ev.min} max={ev.max} step={ev.step ?? 1}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="ev-range"
        style={{ '--fill': `${pct}%` }}
      />
    </div>
  );
}

function ToggleControl({ ev, value, onChange, onRename }) {
  const formatted = ev.fmt ? ev.fmt(value) : (value ? 'Yes' : 'No');
  return (
    <div className="ev-field ev-field-row">
      <EditableLabel label={ev.label} help={ev.help} onRename={onRename} />
      <button
        className={`switch${value ? ' on' : ''}`}
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
      >
        <span className="switch-knob" />
        <span className="switch-text">{formatted}</span>
      </button>
    </div>
  );
}

function SegmentControl({ ev, value, onChange, onRename }) {
  return (
    <div className="ev-field">
      <div className="ev-top">
        <EditableLabel label={ev.label} help={ev.help} onRename={onRename} />
      </div>
      <div className="segment" role="tablist">
        {ev.options.map(o => (
          <button
            key={o.id}
            className={`seg-btn${value === o.id ? ' is-active' : ''}`}
            role="tab"
            aria-selected={value === o.id}
            onClick={() => onChange(o.id)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function EvidenceControls({ investigation, values, onChange }) {
  const [labelOverrides, setLabelOverrides] = useState({});
  if (!investigation) return null;

  function renameLabel(evId, newLabel) {
    setLabelOverrides(prev => ({ ...prev, [evId]: newLabel }));
  }

  return (
    <div className="evidence">
      <div className="evidence-head">
        <h3>Evidence</h3>
        <span className="evidence-sub">Adjust what you know — the chart updates live</span>
      </div>
      <div className="evidence-grid">
        {investigation.evidence_nodes.map(ev => {
          const val = values[ev.id] ?? ev.default;
          const evWithLabel = labelOverrides[ev.id]
            ? { ...ev, label: labelOverrides[ev.id] }
            : ev;
          const onRename = (newLabel) => renameLabel(ev.id, newLabel);
          if (ev.kind === 'slider') {
            return (
              <SliderControl
                key={ev.id} ev={evWithLabel} value={val}
                onChange={v => onChange(ev.id, v)}
                onRename={onRename}
              />
            );
          }
          if (ev.kind === 'toggle') {
            return (
              <ToggleControl
                key={ev.id} ev={evWithLabel} value={val}
                onChange={v => onChange(ev.id, v)}
                onRename={onRename}
              />
            );
          }
          if (ev.kind === 'segment') {
            return (
              <SegmentControl
                key={ev.id} ev={evWithLabel} value={val}
                onChange={v => onChange(ev.id, v)}
                onRename={onRename}
              />
            );
          }
          return null;
        })}
      </div>
    </div>
  );
}
