import { useState } from 'react';
import { IconSend, IconSpinner } from './Icons.jsx';

function buildPlaceholder(investigation) {
  if (!investigation?.evidence_nodes?.length) return 'Describe what you know…';
  const labels = investigation.evidence_nodes.slice(0, 3).map(e => e.label.toLowerCase());
  if (labels.length === 1) return `e.g. Describe ${labels[0]}…`;
  const last = labels.pop();
  return `e.g. Describe ${labels.join(', ')} and ${last}…`;
}

export function NLPInput({ onSubmit, isPlaceholder, investigation }) {
  const [text, setText] = useState('');
  const [status, setStatus] = useState(null); // null | {kind, msg}
  const [busy, setBusy] = useState(false);

  if (isPlaceholder) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setStatus(null);
    try {
      const result = await onSubmit(text.trim());
      if (!result.ok) {
        setStatus({ kind: 'warn', msg: result.message || 'Could not extract evidence.' });
      } else if (!result.llm_available) {
        setStatus({ kind: 'warn', msg: result.message || 'No LLM key configured — add one in Settings.' });
      } else {
        setStatus({ kind: 'ok', msg: 'Evidence sliders updated from your description.' });
      }
    } catch (err) {
      setStatus({ kind: 'warn', msg: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="nlp-bar">
      <form className="nlp-bar-head" onSubmit={handleSubmit}>
        <span className="nlp-bar-label">Describe in plain language:</span>
        <input
          className="nlp-bar-input"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={buildPlaceholder(investigation)}
          disabled={busy}
        />
        <button type="submit" className="nlp-send-btn" disabled={!text.trim() || busy}>
          {busy ? <IconSpinner s={14} /> : <IconSend s={14} />}
          {busy ? 'Analysing…' : 'Analyse'}
        </button>
      </form>
      {status && (
        <div className={`nlp-status ${status.kind}`}>
          <span className="nlp-status-dot" />
          {status.msg}
        </div>
      )}
    </div>
  );
}
