import { useState } from 'react';
import { useWhatIf } from './hooks/useWhatIf.js';
import { Sidebar } from './components/Sidebar.jsx';
import { BarChart } from './components/BarChart.jsx';
import { EvidenceControls } from './components/EvidenceControls.jsx';
import { ExplanationPanel } from './components/ExplanationPanel.jsx';
import { NLPInput } from './components/NLPInput.jsx';
import { SettingsPanel } from './components/SettingsPanel.jsx';
import { NewInvestigationWizard } from './components/NewInvestigationWizard.jsx';
import { Pct } from './components/Pct.jsx';
import { TernaMode } from './components/TernaMode.jsx';

export default function App() {
  const [appMode, setAppMode] = useState('whatif');
  if (appMode === 'terna') return <TernaMode onBack={() => setAppMode('whatif')} />;
  const {
    investigations,
    activeId,
    active,
    activeSummary,
    computed,
    values,
    openWhy,
    loading,
    error,
    wizardOpen,
    setValue,
    selectCase,
    setOpenWhy,
    openWizard,
    onInvestigationCreated,
    deleteInvestigation,
    applyExtractedEvidence,
  } = useWhatIf();

  const [settingsOpen, setSettingsOpen] = useState(false);

  if (loading) return <LoadingShell />;
  if (error) return <ErrorShell message={error} />;

  const isPlaceholder = activeSummary?.is_placeholder ?? true;

  return (
    <div className="app">
      <Sidebar
        investigations={investigations}
        activeId={activeId}
        onSelect={selectCase}
        onNew={openWizard}
        onDelete={deleteInvestigation}
        onSettings={() => setSettingsOpen(true)}
        onTerna={() => setAppMode('terna')}
        settingsOpen={settingsOpen}
      />

      <main className="main">
        {wizardOpen ? (
          <NewInvestigationWizard
            onCreated={onInvestigationCreated}
            onCancel={() => selectCase(activeId)}
          />
        ) : isPlaceholder ? (
          <PlaceholderView title={activeSummary?.title || 'New investigation'} />
        ) : (
          <>
            {/* Header */}
            <header className="case-header">
              <div>
                <h1 className="case-h1">{activeSummary?.title}</h1>
                <p className="case-sub">{active?.subtitle}</p>
              </div>
              {computed && (
                <div className="confidence">
                  <span className="confidence-label">Leading cause</span>
                  <span className="confidence-val">{computed.top.label}</span>
                  <Pct value={computed.top.p} className="confidence-pct" />
                </div>
              )}
            </header>

            {/* NLP input */}
            <NLPInput
              isPlaceholder={isPlaceholder}
              investigation={active}
              onSubmit={applyExtractedEvidence}
            />

            {/* Dashboard: chart + evidence */}
            <div className="dashboard">
              <section className="card chart-card">
                <div className="card-title-row">
                  <h2 className="card-title">Likely causes</h2>
                  <span className="card-hint">
                    Ranked by probability · click <em>Why?</em> for the reasoning
                  </span>
                </div>
                {computed ? (
                  <BarChart
                    results={computed.results}
                    openWhy={openWhy}
                    onToggleWhy={id => setOpenWhy(prev => prev === id ? null : id)}
                    muteOthers={true}
                  />
                ) : (
                  <SkeletonChart />
                )}
              </section>

              <section className="card evidence-card">
                <EvidenceControls
                  investigation={active}
                  values={values}
                  onChange={setValue}
                />
              </section>
            </div>

            {/* What-If explanation */}
            <ExplanationPanel computed={computed} />
          </>
        )}
      </main>

      {settingsOpen && (
        <SettingsPanel onClose={() => setSettingsOpen(false)} />
      )}

    </div>
  );
}

function PlaceholderView({ title }) {
  return (
    <div className="empty">
      <div className="empty-card">
        <h1 className="empty-title">{title}</h1>
        <p className="empty-sub">
          Let's set this up. Describe the problem and the possible causes,
          then add what you know as evidence.
        </p>
        <ol className="empty-steps">
          <li><span className="step-n">1</span> Name the problem in plain language</li>
          <li><span className="step-n">2</span> List 2–4 things that might be causing it</li>
          <li><span className="step-n">3</span> Answer a few guided questions</li>
          <li><span className="step-n">4</span> Watch the ranked causes update as you go</li>
        </ol>
        <button className="empty-cta">Start with a guided template</button>
        <p className="empty-foot">
          This is a placeholder screen — the electricity and café cases are fully worked examples.
        </p>
      </div>
    </div>
  );
}

function SkeletonChart() {
  return (
    <div className="chart">
      {[0.55, 0.35, 0.15].map((w, i) => (
        <div key={i} className="bar-block" style={{ gap: 9 }}>
          <div className="skeleton" style={{ height: 14, width: '40%', marginBottom: 2 }} />
          <div className="skeleton" style={{ height: 17, width: `${w * 100}%` }} />
        </div>
      ))}
    </div>
  );
}

function LoadingShell() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-head">
          <div className="brand">
            <span className="brand-mark" />
            <span className="brand-name">WhatIf</span>
          </div>
        </div>
        <div style={{ padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[1,2,3].map(i => (
            <div key={i} className="skeleton" style={{ height: 56, borderRadius: 13 }} />
          ))}
        </div>
      </aside>
      <main className="main" style={{ justifyContent: 'center', alignItems: 'center', opacity: .5 }}>
        <p style={{ color: 'var(--text-3)' }}>Loading…</p>
      </main>
    </div>
  );
}

function ErrorShell({ message }) {
  return (
    <div className="app" style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)',
        padding: '32px 36px', maxWidth: 480, boxShadow: 'var(--shadow-md)',
      }}>
        <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 10 }}>Cannot connect to backend</h2>
        <p style={{ color: 'var(--text-2)', fontSize: 14, lineHeight: 1.6 }}>
          Make sure the FastAPI server is running on <code
            style={{ fontFamily: 'var(--mono)', fontSize: 12.5, background: 'var(--border-2)', padding: '1px 6px', borderRadius: 4 }}>
            localhost:8000
          </code>.
        </p>
        <p style={{ color: 'var(--text-3)', fontSize: 12.5, marginTop: 10 }}>{message}</p>
      </div>
    </div>
  );
}
