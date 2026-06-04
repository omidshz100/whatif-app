import { IconPlus, IconGear } from './Icons.jsx';

export function Sidebar({ investigations, activeId, onSelect, onNew, onSettings, settingsOpen }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">WhatIf</span>
        </div>
        <p className="sidebar-tagline">Find the most likely cause</p>
      </div>

      <div className="sidebar-section-label">My investigations</div>

      <nav className="case-list">
        {investigations.map(inv => (
          <button
            key={inv.id}
            className={`case-item${inv.id === activeId ? ' is-active' : ''}${inv.is_placeholder ? ' is-new' : ''}`}
            onClick={() => onSelect(inv.id)}
          >
            <span className="case-title">{inv.title}</span>
            {inv.is_placeholder ? (
              <span className="case-result is-empty">Not started yet</span>
            ) : (
              <span className="case-result">
                <span className="case-pct">{Math.round((inv.top_p ?? 0) * 100)}%</span>
                <span className="case-cause">{inv.top_label}</span>
              </span>
            )}
          </button>
        ))}
      </nav>

      <button className="new-btn" onClick={onNew}>
        <IconPlus /> New investigation
      </button>

      <div className="sidebar-footer">
        <button
          className={`settings-btn${settingsOpen ? ' is-active' : ''}`}
          onClick={onSettings}
          title="LLM settings"
        >
          <IconGear s={14} />
          Settings
        </button>
      </div>
    </aside>
  );
}
