import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { IconSpinner } from './Icons.jsx';

export function SettingsPanel({ onClose }) {
  const [provider, setProvider] = useState('claude');
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [keySource, setKeySource] = useState('none'); // "session" | "env" | "none"
  const [status, setStatus] = useState(null); // null | {kind, msg}
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load current settings on mount
  useEffect(() => {
    api.getSettings().then(s => {
      setProvider(s.provider);
      setKeySource(s.key_source);
      if (s.key_source === 'env') {
        setStatus({
          kind: 'connected',
          msg: `API key loaded from environment variable.`,
        });
      }
    }).catch(() => {});
  }, []);

  async function handleSave() {
    setSaving(true);
    setStatus(null);
    try {
      const updated = await api.saveSettings({
        provider,
        api_key: apiKey || undefined,
      });
      setKeySource(updated.key_source);
      setStatus({ kind: 'connected', msg: 'Settings saved for this session.' });
      setApiKey('');
    } catch (err) {
      setStatus({ kind: 'error', msg: err.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setStatus({ kind: 'testing', msg: 'Testing connection…' });
    try {
      const result = await api.testConnection();
      setStatus({
        kind: result.ok ? 'connected' : 'error',
        msg: result.message,
      });
    } catch (err) {
      setStatus({ kind: 'error', msg: err.message });
    } finally {
      setTesting(false);
    }
  }

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  const statusKind = status?.kind || (keySource === 'none' ? 'none' : 'connected');
  const statusMsg = status?.msg || {
    none:      'No API key configured. Add one below or set an environment variable.',
    env:       'API key loaded from environment variable.',
    session:   'API key set for this session.',
    connected: 'Ready.',
  }[keySource] || '';

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <div className="modal-head">
          <h2 className="modal-title" id="settings-title">LLM Settings</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close settings">✕</button>
        </div>

        {/* Provider */}
        <div className="modal-section">
          <label className="modal-label" htmlFor="provider-select">Provider</label>
          <select
            id="provider-select"
            className="modal-select"
            value={provider}
            onChange={e => setProvider(e.target.value)}
          >
            <option value="claude">Claude (Anthropic)</option>
            <option value="openai">GPT (OpenAI)</option>
          </select>
        </div>

        {/* API Key */}
        <div className="modal-section">
          <label className="modal-label" htmlFor="api-key-input">
            API Key
            {keySource === 'env' && (
              <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: 6, color: 'var(--up)' }}>
                · loaded from env
              </span>
            )}
          </label>
          <div className="modal-key-wrap">
            <input
              id="api-key-input"
              className="modal-key-input"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={
                keySource === 'env' ? '(using env var — paste to override)' :
                keySource === 'session' ? '(session key set — paste to replace)' :
                provider === 'claude' ? 'sk-ant-…' : 'sk-…'
              }
              autoComplete="off"
              spellCheck={false}
            />
            <button
              className="modal-key-toggle"
              type="button"
              onClick={() => setShowKey(v => !v)}
              tabIndex={-1}
            >
              {showKey ? 'hide' : 'show'}
            </button>
          </div>
        </div>

        {/* Status */}
        <div className={`modal-status ${statusKind}`}>
          <span className="modal-status-dot" />
          {statusKind === 'testing'
            ? <span style={{ display:'flex', alignItems:'center', gap:6 }}><IconSpinner s={12} /> {statusMsg}</span>
            : statusMsg}
        </div>

        <div className="modal-divider" />

        {/* Actions */}
        <div className="modal-actions">
          <button
            className="modal-btn secondary"
            onClick={handleTest}
            disabled={testing}
          >
            {testing ? 'Testing…' : 'Test connection'}
          </button>
          <button
            className="modal-btn primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>

        <div className="modal-divider" />
        <p className="modal-hint">
          Keys entered here are stored only in the current server session — never on disk.
          For permanent setup, add them to <code>backend/.env</code> (see <code>.env.example</code>).
          The LLM is only used for natural-language input; all probabilities come from the
          Bayesian engine.
        </p>
      </div>
    </div>
  );
}
